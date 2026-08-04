#!/usr/bin/env python3
"""NotesApp deterministic probe battery. No model in the loop.

The batteries ARE the harness's integration tests: every probe runs only
through background-safe channels (AX scan, AXPress, semantic port, UserDefaults
ground truth, SCK canonical goldens) while the desktop stays usable.

Usage: battery_notes.py <variant-id> [--make-golden]
Assumes the app is already built at the manifest's app_path. Writes
bench/data/notes-<variant>.json.

Needs a live macOS session: unlocked screen, Accessibility + Screen Recording
permissions granted to the host terminal.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from offstage.driver import Driver  # noqa: E402
from offstage.manifest import Manifest  # noqa: E402

HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parent / "examples" / "notesapp.manifest.json"

results = []


def probe(name, ok, detail, ms=None):
    results.append({"probe": name, "pass": bool(ok), "detail": str(detail)[:300],
                    **({"ms": round(ms, 1)} if ms is not None else {})})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:120]}")


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "local"
    make_golden = "--make-golden" in sys.argv
    d = Driver(Manifest.load(MANIFEST))

    def titles():
        # Ground truth: the persisted store, never the port's echo alone.
        notes = d.defaults_json().get("notes.v1", [])
        return [n["title"] for n in notes] if isinstance(notes, list) else []

    front_before = d.probe("front")

    # P1 launch (fresh reset, port up)
    t0 = time.time()
    up = d.launch(True)
    probe("launch", up, f"port up={up}", (time.time() - t0) * 1000)
    if not up:
        return finish(d, variant, front_before)

    # P2 a11y scan vs the manifest baseline
    scan = d.probe("axscan", d.mf.bundle_id)
    got = {}
    if "UNLABELLED_BUTTONS=" in scan:
        got = {"unlabelled_buttons": int(scan.split("UNLABELLED_BUTTONS=")[1].split()[0]),
               "empty_menu_items": int(scan.split("EMPTY_MENU_ITEMS=")[1].split()[0])}
    probe("a11y-scan", got == d.mf.a11y_baseline,
          f"counts={got} baseline={d.mf.a11y_baseline}")

    # P3 journey-create
    t0 = time.time()
    d.press("addNote")
    t = titles()
    probe("journey-create", t == ["Untitled"], f"titles={t}", (time.time() - t0) * 1000)

    # P4 journey-delete-undo
    t0 = time.time()
    d.menu("File", "Delete Note")
    mid = titles()
    undo = d.probe("axpress", d.mf.bundle_id, "undoDelete")
    if "FAIL" in undo:  # overflow popup can race its first open; one retry
        time.sleep(0.7)
        undo = d.probe("axpress", d.mf.bundle_id, "undoDelete") + " (retried)"
    time.sleep(0.6)
    end = titles()
    probe("journey-delete-undo", mid == [] and end == ["Untitled"],
          f"after-delete={mid} after-undo={end} {undo}", (time.time() - t0) * 1000)

    # P5 journey-select-delete (needs 2 distinctly named notes)
    t0 = time.time()
    if titles() != ["Untitled"]:  # repair state so this probe is independent
        d.launch(True)
        d.press("addNote")
    d.press("addNote")
    d.port_cmd({"cmd": "rename", "index": 0, "title": "TOP"})
    d.port_cmd({"cmd": "rename", "index": 1, "title": "BOTTOM"})
    time.sleep(0.3)
    d.menu("File", "Delete Note")
    t = titles()
    stale = d.probe("axhas", d.mf.bundle_id, "emptyDetail")
    probe("journey-select-delete", t == ["BOTTOM"] and stale == "HAS=0",
          f"titles={t} emptyDetail:{stale}", (time.time() - t0) * 1000)

    # P6 port-rename (hang + no-op detector)
    t0 = time.time()
    reply = d.port_cmd({"cmd": "rename", "index": 0, "title": "RENAMED"})
    ms = (time.time() - t0) * 1000
    time.sleep(0.3)
    t = titles()
    probe("port-rename", t[:1] == ["RENAMED"] and ms < 2000,
          f"titles={t} reply={reply}", ms)

    # P7 port-reorder normal + edge (crash detector)
    d.press("addNote")
    before = titles()
    d.port_cmd({"cmd": "reorder", "from": 1, "to": 0})
    time.sleep(0.3)
    after = titles()
    swapped = len(before) == 2 and after == [before[1], before[0]]
    d.port_cmd({"cmd": "reorder", "from": 99, "to": 0})
    time.sleep(1.0)
    alive = d.pid() is not None
    probe("port-reorder", swapped and alive,
          f"before={before} after={after} alive-after-edge={alive}")
    if not alive:
        return finish(d, variant, front_before)

    # P8 canonical goldens (reset to fixture state, two window sizes, pixel diff)
    out = d.golden(make=make_golden)
    if make_golden:
        probe("canonical-golden", "GOLDEN WRITTEN" in out, out[:280])
    else:
        pcts = []
        for part in out.split("DIFF_PCT=")[1:]:
            try:
                pcts.append(float(part.split()[0]))
            except ValueError:
                pass
        probe("canonical-golden",
              len(pcts) == len(d.mf.goldens)
              and all(p <= d.mf.golden_threshold_pct for p in pcts),
              out[:280])

    # P9 persistence across relaunch (golden left canonical GOLD-A/GOLD-B state)
    expect = titles()
    up = d.launch(False)
    t = titles() if up else []
    probe("persistence", up and t == expect and expect != [],
          f"expected={expect} got={t}")

    finish(d, variant, front_before)


def finish(d, variant, front_before):
    d.stop()
    front_after = d.probe("front")
    results.append({"probe": "app-never-frontmost",
                    "pass": d.mf.bundle_id not in (front_before, front_after),
                    "detail": f"{front_before} -> {front_after}"})
    out = HERE / "data" / f"notes-{variant}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"variant": variant, "results": results}, indent=1))
    print(f"wrote {out}")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


if __name__ == "__main__":
    main()
