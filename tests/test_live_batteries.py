"""Live integration tests: run the deterministic batteries end-to-end.

Marked `live` — they need an unlocked macOS session with Accessibility and
Screen Recording permissions, and the fixture apps built at the manifests'
app_paths (see README quick start). Run with: pytest -m live
"""
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
