"""Codex usage source.

Polls ~/.codex/sessions/**/rollout-*.jsonl for the latest token_count event
with valid rate_limits.primary. Writes to /tmp/busytag-meter-usage.json.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from busytag_meter.sources._shared_state import read_state, write_state
from busytag_meter.sources.base import UsageSnapshot, UsageSource

SOURCE_NAME = "codex"
STALE_SECONDS = 30 * 60
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
SCAN_DAYS = 7
TAIL_BYTES = 65536  # read last 64KB per file — token_count events are near the end


class CodexSource(UsageSource):
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


def poll_and_dump() -> bool:
    """Scan Codex rollout JSONL files, write latest rate_limits to shared state.

    Returns True if new data was written, False otherwise.
    """
    result = _scan_codex_sessions()
    if result is None:
        return False

    ts_str, payload = result
    rl = payload.get("rate_limits") or {}
    primary = rl.get("primary") or {}
    secondary = rl.get("secondary")

    used = primary.get("used_percent")
    if used is None:
        return False

    entry = {
        "primary": {
            "used_percent": used,
            "resets_at": primary.get("resets_at"),
        },
        "secondary": {
            "used_percent": secondary["used_percent"],
            "resets_at": secondary.get("resets_at"),
        } if secondary and secondary.get("used_percent") is not None else None,
        "plan_type": rl.get("plan_type"),
        "ts": time.time(),
    }
    return write_state(SOURCE_NAME, entry)


def _scan_codex_sessions() -> Optional[tuple[str, dict]]:
    """Find the globally latest token_count payload across all recent JSONL files."""
    if not CODEX_SESSIONS_DIR.exists():
        return None

    cutoff = time.time() - SCAN_DAYS * 86400
    candidates = [
        p for p in CODEX_SESSIONS_DIR.glob("**/rollout-*.jsonl")
        if p.stat().st_mtime >= cutoff
    ]
    if not candidates:
        return None

    latest_ts = ""
    latest_payload = None

    for path in candidates:
        result = _latest_token_count_from_file(path)
        if result is None:
            continue
        ts, payload = result
        if ts > latest_ts:
            latest_ts = ts
            latest_payload = payload

    if latest_payload is None:
        return None
    return latest_ts, latest_payload


def _latest_token_count_from_file(path: Path) -> Optional[tuple[str, dict]]:
    """Return (timestamp_str, payload) for the last valid token_count in a file."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as fp:
            fp.seek(max(0, size - TAIL_BYTES))
            tail = fp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    for line in reversed(tail.splitlines()):
        if '"token_count"' not in line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        payload = d.get("payload") or {}
        if payload.get("type") != "token_count":
            continue
        # Skip events where rate_limits.primary is absent (quota-hit events)
        rl = payload.get("rate_limits") or {}
        primary = rl.get("primary") or {}
        if primary.get("used_percent") is None:
            continue
        return d.get("timestamp", ""), payload

    return None
