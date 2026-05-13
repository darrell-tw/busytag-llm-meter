"""Claude Code usage source.

Reads from /tmp/busytag-meter-usage.json (written by dump_from_stdin).
dump_from_stdin() is called by the Phase 2 Stop hook — Phase 1 reads whatever
the user has seeded via `python -m busytag_meter dump-claude-stdin`.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Optional

from busytag_meter.sources._shared_state import read_state, write_state
from busytag_meter.sources.base import UsageSnapshot, UsageSource

SOURCE_NAME = "claude_code"
STALE_SECONDS = 30 * 60  # 30 min


class ClaudeCodeSource(UsageSource):
    @property
    def name(self) -> str:
        return SOURCE_NAME

    def read(self) -> Optional[UsageSnapshot]:
        entry = read_state().get(SOURCE_NAME)
        if not entry:
            return None
        primary = entry.get("primary") or {}
        used = primary.get("used_percent")
        if used is None:
            return None
        secondary = entry.get("secondary") or {}
        return UsageSnapshot(
            source=SOURCE_NAME,
            primary_used_pct=float(used),
            primary_resets_at=primary.get("resets_at"),
            secondary_used_pct=float(secondary["used_percent"]) if secondary.get("used_percent") is not None else None,
            secondary_resets_at=secondary.get("resets_at"),
            plan_type=entry.get("plan_type"),
            ts=float(entry.get("ts") or time.time()),
        )

    def stale_after_seconds(self) -> int:
        return STALE_SECONDS


def dump_from_stdin() -> int:
    """Read Claude Code hook stdin JSON, extract rate_limits, write to shared state.

    Handles both the Claude Code Stop hook format and the statusline format.
    Called by Phase 2 hook; can also be run standalone for testing.
    """
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(f"[dump-claude-stdin] stdin parse failed: {e}", file=sys.stderr)
        return 1

    rl = data.get("rate_limits") or {}
    five_hour = rl.get("five_hour") or {}
    # Anthropic uses "used_percentage"; normalize to "used_percent" for shared state
    used = five_hour.get("used_percentage")
    resets_at = five_hour.get("resets_at")

    if used is None:
        return 0  # no rate_limits in this payload — silent skip

    entry = {
        "primary": {"used_percent": used, "resets_at": resets_at},
        "secondary": None,
        "plan_type": None,
        "ts": time.time(),
    }
    written = write_state(SOURCE_NAME, entry)
    if written:
        print(f"[dump-claude-stdin] wrote 5h={used}%", file=sys.stderr)
    return 0
