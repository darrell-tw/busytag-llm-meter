"""Shared state file I/O with max() v2 disambiguation.

State file: /tmp/busytag-meter-usage.json
Schema:
  {
    "claude_code": {
      "primary": {"used_percent": 28, "resets_at": 1779000000},
      "secondary": null,
      "plan_type": "max",
      "ts": 1778950000
    },
    "codex": {
      "primary": {"used_percent": 30, "resets_at": 1778597731},
      "secondary": {"used_percent": 5, "resets_at": 1779174459},
      "plan_type": "plus",
      "ts": 1778950500
    }
  }

max() v2 disambiguation (from private busytag four-round post-mortem):
  - new primary.resets_at > existing  → write   (new block)
  - new primary.resets_at == existing, new used_percent > existing → write (same block, usage grew)
  - new primary.resets_at < existing  → skip    (stale snapshot from older block)
  - existing is absent or resets_at missing → write
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

STATE_FILE = "/tmp/busytag-meter-usage.json"


def read_state() -> dict[str, Any]:
    """Return full state dict, or {} if file is absent/corrupt."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(source_name: str, entry: dict[str, Any]) -> bool:
    """Write entry for source_name into shared state, applying max() v2 disambiguation.

    entry must have at least {"primary": {"used_percent": N, "resets_at": T}, "ts": T}.
    Returns True if written, False if skipped.
    """
    new_primary = (entry.get("primary") or {})
    new_used = new_primary.get("used_percent")
    new_resets = new_primary.get("resets_at")

    if new_used is None:
        return False

    state = read_state()
    existing_entry = state.get(source_name) or {}
    ex_primary = (existing_entry.get("primary") or {})
    ex_used = ex_primary.get("used_percent")
    ex_resets = ex_primary.get("resets_at")

    if ex_resets is not None and new_resets is not None:
        if new_resets < ex_resets:
            return False
        if new_resets == ex_resets and ex_used is not None and new_used <= ex_used:
            return False

    state[source_name] = entry
    _atomic_write(state)
    return True


def _atomic_write(state: dict[str, Any]) -> None:
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE_FILE)
