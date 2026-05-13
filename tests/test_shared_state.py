"""Tests for _shared_state.py max() v2 disambiguation — 5 required cases."""
import json
import os
import tempfile
import time
from unittest.mock import patch

import pytest

from busytag_meter.sources._shared_state import read_state, write_state


@pytest.fixture(autouse=True)
def tmp_state_file(tmp_path, monkeypatch):
    state_path = str(tmp_path / "busytag-meter-usage.json")
    monkeypatch.setattr("busytag_meter.sources._shared_state.STATE_FILE", state_path)
    yield state_path


def _make_entry(used: float, resets_at: int) -> dict:
    return {
        "primary": {"used_percent": used, "resets_at": resets_at},
        "secondary": None,
        "plan_type": None,
        "ts": time.time(),
    }


def test_empty_file_writes_new_value(tmp_state_file):
    """Case 1: state file absent → write new value."""
    assert not os.path.exists(tmp_state_file)
    written = write_state("claude_code", _make_entry(28.0, 1_779_000_000))
    assert written is True
    state = json.loads(open(tmp_state_file).read())
    assert state["claude_code"]["primary"]["used_percent"] == 28.0


def test_newer_resets_at_overwrites(tmp_state_file):
    """Case 2: new resets_at > existing → overwrite regardless of used_percent."""
    write_state("claude_code", _make_entry(50.0, 1_000_000_000))
    written = write_state("claude_code", _make_entry(10.0, 1_200_000_000))  # bigger resets_at, smaller used
    assert written is True
    state = read_state()
    assert state["claude_code"]["primary"]["resets_at"] == 1_200_000_000
    assert state["claude_code"]["primary"]["used_percent"] == 10.0


def test_older_resets_at_skipped(tmp_state_file):
    """Case 3: new resets_at < existing → skip (stale snapshot from older block)."""
    write_state("claude_code", _make_entry(50.0, 1_200_000_000))
    written = write_state("claude_code", _make_entry(90.0, 1_000_000_000))  # older block
    assert written is False
    state = read_state()
    assert state["claude_code"]["primary"]["resets_at"] == 1_200_000_000
    assert state["claude_code"]["primary"]["used_percent"] == 50.0


def test_same_resets_at_larger_used_overwrites(tmp_state_file):
    """Case 4: same resets_at, new used_percent > existing → overwrite (usage grew)."""
    write_state("claude_code", _make_entry(30.0, 1_200_000_000))
    written = write_state("claude_code", _make_entry(45.0, 1_200_000_000))
    assert written is True
    state = read_state()
    assert state["claude_code"]["primary"]["used_percent"] == 45.0


def test_same_resets_at_smaller_used_skipped(tmp_state_file):
    """Case 5: same resets_at, new used_percent <= existing → skip."""
    write_state("claude_code", _make_entry(45.0, 1_200_000_000))
    written = write_state("claude_code", _make_entry(20.0, 1_200_000_000))
    assert written is False
    state = read_state()
    assert state["claude_code"]["primary"]["used_percent"] == 45.0
