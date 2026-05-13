"""Tests for CodexSource poll_and_dump() using fixture JSONL."""
import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from busytag_meter.sources.codex import _latest_token_count_from_file, poll_and_dump
from busytag_meter.sources._shared_state import read_state

FIXTURE = Path(__file__).parent / "fixtures" / "rollout-sample.jsonl"


def test_latest_token_count_from_fixture():
    """Fixture should return the last token_count event (42.0% primary)."""
    result = _latest_token_count_from_file(FIXTURE)
    assert result is not None
    ts_str, payload = result
    assert ts_str == "2026-01-01T11:00:00.000Z"
    assert payload["type"] == "token_count"
    rl = payload["rate_limits"]
    assert rl["primary"]["used_percent"] == 42.0
    assert rl["primary"]["resets_at"] == 1735736400
    assert rl["secondary"]["used_percent"] == 10.5
    assert rl["plan_type"] == "plus"


def test_poll_and_dump_writes_to_shared_state(tmp_path, monkeypatch):
    """poll_and_dump should write codex entry to shared state."""
    state_path = str(tmp_path / "busytag-meter-usage.json")
    monkeypatch.setattr("busytag_meter.sources._shared_state.STATE_FILE", state_path)
    monkeypatch.setattr("busytag_meter.sources.codex.STATE_FILE", state_path, raising=False)

    # Point CODEX_SESSIONS_DIR at a temp dir containing our fixture
    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "01" / "01"
    session_dir.mkdir(parents=True)
    import shutil
    shutil.copy(FIXTURE, session_dir / "rollout-sample.jsonl")

    with patch("busytag_meter.sources.codex.CODEX_SESSIONS_DIR", tmp_path / ".codex" / "sessions"):
        written = poll_and_dump()

    assert written is True
    state = json.loads(open(state_path).read())
    assert "codex" in state
    assert state["codex"]["primary"]["used_percent"] == 42.0
    assert state["codex"]["secondary"]["used_percent"] == 10.5
    assert state["codex"]["plan_type"] == "plus"


def test_poll_and_dump_skips_stale_block(tmp_path, monkeypatch):
    """If state already has newer resets_at, poll_and_dump skips the write."""
    state_path = str(tmp_path / "busytag-meter-usage.json")
    monkeypatch.setattr("busytag_meter.sources._shared_state.STATE_FILE", state_path)
    monkeypatch.setattr("busytag_meter.sources.codex.STATE_FILE", state_path, raising=False)

    # Pre-populate state with a newer resets_at
    future_resets = 9_999_999_999
    existing = {
        "codex": {
            "primary": {"used_percent": 90.0, "resets_at": future_resets},
            "secondary": None,
            "plan_type": "plus",
            "ts": time.time(),
        }
    }
    with open(state_path, "w") as f:
        json.dump(existing, f)

    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "01" / "01"
    session_dir.mkdir(parents=True)
    import shutil
    shutil.copy(FIXTURE, session_dir / "rollout-sample.jsonl")

    with patch("busytag_meter.sources.codex.CODEX_SESSIONS_DIR", tmp_path / ".codex" / "sessions"):
        written = poll_and_dump()

    assert written is False
    state = json.loads(open(state_path).read())
    assert state["codex"]["primary"]["resets_at"] == future_resets
