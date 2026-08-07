#!/usr/bin/env python3
"""Per-verb CLI calls vs one `batch` call, on the same NotesApp journey.

Three costs matter, and they do not move together:
  * turns    — one CLI call is one agent turn; this is what batching removes;
  * tokens   — per-verb verification means reading an `observe` dump after
               every mutation, while `expect` answers pass/fail in a few bytes;
  * seconds  — process starts plus the driver's own work.

Usage: bench_batch.py [runs]   (default 3, reports the median)
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

# The journey both flows perform: two notes, renamed, one deleted via the menu.
MUTATIONS = [
    ["press", MANIFEST, "addNote"],
    ["press", MANIFEST, "addNote"],
    ["port", MANIFEST, '{"cmd":"rename","index":0,"title":"TOP"}'],
    ["port", MANIFEST, '{"cmd":"rename","index":1,"title":"BOTTOM"}'],
    ["menu", MANIFEST, "File", "Delete Note"],
]
BATCH_STEPS = [
    ["start"],
    ["press", "addNote"],
    ["expect", "/defaults/notes.v1/0/title", '"Untitled"'],
    ["press", "addNote"],
    ["port", '{"cmd":"rename","index":0,"title":"TOP"}'],
    ["port", '{"cmd":"rename","index":1,"title":"BOTTOM"}'],
    ["expect", "/port/titles", '["TOP","BOTTOM"]'],
    ["menu", "File", "Delete Note"],
    ["expect", "/defaults/notes.v1/0/title", '"BOTTOM"'],
    ["stop"],
]


def run(*args):
    return subprocess.run([OFFSTAGE, *args], capture_output=True, text=True).stdout


def flow_per_verb():
    """What an agent does today: one call per verb, and an `observe` after each
    mutation because that is the only way to verify it landed."""
    turns, chars = 0, 0
    out = run("start", MANIFEST)
    turns, chars = turns + 1, chars + len(out)
    for m in MUTATIONS:
        chars += len(run(*m))
        chars += len(run("observe", MANIFEST))
        turns += 2
    chars += len(run("stop", MANIFEST))
    return turns + 1, chars


def flow_batch():
    out = run("batch", MANIFEST, json.dumps(BATCH_STEPS))
    ok = json.loads(out)["ok"] if out.strip() else False
    if not ok:
        print("  WARN: batch reported failure", out[:300])
    return 1, len(out)


def main():
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    rows = {}
    for name, fn in (("per-verb", flow_per_verb), ("batch", flow_batch)):
        secs, turns, chars = [], 0, 0
        for _ in range(runs):
            t0 = time.time()
            turns, chars = fn()
            secs.append(time.time() - t0)
        rows[name] = {"turns": turns, "tokens": chars // 4,
                      "seconds": round(statistics.median(secs), 2)}
        print(f"  {name:9} turns={turns:3}  tokens~{chars // 4:6}  "
              f"median {rows[name]['seconds']}s")
    a, b = rows["per-verb"], rows["batch"]
    print(f"  batch is {a['turns'] / b['turns']:.0f}x fewer turns, "
          f"{a['tokens'] / max(b['tokens'], 1):.1f}x fewer tokens, "
          f"{a['seconds'] / max(b['seconds'], 0.01):.1f}x faster")
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "data" / "batch-vs-per-verb.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
