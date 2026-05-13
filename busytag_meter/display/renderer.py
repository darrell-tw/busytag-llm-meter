"""240×280 PNG renderer for Busy Tag display.

Layout (two symmetric 140px rows, separated by a divider at y=140):
  Row 0 (y=0..139):   Claude Code — 5h primary rate limit
  Row 1 (y=140..279): Codex       — primary rate limit

Each row shows: label, used%, progress bar, resets-at countdown.
Stale rows (age > stale_after_sec) are shown in gray with "~Nm ago".
"""
from __future__ import annotations

import io
import time
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from busytag_meter.sources.base import UsageSnapshot

# Canvas
WIDTH, HEIGHT = 240, 280
ROW_HEIGHT = 140

# Colors
BG_COLOR = (0, 0, 0)
DIVIDER_COLOR = "#333333"
LABEL_COLOR = "#888888"
GRAY_COLOR = "#666666"
TICK_COLOR_NORMAL = "#76c5ff"   # Claude row uses #da7756; Codex uses #76c5ff
TICK_COLOR_WARN = "#ffaa44"
TICK_COLOR_CRIT = "#ff5555"

# Thresholds
WARN_PCT = 60
CRIT_PCT = 80

# TODO: vendor Noto Sans CJK subset in assets/fonts/ before Phase 3 public release
_FONT_PATHS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]

_font_cache: dict[int, ImageFont.FreeTypeFont] = {}


def _get_font(size: int) -> ImageFont.ImageFont:
    if size in _font_cache:
        return _font_cache[size]
    for path in _FONT_PATHS:
        try:
            f = ImageFont.truetype(path, size)
            _font_cache[size] = f
            return f
        except Exception:
            continue
    import warnings
    warnings.warn("No TrueType font found; using bitmap default — text quality will be poor", stacklevel=2)
    return ImageFont.load_default()


def _color_for(used_pct: float, stale: bool, base_color: str) -> str:
    if stale:
        return GRAY_COLOR
    if used_pct >= CRIT_PCT:
        return TICK_COLOR_CRIT
    if used_pct >= WARN_PCT:
        return TICK_COLOR_WARN
    return base_color


def _format_countdown(resets_at: Optional[int]) -> str:
    if not resets_at:
        return "— —"
    remain = int(resets_at - time.time())
    if remain <= 0:
        return "now"
    if remain < 60:
        return "<1m"
    h, m = divmod(remain // 60, 60)
    if h >= 24:
        d, h2 = divmod(h, 24)
        return f"{d}d {h2}h"
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _render_row(
    draw: ImageDraw.ImageDraw,
    y: int,
    snapshot: Optional[UsageSnapshot],
    age_sec: float,
    label: str,
    base_color: str,
    stale_after: int,
) -> None:
    """Render one 140px-high row for a source."""
    if snapshot is None:
        draw.text((120, y + 70), f"{label}\nidle", font=_get_font(18), fill=GRAY_COLOR, anchor="mm")
        return

    used = float(snapshot.primary_used_pct)
    resets_at = snapshot.primary_resets_at

    # If block has already reset, used is definitively 0 (Anthropic/OpenAI contract)
    if resets_at and resets_at < time.time():
        used = 0.0
        stale = False
    else:
        stale = age_sec > stale_after

    color = _color_for(used, stale, base_color)

    # Label row (top of block)
    draw.text((12, y + 10), label, font=_get_font(14), fill=LABEL_COLOR, anchor="lm")

    # Big percent
    draw.text((120, y + 62), f"{int(round(used))}%", font=_get_font(48), fill=color, anchor="mm")

    # Reset countdown (right-aligned, below big %)
    draw.text((228, y + 90), _format_countdown(resets_at), font=_get_font(14), fill="#cccccc", anchor="rm")
    draw.text((228, y + 108), "till reset", font=_get_font(11), fill=GRAY_COLOR, anchor="rm")

    # Progress bar
    bar_x, bar_y, bar_w, bar_h = 12, y + 118, 216, 8
    draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline="#333333", width=1)
    fill_w = int(bar_w * min(1.0, used / 100.0))
    if fill_w > 0:
        draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=color)

    # Stale age label
    if stale:
        age_min = int(age_sec // 60)
        stale_label = f"~{age_min}m ago" if age_min < 60 else f"~{age_min // 60}h ago"
        draw.text((228, y + 130), stale_label, font=_get_font(11), fill=GRAY_COLOR, anchor="rm")


def render(
    snapshots: list[Optional[UsageSnapshot]],
    stale_marker: dict[str, int],
) -> bytes:
    """Render 240×280 PNG from a list of up to 2 snapshots.

    snapshots: [claude_code_snapshot, codex_snapshot] (None = idle)
    stale_marker: {source_name: age_in_seconds}
    Returns raw PNG bytes.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    row_configs = [
        ("Claude", "#da7756"),  # Claude Code row
        ("Codex", "#76c5ff"),   # Codex row
    ]

    for i, (label, base_color) in enumerate(row_configs):
        snap = snapshots[i] if i < len(snapshots) else None
        age = stale_marker.get(snap.source if snap else "", 0)
        stale_after = snap.stale_after_seconds() if hasattr(snap, "stale_after_seconds") else 1800

        # Use stale_marker value as age; if snap has ts, compute from ts
        if snap is not None:
            age = int(time.time() - snap.ts)

        _render_row(
            draw,
            y=i * ROW_HEIGHT,
            snapshot=snap,
            age_sec=age,
            label=label,
            base_color=base_color,
            stale_after=stale_marker.get(snap.source if snap else "", 1800),
        )

    # Divider between rows
    draw.line([(12, ROW_HEIGHT), (228, ROW_HEIGHT)], fill=DIVIDER_COLOR, width=1)

    # Quantize for smaller PNG (~2KB on device)
    img = img.convert("P", palette=Image.ADAPTIVE, colors=64)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
