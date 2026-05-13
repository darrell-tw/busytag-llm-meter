"""Tests for the PNG renderer — verifies valid output without needing a device."""
import time

import pytest
from PIL import Image
import io

from busytag_meter.display.renderer import render
from busytag_meter.sources.base import UsageSnapshot


def _snapshot(source: str, used: float, resets_at: int = 0, ts: float = 0) -> UsageSnapshot:
    return UsageSnapshot(
        source=source,
        primary_used_pct=used,
        primary_resets_at=resets_at or int(time.time() + 3600),
        ts=ts or time.time(),
    )


def test_render_two_snapshots_produces_valid_png():
    """render() with two snapshots must return bytes loadable as a 240×280 PNG."""
    snaps = [
        _snapshot("claude_code", 28.0),
        _snapshot("codex", 35.0),
    ]
    stale_marker = {"claude_code": 1800, "codex": 1800}
    png_bytes = render(snaps, stale_marker)

    assert isinstance(png_bytes, bytes)
    assert len(png_bytes) > 0

    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (240, 280)


def test_render_with_none_snapshots_does_not_raise():
    """render() with all-None snapshots (idle state) must not raise."""
    png_bytes = render([None, None], {})
    assert isinstance(png_bytes, bytes)
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (240, 280)


def test_render_with_one_snapshot_one_none():
    """render() with mixed None/snapshot must produce valid PNG."""
    snaps = [_snapshot("claude_code", 75.0), None]
    png_bytes = render(snaps, {"claude_code": 1800})
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (240, 280)


def test_render_stale_snapshot():
    """Stale snapshot (ts far in the past) must not raise."""
    old_ts = time.time() - 3600  # 1 hour ago
    snaps = [_snapshot("claude_code", 50.0, ts=old_ts), None]
    png_bytes = render(snaps, {"claude_code": 1800})
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (240, 280)


def test_render_critical_usage_does_not_raise():
    """High usage (>80%) must still render without error."""
    snaps = [
        _snapshot("claude_code", 95.0),
        _snapshot("codex", 85.0),
    ]
    png_bytes = render(snaps, {"claude_code": 1800, "codex": 1800})
    img = Image.open(io.BytesIO(png_bytes))
    assert img.size == (240, 280)
