"""Compile and locate the Swift probe binaries.

Probes are single-file Swift CLIs (AX, ScreenCaptureKit, CoreGraphics). They are
compiled once per source change into a cache directory and reused; `offstage
probes build` forces the build up front (recommended at install time).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROBE_NAMES = [
    "axdump", "axscan", "axpress", "axmenu", "axhas",
    "resize", "sckwin", "pixdiff", "sesslock", "front",
]

SRC_DIR = Path(__file__).resolve().parent / "probes"


def bin_dir() -> Path:
    d = os.environ.get("OFFSTAGE_BIN")
    if d:
        return Path(d)
    return Path.home() / ".cache" / "offstage" / "bin"


def _stamp(src: Path) -> str:
    return hashlib.sha256(src.read_bytes()).hexdigest()[:16]


def build(force: bool = False, quiet: bool = False) -> Path:
    """Compile any probe whose source changed. Returns the bin directory."""
    out = bin_dir()
    out.mkdir(parents=True, exist_ok=True)
    for name in PROBE_NAMES:
        src = SRC_DIR / f"{name}.swift"
        if not src.exists():
            raise FileNotFoundError(f"probe source missing: {src}")
        exe = out / name
        stamp_file = out / f".{name}.sha"
        stamp = _stamp(src)
        if not force and exe.exists() and stamp_file.exists() \
                and stamp_file.read_text() == stamp:
            continue
        if not quiet:
            print(f"compiling {name} ...", file=sys.stderr)
        r = subprocess.run(
            ["swiftc", "-O", "-o", str(exe), str(src)],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"swiftc failed for {name}:\n{r.stderr}")
        stamp_file.write_text(stamp)
    return out


def ensure() -> Path:
    """Build-if-needed and return the bin dir. Cheap when up to date."""
    return build(quiet=True)
