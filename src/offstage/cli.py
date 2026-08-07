"""offstage CLI.

    offstage probes build              compile the Swift probe binaries
    offstage doctor                    check host prerequisites
    offstage validate <manifest>       validate a per-app manifest
    offstage start <manifest>          launch fresh (full state reset)
    offstage restart <manifest>        quit + relaunch WITHOUT reset (persistence check)
    offstage stop <manifest>           quit the app
    offstage press <manifest> <id>     AXPress a button by AX identifier
    offstage menu <manifest> <m> <i>   AXPress a menu-bar item by titles
    offstage port <manifest> <json>    send raw JSON to the app's agent port
    offstage observe <manifest>        perception snapshot (--mode ax|screenshot)
    offstage golden check <manifest>   reset to canonical fixture state, capture, diff
    offstage golden bake <manifest>    same, but WRITE the golden files
    offstage batch <manifest> <steps>  run a whole step list in one process, one JSON out
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, probes
from .driver import Driver, SessionLockedError
from .manifest import Manifest, ManifestError


def _driver(args) -> Driver:
    return Driver(Manifest.load(args.manifest),
                  mode=getattr(args, "mode", None))


def cmd_probes(args) -> int:
    d = probes.build(force=args.force)
    print(f"probes ready in {d}")
    return 0


def cmd_doctor(args) -> int:
    import shutil as _sh
    ok = True
    if sys.platform != "darwin":
        print("FAIL  offstage only runs on macOS")
        return 1
    if _sh.which("swiftc"):
        print("ok    swiftc found")
    else:
        print("FAIL  swiftc not found — install Xcode command-line tools")
        ok = False
    try:
        b = probes.ensure()
        print(f"ok    probes compiled in {b}")
    except Exception as e:
        print(f"FAIL  probe build: {e}")
        return 1
    d = Driver.__new__(Driver)
    d.bin = b
    lock = d.probe("sesslock")
    if "ScreenIsLocked = 1" in lock:
        print("FAIL  screen session is LOCKED — unlock it; background AX/SCK degrade silently")
        ok = False
    else:
        print("ok    screen session unlocked")
    print("note  Accessibility permission: grant to your terminal/agent host in "
          "System Settings > Privacy & Security > Accessibility (probes print NOAPP/empty "
          "trees without it)")
    print("note  Screen Recording permission: required for sckwin golden captures")
    print("note  keep the display awake during runs: caffeinate -du")
    return 0 if ok else 1


def cmd_skill(args) -> int:
    import shutil as _sh
    src = Path(__file__).resolve().parent / "skill" / "offstage-qa"
    if not src.exists():
        print(f"skill files missing from package: {src}")
        return 1
    target = Path(args.target).expanduser() / "offstage-qa"
    target.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        _sh.copyfile(f, target / f.name)
    print(f"installed skill to {target}")
    print("restart your agent session (or /skills reload) to pick it up")
    return 0


def cmd_validate(args) -> int:
    try:
        mf = Manifest.load(args.manifest)
    except ManifestError as e:
        print(f"INVALID: {e}")
        return 1
    print(f"ok  {mf.name} ({mf.bundle_id}); {len(mf.canonical_fixture)} fixture steps, "
          f"{len(mf.goldens)} goldens, threshold {mf.golden_threshold_pct}%")
    if not mf.app_path.exists():
        print(f"warn  app_path does not exist (yet): {mf.app_path}")
    return 0


def cmd_lifecycle(args) -> int:
    d = _driver(args)
    if args.cmd == "start":
        print(f"started={d.launch(True)} app_alive={d.pid() is not None}")
    elif args.cmd == "restart":
        print(f"restarted={d.launch(False)} app_alive={d.pid() is not None}")
    else:
        d.stop()
        print("stopped")
    return 0


def cmd_act(args) -> int:
    d = _driver(args)
    if args.cmd == "press":
        print(d.press(args.identifier))
    elif args.cmd == "menu":
        print(d.menu(args.menu, args.item))
    else:
        print(d.port(args.json))
    return 0


def cmd_observe(args) -> int:
    print(_driver(args).observe())
    return 0


def cmd_batch(args) -> int:
    """Steps come from inline JSON, a .json file, or stdin ('-')."""
    src = args.steps
    if src == "-":
        raw = sys.stdin.read()
    elif src.lstrip()[:1] in ("[", "{"):
        raw = src
    else:
        p = Path(src)
        if not p.exists():
            print(f"no such steps file: {p} (pass inline JSON, a file path, or '-')")
            return 64
        raw = p.read_text()
    try:
        steps = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"steps are not valid JSON: {e}")
        return 64
    try:
        res = _driver(args).batch(steps, stop=not args.keep_going)
    except ValueError as e:
        print(str(e))
        return 64
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


def cmd_golden(args) -> int:
    print(_driver(args).golden(make=(args.golden_cmd == "bake")))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="offstage",
        description="Background-safe autonomous QA harness for macOS apps.")
    p.add_argument("--version", action="version", version=f"offstage {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probes", help="manage probe binaries")
    spp = sp.add_subparsers(dest="probes_cmd", required=True)
    b = spp.add_parser("build", help="compile the Swift probes")
    b.add_argument("--force", action="store_true")
    b.set_defaults(fn=cmd_probes)

    sp = sub.add_parser("doctor", help="check host prerequisites")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("skill", help="install the agent skill (Claude Code etc.)")
    spp = sp.add_subparsers(dest="skill_cmd", required=True)
    si = spp.add_parser("install", help="copy the offstage-qa skill into a skills dir")
    si.add_argument("--target", default="~/.claude/skills",
                    help="skills directory (default: ~/.claude/skills)")
    si.set_defaults(fn=cmd_skill)

    sp = sub.add_parser("validate", help="validate a manifest")
    sp.add_argument("manifest")
    sp.set_defaults(fn=cmd_validate)

    for name, hlp in (("start", "launch fresh (full state reset)"),
                      ("restart", "relaunch WITHOUT reset (persistence check)"),
                      ("stop", "quit the app")):
        sp = sub.add_parser(name, help=hlp)
        sp.add_argument("manifest")
        sp.set_defaults(fn=cmd_lifecycle)

    sp = sub.add_parser("press", help="AXPress a button by AX identifier")
    sp.add_argument("manifest")
    sp.add_argument("identifier")
    sp.set_defaults(fn=cmd_act)

    sp = sub.add_parser("menu", help="AXPress a menu-bar item by titles")
    sp.add_argument("manifest")
    sp.add_argument("menu")
    sp.add_argument("item")
    sp.set_defaults(fn=cmd_act)

    sp = sub.add_parser("port", help="send raw JSON to the app's agent port")
    sp.add_argument("manifest")
    sp.add_argument("json")
    sp.set_defaults(fn=cmd_act)

    sp = sub.add_parser("observe", help="perception snapshot")
    sp.add_argument("manifest")
    sp.add_argument("--mode", choices=["ax", "screenshot"], default=None,
                    help="default: ax (or $OFFSTAGE_OBSERVE)")
    sp.set_defaults(fn=cmd_observe)

    sp = sub.add_parser(
        "batch", help="run a step list in one process (one JSON result)",
        description="Steps: [[\"start\"],[\"press\",\"addNote\"],"
                    "[\"expect\",\"/defaults/notes.v1/0/title\",\"\\\"Untitled\\\"\"]]. "
                    "Verbs: start restart stop press menu port sleep observe "
                    "golden check|bake expect <json-pointer> <expected-json>. "
                    "expect resolves against {defaults: persisted store, "
                    "port: the port's state reply}.")
    sp.add_argument("manifest")
    sp.add_argument("steps", help="inline JSON, a path to a .json file, or '-' for stdin")
    sp.add_argument("--keep-going", action="store_true",
                    help="run every step even after a failure (default: stop at the first)")
    sp.add_argument("--mode", choices=["ax", "screenshot"], default=None,
                    help="observe mode for observe steps")
    sp.set_defaults(fn=cmd_batch)

    sp = sub.add_parser("golden", help="canonical-state visual goldens")
    sp.add_argument("golden_cmd", choices=["check", "bake"])
    sp.add_argument("manifest")
    sp.set_defaults(fn=cmd_golden)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except SessionLockedError as e:
        print(f"ABORT: {e}")
        return 2
    except ManifestError as e:
        print(f"manifest error: {e}")
        return 64


if __name__ == "__main__":
    sys.exit(main())
