"""Per-app manifest: the only place app-specific knowledge lives.

All harness verbs are generic; a manifest is data, not code. Relative paths
resolve against the manifest file's own directory.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DRIVER_VERBS = {"press", "menu", "port", "sleep"}


class ManifestError(ValueError):
    pass


@dataclass
class Golden:
    name: str
    size: str  # "WxH"
    file: Path

    @property
    def width(self) -> int:
        return int(self.size.lower().split("x")[0])

    @property
    def height(self) -> int:
        return int(self.size.lower().split("x")[1])


@dataclass
class Manifest:
    name: str
    bundle_id: str
    app_path: Path
    sock_path: str
    canonical_fixture: list[list[str]] = field(default_factory=list)
    goldens: list[Golden] = field(default_factory=list)
    golden_threshold_pct: float = 0.1
    launch_args: list[str] = field(default_factory=list)
    a11y_baseline: dict = field(default_factory=dict)
    path: Path | None = None  # where this manifest was loaded from

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        path = Path(path).resolve()
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ManifestError(f"{path}: not valid JSON: {e}") from e
        errors = validate(raw)
        if errors:
            raise ManifestError(f"{path}: " + "; ".join(errors))
        base = path.parent

        def rp(p: str) -> Path:
            q = Path(p)
            return q if q.is_absolute() else (base / q)

        return cls(
            name=raw["name"],
            bundle_id=raw["bundle_id"],
            app_path=rp(raw["app_path"]),
            sock_path=raw["sock_path"],
            canonical_fixture=[list(s) for s in raw.get("canonical_fixture", [])],
            goldens=[Golden(g["name"], g["size"], rp(g["file"]))
                     for g in raw.get("goldens", [])],
            golden_threshold_pct=float(raw.get("golden_threshold_pct", 0.1)),
            launch_args=list(raw.get("launch_args", [])),
            a11y_baseline=dict(raw.get("a11y_baseline", {})),
            path=path,
        )


def validate(raw: dict) -> list[str]:
    """Return a list of problems (empty = valid). Pure function for testing."""
    errors: list[str] = []
    if not isinstance(raw, dict):
        return ["manifest must be a JSON object"]
    for key in ("name", "bundle_id", "app_path", "sock_path"):
        if not isinstance(raw.get(key), str) or not raw.get(key):
            errors.append(f"missing or empty required string field '{key}'")
    fixture = raw.get("canonical_fixture", [])
    if not isinstance(fixture, list):
        errors.append("'canonical_fixture' must be a list of [verb, ...args] steps")
    else:
        for i, step in enumerate(fixture):
            if (not isinstance(step, list) or not step
                    or not all(isinstance(x, str) for x in step)):
                errors.append(f"canonical_fixture[{i}]: must be a non-empty list of strings")
            elif step[0] not in DRIVER_VERBS:
                errors.append(
                    f"canonical_fixture[{i}]: unknown verb '{step[0]}' "
                    f"(allowed: {sorted(DRIVER_VERBS)})")
            elif step[0] == "port":
                try:
                    json.loads(step[1])
                except (IndexError, json.JSONDecodeError):
                    errors.append(f"canonical_fixture[{i}]: port payload must be valid JSON")
            elif step[0] == "menu" and len(step) != 3:
                errors.append(f"canonical_fixture[{i}]: menu takes exactly <menu> <item>")
            elif step[0] == "press" and len(step) != 2:
                errors.append(f"canonical_fixture[{i}]: press takes exactly <identifier>")
    goldens = raw.get("goldens", [])
    if not isinstance(goldens, list):
        errors.append("'goldens' must be a list")
    else:
        for i, g in enumerate(goldens):
            if not isinstance(g, dict):
                errors.append(f"goldens[{i}]: must be an object")
                continue
            for key in ("name", "size", "file"):
                if not isinstance(g.get(key), str) or not g.get(key):
                    errors.append(f"goldens[{i}]: missing string field '{key}'")
            size = g.get("size", "")
            parts = size.lower().split("x")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                errors.append(f"goldens[{i}]: size must look like '1000x600', got '{size}'")
    thr = raw.get("golden_threshold_pct", 0.1)
    if not isinstance(thr, (int, float)) or thr < 0:
        errors.append("'golden_threshold_pct' must be a non-negative number")
    elif 0 < thr < 0.08:
        # First-run SCK noise band sits around 0.079% (measured); a
        # threshold inside it false-alarms on clean runs.
        errors.append(
            f"'golden_threshold_pct'={thr} is inside the measured first-run "
            "capture noise band (~0.08%); use >= 0.08 (0.1 recommended) or exactly 0")
    if "launch_args" in raw and (
            not isinstance(raw["launch_args"], list)
            or not all(isinstance(x, str) for x in raw["launch_args"])):
        errors.append("'launch_args' must be a list of strings")
    return errors
