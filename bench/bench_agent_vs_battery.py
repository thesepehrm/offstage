#!/usr/bin/env python3
"""A screenshot agent vs an offstage battery, on the same NotesApp journey.

`bench_batch.py` compares two offstage flows against each other. This one
compares offstage against the thing it replaces: an agent that observes the
app through screenshots and acts through synthetic clicks, which means the app
must be frontmost and the machine belongs to the run.

The two arms are not symmetric and the report says so:

  offstage arm  — scripted, deterministic, no model in the loop. Scripted here
                  and timed by this file.
  agent arm     — a real model driving computer-use tools: screenshot, decide,
                  click, screenshot again to verify. Cannot be scripted from
                  inside this file, because the whole point is that a model is
                  the loop. Run it by the protocol below and record the result
                  with `record-agent`; wall clock is what a human sitting there
                  would measure, start of first screenshot to last verify.

The honest reading: the offstage arm is a fixed program and the agent arm is a
sample of a stochastic process. Run the agent arm at least 5 times, keep the
median, and report the failure count next to it. A run where the model clicks
the wrong row is a real cost of that approach, not an outlier to discard.

Usage:
  bench_agent_vs_battery.py offstage [runs]      # arm A, default 5, median
  bench_agent_vs_battery.py record-agent SECONDS [--turns N] [--tokens N]
                                                 [--failed]
  bench_agent_vs_battery.py report               # merge both arms, print table
  bench_agent_vs_battery.py protocol             # print the agent-arm script

Assumes NotesApp is built at the manifest's app_path.
"""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = str(HERE.parent / "examples" / "notesapp.manifest.json")
OFFSTAGE = str(HERE.parent / ".venv" / "bin" / "offstage")
DATA = HERE / "data"
AGENT_FILE = DATA / "agent-arm.json"
OUT_FILE = DATA / "agent-vs-battery.json"

# The journey, stated once in English so both arms provably do the same work.
JOURNEY = [
    "launch the app fresh (no leftover notes)",
    "add a note",
    "add a second note",
    "rename the first note to TOP",
    "rename the second note to BOTTOM",
    "verify the list reads TOP then BOTTOM",
    "delete a note from the File menu",
    "verify the remaining note is BOTTOM",
    "quit the app",
]

# Arm A: the same journey as one batch call. `expect` steps are the
# verifications; they read persisted state, not the actuation result.
BATCH_STEPS = [
    ["start"],
    ["press", "addNote"],
    ["press", "addNote"],
    ["port", '{"cmd":"rename","index":0,"title":"TOP"}'],
    ["port", '{"cmd":"rename","index":1,"title":"BOTTOM"}'],
    ["expect", "/port/titles", '["TOP","BOTTOM"]'],
    ["menu", "File", "Delete Note"],
    ["expect", "/defaults/notes.v1/0/title", '"BOTTOM"'],
    ["stop"],
]

PROTOCOL = """\
Agent-arm protocol (run this by hand, or hand it to a computer-use agent)

Give the agent exactly this task, with screenshot and click tools and no
offstage access:

    Open NotesApp (at {app}). Add two notes. Rename the first to TOP and the
    second to BOTTOM. Confirm the list shows TOP then BOTTOM. Delete a note
    using the File menu. Confirm the remaining note is BOTTOM. Quit the app.
    Verify each step from what you can see.

Rules that keep the comparison fair:
  * Reset first: `defaults delete {bundle}` so both arms start clean.
  * Wall clock runs from the agent's first screenshot to its last verification,
    not including your typing of the prompt.
  * Count a turn as one model round trip.
  * If the agent gets a step wrong and recovers, that time counts.
  * If it finishes with a wrong or unverified result, record it with --failed.
  * Do not touch the keyboard during the run. If you cannot avoid touching it,
    that is the finding, and it is the one this project is about.

Then record it:
    bench_agent_vs_battery.py record-agent 214 --turns 23 --tokens 41000
"""


def run(*args):
    return subprocess.run([OFFSTAGE, *args], capture_output=True, text=True).stdout


