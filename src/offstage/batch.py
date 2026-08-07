"""Step-list execution: many verbs, one process, one JSON result.

Per-verb CLI calls cost an agent one model turn each, and each turn re-pays
process start plus the app's launch/settle work. A batch is the same steps in
one process: the whole journey costs one turn.

The `expect` verb is what makes a batch self-judging — it asserts a JSON
pointer into ground truth (`/defaults/...`, the persisted store) or the port's
state (`/port/...`), so the result says pass/fail instead of handing the agent
a dump to interpret. Ground truth first: `/defaults` is the store, `/port` is
the app's own answer, and neither is an actuation echo.
"""
from __future__ import annotations

import json


class _Missing:
    def __repr__(self) -> str:
        return "<missing>"


MISSING = _Missing()


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer lookup. Returns MISSING for any path that does
    not exist (dotted keys like `notes.v1` are ordinary tokens, which is why
    pointers beat dotted paths here). `""` is the whole document."""
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"expect takes an RFC 6901 JSON pointer starting with '/', "
                         f"got {pointer!r}")
    cur = doc
    for tok in pointer.split("/")[1:]:
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            try:
                cur = cur[int(tok)]
            except (ValueError, IndexError):
                return MISSING
        elif isinstance(cur, dict):
            if tok not in cur:
                return MISSING
            cur = cur[tok]
        else:
            return MISSING
    return cur
