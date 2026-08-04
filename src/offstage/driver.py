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

    def pid(self) -> int | None:
        out = self.sh("pgrep", "-x", self.mf.name)
        return int(out.split()[0]) if out else None

    def cost(self, kind: str, tokens: int) -> None:
        if self.cost_log:
            with self.cost_log.open("a") as f:
                f.write(f"{kind} {tokens}\n")

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
        p = self.pid()
        if p:
            subprocess.run(["kill", str(p)])
            time.sleep(1)
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
        args = ["open", "-g", "-a", str(self.mf.app_path), "--args",
                "-NSRequiresAquaSystemAppearance", "YES",
                *self.mf.launch_args,
                "-uitest-port", self.mf.sock_path]
        if reset:
            args += ["-uitest-reset", "1"]
        subprocess.run(args, check=True)
        t0 = time.time()
        while time.time() - t0 < 10:
            if Path(self.mf.sock_path).exists() and self.pid():
                time.sleep(0.8)  # let SwiftUI finish first layout
                return True
        return False

    def stop(self) -> None:
        p = self.pid()
        if p:
            subprocess.run(["kill", str(p)])

    # ---------- actuation ----------

    def _act(self, fn) -> str:
        t0 = time.time()
        fn()
        ms = (time.time() - t0) * 1000  # action only; settle sleep excluded
        time.sleep(0.6)
        return f"done latency_ms={ms:.0f} app_alive={self.pid() is not None}"

    def press(self, identifier: str) -> str:
        return self._act(lambda: self.probe("axpress", self.mf.bundle_id, identifier))

    def menu(self, menu: str, item: str) -> str:
        return self._act(lambda: self.probe("axmenu", self.mf.bundle_id, menu, item,
                                            timeout=60))

    def port(self, payload: str) -> str:
        t0 = time.time()
        reply = self.port_cmd(json.loads(payload))
        ms = (time.time() - t0) * 1000
        time.sleep(0.6)
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
        ax = self.probe("axdump", self.mf.bundle_id)
        scan = self.probe("axscan", self.mf.bundle_id).replace("\n", " ")
        state = self.port_cmd({"cmd": "state"})
        txt = json.dumps({"ax": ax.split("\n"), "defaults": self.defaults_json(),
                          "port_state": state, "a11y_scan": scan})
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
            self.probe("resize", self.mf.bundle_id, g.width, g.height)
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
                self.probe("resize", self.mf.bundle_id, g.width, g.height + 1)
                time.sleep(0.4)
                self.probe("resize", self.mf.bundle_id, g.width, g.height)
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