def arm_offstage(runs):
    secs, chars, failures = [], 0, 0
    for _ in range(runs):
        subprocess.run(["defaults", "delete", "com.example.offstage.NotesApp"],
                       capture_output=True)
        t0 = time.time()
        out = run("batch", MANIFEST, json.dumps(BATCH_STEPS))
        secs.append(time.time() - t0)
        chars = len(out)
        try:
            if not json.loads(out)["ok"]:
                failures += 1
        except (ValueError, KeyError):
            failures += 1
            print(f"  WARN: unparseable batch output {out[:200]}")
    return {"arm": "offstage battery", "turns": 1, "tokens": chars // 4,
            "seconds": round(statistics.median(secs), 2),
            "runs": runs, "failures": failures, "took_over_machine": False}


def cmd_record_agent(argv):
    seconds = float(argv[0])
    rec = {"arm": "screenshot agent", "seconds": seconds, "turns": None,
           "tokens": None, "runs": 1, "failures": 0, "took_over_machine": True}
    for i, a in enumerate(argv[1:]):
        if a == "--turns":
            rec["turns"] = int(argv[i + 2])
        elif a == "--tokens":
            rec["tokens"] = int(argv[i + 2])
        elif a == "--failed":
            rec["failures"] = 1
    DATA.mkdir(exist_ok=True)
    prior = json.loads(AGENT_FILE.read_text()) if AGENT_FILE.exists() else []
    prior.append(rec)
    AGENT_FILE.write_text(json.dumps(prior, indent=1))
    print(f"recorded run {len(prior)}: {seconds}s, "
          f"{'FAILED' if rec['failures'] else 'ok'}")
    return 0


def cmd_report():
    if not OUT_FILE.exists():
        print("no offstage arm yet: run `bench_agent_vs_battery.py offstage`")
        return 1
    a = json.loads(OUT_FILE.read_text())
    if not AGENT_FILE.exists():
        print("no agent arm yet: see `bench_agent_vs_battery.py protocol`")
        return 1
    runs = json.loads(AGENT_FILE.read_text())
    b = {"arm": "screenshot agent", "runs": len(runs),
         "seconds": round(statistics.median(r["seconds"] for r in runs), 2),
         "turns": _median_opt(runs, "turns"), "tokens": _median_opt(runs, "tokens"),
         "failures": sum(r["failures"] for r in runs), "took_over_machine": True}
    print(f"  {'arm':18} {'runs':>4} {'seconds':>8} {'turns':>6} {'tokens':>8} "
          f"{'failed':>7}  machine")
    for row in (b, a):
        print(f"  {row['arm']:18} {row['runs']:>4} {row['seconds']:>8} "
              f"{str(row['turns']):>6} {str(row['tokens']):>8} "
              f"{row['failures']:>7}  "
              f"{'taken over' if row['took_over_machine'] else 'yours'}")
    print(f"\n  offstage is {b['seconds'] / max(a['seconds'], 0.01):.0f}x faster "
          f"in wall clock on this journey, and does not take the machine.")
    (DATA / "agent-vs-battery-report.json").write_text(
        json.dumps({"agent": b, "offstage": a, "journey": JOURNEY}, indent=1))
    return 0


def _median_opt(runs, key):
    vals = [r[key] for r in runs if r.get(key) is not None]
    return round(statistics.median(vals)) if vals else None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "protocol":
        mf = json.loads(Path(MANIFEST).read_text())
        print(PROTOCOL.format(app=mf["app_path"], bundle=mf["bundle_id"]))
        return 0
    if cmd == "record-agent":
        return cmd_record_agent(sys.argv[2:])
    if cmd == "offstage":
        runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        row = arm_offstage(runs)
        DATA.mkdir(exist_ok=True)
        OUT_FILE.write_text(json.dumps(row, indent=1))
        print(f"  offstage battery: median {row['seconds']}s over {runs} runs, "
              f"{row['failures']} failures, ~{row['tokens']} tokens, 1 turn")
        return 0
    return cmd_report()


if __name__ == "__main__":
    sys.exit(main())
