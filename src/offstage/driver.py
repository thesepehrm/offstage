"""The app-agnostic QA driver: the ONLY interface an agent uses to exercise an
app under test. All per-app knowledge lives in the manifest (data, not code).

Verbs: start / restart / stop / press / menu / port / observe / golden.

Safety and reliability rules encoded here (each one cost a broken run in the
research program — see docs/limits.md):
  * refuse to run against a locked screen (channels silently degrade);
  * clear crash residue (CrashReporter plist + saved state) before every launch;
  * pin per-app light appearance so goldens survive system dark mode;
  * capture goldens only from the manifest's canonical fixture state;
  * verify against ground truth (UserDefaults / port state), never only the
    actuation layer's echo.
"""
from __future__ import annotations

import json
import os
import plistlib
import shutil
import socket
import subprocess
import time
from pathlib import Path

from . import probes
from .batch import MISSING, resolve
from .manifest import Manifest


class SessionLockedError(RuntimeError):
    """The login session is locked or the display is asleep: AX trees come back
    empty, SCK captures fail, and AXPress stalls for seconds. Unlock first
    (`caffeinate -du` keeps the display awake during long runs)."""


def work_dir() -> Path:
    d = Path(os.environ.get("OFFSTAGE_DIR", Path.home() / ".cache" / "offstage"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Driver:
    def __init__(self, manifest: Manifest, mode: str | None = None,
                 cost_log: Path | None = None):
        self.mf = manifest
        self.bin = probes.ensure()
        self.mode = mode or os.environ.get("OFFSTAGE_OBSERVE", "ax")
        self.shots = work_dir() / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        env_log = os.environ.get("OFFSTAGE_COST_LOG")
        self.cost_log = cost_log or (Path(env_log) if env_log else None)

    # ---------- plumbing ----------

    def sh(self, *cmd, timeout=60) -> str:
        return subprocess.run([str(c) for c in cmd], capture_output=True,
                              text=True, timeout=timeout).stdout.strip()

    def probe(self, name, *args, timeout=60) -> str:
        return self.sh(self.bin / name, *args, timeout=timeout)

    def _processes(self) -> list[tuple[int, str]]:
        """Every running process whose executable name matches the manifest,
        with its full command line.

        Two steps because BSD `pgrep` cannot print arguments: `-a` means
        something else here than it does on Linux (it prints bare pids), and
        `-l` prints the process name only. `ps` supplies the command line.
        """
        pids = [x for x in self.sh("pgrep", "-x", self.mf.name).split() if x.isdigit()]
        if not pids:
            return []
        out = self.sh("ps", "-o", "pid=,args=", "-p", ",".join(pids))
        rows = []
        for line in out.splitlines():
            head, _, args = line.strip().partition(" ")
            if head.isdigit():
                rows.append((int(head), args))
        return rows

    def pid(self) -> int | None:
        """The pid of THIS manifest's instance.

        Never `pgrep -x <name>` alone. One app built from several checkouts —
        worktrees, a release build beside a debug one — puts several processes
        of the same name and the same bundle id on the machine, and the first
        match is arbitrary. Taking it means `launch` kills somebody else's app,
        `app_alive` reports a stranger's liveness, and the AX probes describe a
        window the socket in this manifest does not talk to.

        The socket path is the discriminator: it is per-manifest, and `launch`
        passes it on the command line. Fall back to the app bundle path, then
        to the bare name for apps that carry neither.

        The last fallback is a GUESS, and read-only callers are the only ones
        allowed to take it — see `owned_pid`.
        """
        return self._resolve_pid()[0]

    def owned_pid(self) -> int | None:
        """The pid only when a marker proves it is ours.

        `pid`'s lone-process fallback exists for apps that carry neither
        marker, and it is right for read-only questions — liveness, which pid
        the AX probes should address. It is wrong for anything destructive: the
        one process running is the stranger's precisely when our own instance
        is NOT up, so `stop` would kill an app this session never launched
        (observed: an `offstage stop` for a manifest whose instance had never
        started quit the user's installed copy of the same app).
        """
        p, matched = self._resolve_pid()
        return p if matched else None

    def _resolve_pid(self) -> tuple[int | None, bool]:
        """(pid, matched-a-marker). False means the pid is a guess."""
        rows = self._processes()
        if not rows:
            return None, False
        for marker in (f"-uitest-port {self.mf.sock_path}", str(self.mf.app_path)):
            for p, args in rows:
                if marker in args:
                    return p, True
        return (rows[0][0], False) if len(rows) == 1 else (None, False)

    def strangers(self) -> list[tuple[int, str]]:
        """Same-named processes that are NOT this manifest's instance. They
        share the bundle id, so they compete for every bundle-id-addressed
        channel — and a `start` in their session terminates this one."""
        mine = self.pid()
        return [(p, args) for p, args in self._processes() if p != mine]

    def stranger_note(self) -> str:
        """A one-line warning when another copy of the app is running. It cannot
        be fixed from here — both copies share a bundle id, so they share the
        UserDefaults domain this harness reads as ground truth, and a `start`
        or an `xcodebuild test` in that other checkout terminates this
        instance. Saying so beats letting the run fail mysteriously later."""
        others = self.strangers()
        if not others:
            return ""
        where = ", ".join(sorted({self.bundle_of(args) for _, args in others}))
        return (f" WARNING: {len(others)} other {self.mf.name} process(es) running"
                f" from {where}; they share this bundle id and can terminate this"
                " instance or answer bundle-id-addressed probes")

    @staticmethod
    def bundle_of(args: str) -> str:
        head = args.split(" -")[0]
        marker = ".app/"
        return head[:head.index(marker) + 4] if marker in head else head

    def target(self) -> str:
        """What the AX probes address. A pid when we know ours, otherwise the
        bundle id — probes accept either, and a stale bundle id at least keeps
        single-instance hosts working."""
        p = self.pid()
        return str(p) if p else self.mf.bundle_id

    def cost(self, kind: str, tokens: int) -> None:
        if self.cost_log:
            with self.cost_log.open("a") as f:
                f.write(f"{kind} {tokens}\n")

    def wait_gone(self, p: int, timeout: float = 3.0) -> None:
        """Wait for pid `p` itself to leave, not for `pid()` to go quiet — with
        a stranger running, `pid()`'s fallback keeps answering after our own
        process is gone and every wait would burn the full timeout."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if p not in {row[0] for row in self._processes()}:
                return
            time.sleep(0.05)
        subprocess.run(["kill", "-9", str(p)])
        time.sleep(0.2)

    def settle(self, timeout: float = 2.0) -> None:
        """Post-action settle: a port round-trip instead of a flat sleep. The
        port handler replies via DispatchQueue.main.sync, so one successful
        round-trip proves every main-thread task queued before it (AXPress
        action handlers, store writes) has completed. Apps without a live
        port keep the old flat settle."""
        r = self.port_cmd({"cmd": "offstage.ping"}, timeout=timeout)
        if not (isinstance(r, dict) and "error" not in r):
            time.sleep(0.6)

    def check_session_unlocked(self) -> None:
        if "ScreenIsLocked = 1" in self.probe("sesslock"):
            raise SessionLockedError(
                "screen session is locked; background channels are degraded. "
                "Unlock the screen (and keep the display awake: caffeinate -du).")

    # ---------- semantic port ----------

    def port_cmd(self, obj: dict, timeout: float = 8.0) -> dict | None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect(self.mf.sock_path)
            s.sendall((json.dumps(obj) + "\n").encode())
            buf = b""
            while b"\n" not in buf:
                c = s.recv(4096)
                if not c:
                    break
                buf += c
            return json.loads(buf) if buf else None
        except Exception as e:  # noqa: BLE001 — reply shape is part of the protocol
            return {"error": repr(e)}
        finally:
            s.close()

    # ---------- ground truth ----------

    @staticmethod
    def _jsonable(v):
        """plist value -> JSON-safe value. Binary blobs over 200 bytes are
        dropped unless they decode as JSON (Data holding a JSON list is a
        common persistence pattern)."""
        if isinstance(v, bytes):
            try:
                j = json.loads(v)
                if isinstance(j, (list, dict)):
                    return j
            except Exception:
                pass
            if len(v) <= 200:
                return {"_bytes_hex": v.hex()}
            return f"<binary {len(v)} bytes dropped>"
        if isinstance(v, dict):
            return {k: Driver._jsonable(x) for k, x in v.items()}
        if isinstance(v, list):
            return [Driver._jsonable(x) for x in v]
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    def defaults_json(self):
        raw = subprocess.run(["defaults", "export", self.mf.bundle_id, "-"],
                             capture_output=True).stdout
        try:
            return self._jsonable(plistlib.loads(raw))
        except Exception as e:  # empty/absent domain
            return {"error": repr(e)}

    # ---------- lifecycle ----------

    def launch(self, reset: bool) -> bool:
        self.check_session_unlocked()
        # owned_pid, not pid: this kills the previous instance, and a guessed
        # pid here means killing a copy that belongs to somebody else. `open -n`
        # below starts ours regardless of what else is running.
        p = self.owned_pid()
        if p:
            subprocess.run(["kill", str(p)])
            self.wait_gone(p)
        Path(self.mf.sock_path).unlink(missing_ok=True)
        # Drop crash-recovery residue: after a crash, the CrashReporter flag
        # plist (and any saved state) makes the next launch show the modal
        # "unexpectedly quit, reopen windows?" dialog, which hijacks AX scans,
        # resize, and captures. (-ApplePersistenceIgnoreState would also prevent
        # the dialog, but it suppresses window creation entirely for a
        # background-launched SwiftUI WindowGroup app.)
        shutil.rmtree(Path.home() / "Library/Saved Application State"
                      / f"{self.mf.bundle_id}.savedState", ignore_errors=True)
        for f in (Path.home() / "Library/Application Support/CrashReporter").glob(
                f"{self.mf.name}_*.plist"):
            f.unlink(missing_ok=True)
        # Pin light appearance for this app only (argument-domain defaults
        # override): goldens are appearance-sensitive and a system dark-mode
        # switch flips ~80% of pixels.
        #
        # ALL harness flags are passed as `-key value` pairs: AppKit strips
        # those from the launch arguments, while leftover bare args are treated
        # as documents to open — and with >=3 leftovers a SwiftUI WindowGroup
        # app never creates its window at all (observed macOS 26.1).
        #
        # `-n` forces a new instance from THIS bundle path. Without it
        # LaunchServices resolves the request by bundle id and hands back a
        # copy already running from a different build, so the launch silently
        # no-ops and every later command drives somebody else's window.
        args = ["open", "-g", "-n", "-a", str(self.mf.app_path), "--args",
                "-NSRequiresAquaSystemAppearance", "YES",
                *self.mf.launch_args,
                "-uitest-port", self.mf.sock_path]
        if reset:
            args += ["-uitest-reset", "1"]
        subprocess.run(args, check=True)
        # Launch is settled when the port answers (main run loop alive) AND an
        # AXWindow exists (SwiftUI finished first layout) — replaces the old
        # flat 0.8 s guess. Apps without a port fall back to that flat wait.
        t0 = time.time()
        while time.time() - t0 < 10:
            if Path(self.mf.sock_path).exists() and self.pid():
                break
            time.sleep(0.05)
        else:
            return False
        while time.time() - t0 < 10:
            r = self.port_cmd({"cmd": "offstage.ping"}, timeout=1.0)
            if (isinstance(r, dict) and "error" not in r
                    and "AXWindow" in self.probe("axdump", self.target())):
                return True
            time.sleep(0.05)
        return False

    def stop(self) -> bool:
        """Quit this manifest's instance. Returns False — without killing
        anything — when no process carries one of this manifest's markers,
        because the only candidate left is a stranger's app."""
        p = self.owned_pid()
        if not p:
            return False
        subprocess.run(["kill", str(p)])
        self.wait_gone(p)
        return True

    # ---------- actuation ----------

    def _act(self, fn) -> str:
        t0 = time.time()
        fn()
        ms = (time.time() - t0) * 1000  # action only; settle excluded
        self.settle()
        return f"done latency_ms={ms:.0f} app_alive={self.pid() is not None}"

    def press(self, identifier: str) -> str:
        return self._act(lambda: self.probe("axpress", self.target(), identifier))

    def menu(self, menu: str, item: str) -> str:
        return self._act(lambda: self.probe("axmenu", self.target(), menu, item,
                                            timeout=60))

    def port(self, payload: str) -> str:
        t0 = time.time()
        reply = self.port_cmd(json.loads(payload))
        ms = (time.time() - t0) * 1000
        self.settle()
        return (json.dumps(reply)
                + f"\ndone latency_ms={ms:.0f} app_alive={self.pid() is not None}")

    def dispatch(self, cmd: str, args: list[str], settle: bool = True) -> str:
        """Run one driver verb (used for canonical-fixture steps)."""
        if cmd == "press":
            return self.press(args[0])
        if cmd == "menu":
            return self.menu(args[0], args[1])
        if cmd == "port":
            if settle:
                return self.port(args[0])
            # Fixture port steps skip the settle sleep: capture timing must
            # match the timing the goldens were baked with (a shifted
            # text-caret blink phase shows up as a nonzero diff).
            self.port_cmd(json.loads(args[0]))
            return ""
        if cmd == "sleep":
            time.sleep(float(args[0]))
            return ""
        raise ValueError(f"unknown driver verb: {cmd}")

    # ---------- batch ----------

    def _snapshot(self) -> dict:
        return {"defaults": self.defaults_json(), "port": self.port_cmd({"cmd": "state"})}

    def _step(self, step: list) -> dict:
        """Run one batch step; return its result record (never raises for an
        app-level failure — a failed step is data, not a crash)."""
        verb, args = step[0], list(step[1:])
        if verb == "expect":
            if len(args) != 2:
                raise ValueError("expect takes <json-pointer> <expected-json>")
            want = json.loads(args[1])
            got = resolve(self._snapshot(), args[0])
            return {"ok": got == want, "pointer": args[0], "want": want,
                    "got": got if got is not MISSING else repr(got)}
        if verb in ("start", "restart"):
            launched = self.launch(verb == "start")
            return {"out": f"launched={launched}{self.stranger_note()}"}
        if verb == "stop":
            if self.stop():
                return {"out": "stopped"}
            return {"out": "not stopped: no process carries this manifest's"
                           " markers; refusing to kill another copy"}
        if verb == "observe":
            return {"out": self.observe()}
        if verb == "golden":
            if args[:1] not in (["check"], ["bake"]):
                raise ValueError("golden takes 'check' or 'bake'")
            return {"out": self.golden(make=args[0] == "bake")}
        return {"out": self.dispatch(verb, args)}

    def batch(self, steps, stop: bool = True) -> dict:
        """Run a step list in this process and return one JSON-able result.

        Steps are the driver verbs (`press`/`menu`/`port`/`sleep`), lifecycle
        (`start`/`restart`/`stop`), perception (`observe`, `golden check|bake`),
        and `expect <pointer> <json>`. By default the run stops at the first
        failing step; a dead app always stops it, since every later step would
        report a failure caused by the first one."""
        if not isinstance(steps, list) or not all(
                isinstance(s, list) and s and all(isinstance(x, str) for x in s)
                for s in steps):
            raise ValueError("batch takes a list of [verb, ...args] string steps")
        out, failed = [], None
        for i, step in enumerate(steps):
            t0 = time.time()
            try:
                rec = self._step(step)
            except Exception as e:  # noqa: BLE001 — a bad step is a result, not a traceback
                rec = {"error": f"{type(e).__name__}: {e}"}
            rec = {"i": i, "verb": step[0], **rec, "ms": round((time.time() - t0) * 1000)}
            rec.setdefault("ok", "error" not in rec)
            if rec["ok"] and step[0] != "stop" and self.pid() is None:
                rec["ok"] = False
                rec["error"] = "app died during this step"
            out.append(rec)
            if not rec["ok"]:
                failed = i if failed is None else failed
                if stop or "died" in rec.get("error", ""):
                    break
        res = {"ok": failed is None, "steps": out,
               "app_alive": self.pid() is not None}
        if failed is not None:
            res["failed_step"] = failed
        txt = json.dumps(res)
        self.cost("text", len(txt) // 4)
        return res

    # ---------- perception ----------

    def observe(self) -> str:
        p = self.pid()
        if not p:
            return "app_alive=False (no observation possible)"
        if self.mode == "screenshot":
            shot = self.shots / f"shot-{int(time.time() * 1000)}.png"
            self.probe("sckwin", p, shot, timeout=30)
            if not shot.exists():
                return "capture failed"
            dims = self.sh("sips", "-g", "pixelWidth", "-g", "pixelHeight", shot)
            w = int(dims.split("pixelWidth:")[1].split()[0])
            h = int(dims.split("pixelHeight:")[1].split()[0])
            scale = min(1.0, 1568 / max(w, h))
            self.cost("image", int(w * scale * h * scale / 750))
            return f"screenshot: {shot}  (read it as an image)"
        ax = self.probe("axdump", self.target())
        scan = self.probe("axscan", self.target()).replace("\n", " ")
        state = self.port_cmd({"cmd": "state"})
        payload = {"ax": ax.split("\n"), "defaults": self.defaults_json(),
                   "port_state": state, "a11y_scan": scan}
        # Surface the ambiguity rather than describing one instance as if it
        # were the only one: the persisted defaults below belong to whichever
        # copy wrote last, and they all share the domain.
        others = self.strangers()
        if others:
            payload["other_instances"] = [
                {"pid": p, "bundle": self.bundle_of(args)} for p, args in others
            ]
        txt = json.dumps(payload)
        self.cost("text", len(txt) // 4)
        return txt

    # ---------- goldens ----------

    def golden(self, make: bool = False) -> str:
        """Reset to the manifest's canonical fixture state, then capture at each
        golden size and pixdiff (or write the goldens with make=True). Goldens
        diffed from arbitrary session state confound the check — canonical
        state always comes first."""
        if not self.launch(True):
            return "golden ABORT: relaunch failed"
        for step in self.mf.canonical_fixture:
            self.dispatch(step[0], step[1:], settle=(step[0] != "port"))
        p = self.pid()
        thr = self.mf.golden_threshold_pct
        out = []
        for g in self.mf.goldens:
            self.probe("resize", self.target(), g.width, g.height)
            time.sleep(1.2)
            shot = self.shots / f"gcheck-{self.mf.name}-{g.name}.png"
            self.probe("sckwin", p, shot, timeout=30)
            if make:
                g.file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(shot, g.file)
                out.append(f"{g.name}: GOLDEN WRITTEN {g.file}")
                continue
            if not g.file.exists():
                out.append(f"{g.name}: NO GOLDEN at {g.file} (run `golden bake` first)")
                continue
            d = self.probe("pixdiff", g.file, shot)
            # A >=50% diff is a bogus capture (SCK sometimes returns a blank
            # frame right after a resize), not a plausible visual change;
            # nudge a redraw and recapture once.
            try:
                pct = float(d.split("DIFF_PCT=")[1].split()[0])
            except (IndexError, ValueError):
                pct = 0.0
            if pct >= 50.0:
                self.probe("resize", self.target(), g.width, g.height + 1)
                time.sleep(0.4)
                self.probe("resize", self.target(), g.width, g.height)
                time.sleep(1.2)
                self.probe("sckwin", p, shot, timeout=30)
                d = self.probe("pixdiff", g.file, shot) + " (recaptured)"
            out.append(f"{g.name}: {d}")
        txt = (" | ".join(out)
               + f" (diffs vs last-known-good visual goldens; >{thr}% = visual change)"
               + " NOTE: session state was RESET to the canonical golden state;"
               + " your previous app state is gone.")
        self.cost("text", len(txt) // 4)
        return txt
