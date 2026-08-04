#!/usr/bin/env python3
"""ConvertApp deterministic probe battery. No model in the loop.

Usage: battery_convert.py <variant-id> [--make-golden]
Assumes the app is already built at the manifest's app_path. Writes
bench/data/convert-<variant>.json.

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
MANIFEST = HERE.parent / "examples" / "convertapp.manifest.json"

results = []


def probe(name, ok, detail, ms=None):
    results.append({"probe": name, "pass": bool(ok), "detail": str(detail)[:300],
                    **({"ms": round(ms, 1)} if ms is not None else {})})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {str(detail)[:120]}")


def timed_port(d, obj):
    t0 = time.time()
    reply = d.port_cmd(obj)
    return reply or {}, (time.time() - t0) * 1000


def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "local"
    make_golden = "--make-golden" in sys.argv
    d = Driver(Manifest.load(MANIFEST))
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
          f"counts={got} baseline={d.mf.a11y_baseline} :: {scan.replace(chr(10), ' ')}")

    # P3 convert-journey: 1000 m -> km via port, AX-read result agrees
    t0 = time.time()
    d.port_cmd({"cmd": "set", "field": "lengthInput", "value": "1000"})
    r, _ = timed_port(d, {"cmd": "units", "tab": "length", "from": "m", "to": "km"})
    ax = d.probe("axdump", d.mf.bundle_id)
    axline = next((l for l in ax.splitlines() if "id=lengthResult" in l), "")
    probe("convert-journey",
          r.get("lengthResult") == "1 km" and 'val="1 km"' in axline,
          f"port={r.get('lengthResult')!r} ax={axline!r}", (time.time() - t0) * 1000)

    # P4 swap-journey: AXPress swapUnits, units swapped in port state
    t0 = time.time()
    d.press("swapUnits")
    r, _ = timed_port(d, {"cmd": "state"})
    got = (r.get("lengthFrom"), r.get("lengthTo"))
    probe("swap-journey", got == ("km", "m"), f"from/to after press = {got}",
          (time.time() - t0) * 1000)

    # P5 stale-check: change ONLY the to-unit, result must follow it
    t0 = time.time()
    d.port_cmd({"cmd": "units", "tab": "length", "from": "m", "to": "km"})
    d.port_cmd({"cmd": "set", "field": "lengthInput", "value": "1000"})
    r, _ = timed_port(d, {"cmd": "units", "tab": "length", "to": "mi"})
    probe("stale-check", r.get("lengthResult") == "0.621371 mi",
          f"result after to-unit->mi = {r.get('lengthResult')!r} (want '0.621371 mi')",
          (time.time() - t0) * 1000)

    # P6 edge-input: non-numeric set must not kill the app
    r, ms = timed_port(d, {"cmd": "set", "field": "lengthInput", "value": "abc"})
    time.sleep(1.0)
    alive = d.pid() is not None
    probe("edge-input", alive and r.get("lengthResult") == "—",
          f"reply={r.get('lengthResult')!r} alive={alive}", ms)
    if not alive:
        d.launch(True)  # repair state so later probes are independent

    # P7 temp-latency: port round-trip on a temperature set stays interactive
    r, ms = timed_port(d, {"cmd": "set", "field": "tempInput", "value": "100"})
    probe("temp-latency", ms < 2000 and r.get("tempResult") == "212 °F",
          f"round-trip={ms:.0f}ms tempResult={r.get('tempResult')!r}", ms)

    # P8 persistence: distinctive state must survive a relaunch without reset
    d.port_cmd({"cmd": "set", "field": "lengthInput", "value": "777"})
    d.port_cmd({"cmd": "units", "tab": "length", "from": "ft", "to": "mi"})
    d.port_cmd({"cmd": "set", "field": "tempInput", "value": "25"})
    a, _ = timed_port(d, {"cmd": "state"})
    d.launch(False)
    b, _ = timed_port(d, {"cmd": "state"})
    probe("persistence", a and b == a, f"before={a} after={b}")

    # P9 canonical goldens: fixed state 1000 m->km, two window sizes, pixel diff
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

    finish(d, variant, front_before)


def finish(d, variant, front_before):
    d.stop()
    front_after = d.probe("front")
    results.append({"probe": "app-never-frontmost",
                    "pass": d.mf.bundle_id not in (front_before, front_after),
                    "detail": f"{front_before} -> {front_after}"})
    out = HERE / "data" / f"convert-{variant}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"variant": variant, "results": results}, indent=1))
    print(f"wrote {out}")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


if __name__ == "__main__":
    main()
