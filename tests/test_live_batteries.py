"""Live integration tests: run the deterministic batteries end-to-end.

Marked `live` — they need an unlocked macOS session with Accessibility and
Screen Recording permissions, and the fixture apps built at the manifests'
app_paths (see README quick start). Run with: pytest -m live
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench"


def _run(script, *args):
    return subprocess.run([sys.executable, str(BENCH / script), *args],
                          capture_output=True, text=True, timeout=600)


@pytest.mark.live
def test_battery_notes_clean():
    r = _run("battery_notes.py", "pytest-live")
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.live
def test_battery_convert_clean():
    r = _run("battery_convert.py", "pytest-live")
    assert r.returncode == 0, r.stdout + r.stderr


MANIFEST = str(BENCH.parent / "examples" / "notesapp.manifest.json")


def _batch(steps):
    return subprocess.run([sys.executable, "-m", "offstage.cli", "batch", MANIFEST,
                           json.dumps(steps)], capture_output=True, text=True, timeout=300)


@pytest.mark.live
def test_batch_journey_passes_against_ground_truth():
    r = _batch([["start"],
                ["press", "addNote"],
                ["expect", "/defaults/notes.v1/0/title", '"Untitled"'],
                ["port", '{"cmd":"rename","index":0,"title":"TOP"}'],
                ["expect", "/port/titles", '["TOP"]'],
                ["expect", "/defaults/notes.v1/0/title", '"TOP"'],
                ["stop"]])
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["ok"] is True


@pytest.mark.live
def test_batch_stops_at_the_first_failing_expect():
    r = _batch([["start"],
                ["expect", "/defaults/notes.v1/0/title", '"NeverThis"'],
                ["press", "addNote"]])
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert out["ok"] is False and out["failed_step"] == 1
    assert len(out["steps"]) == 2  # the press after the failure never ran
