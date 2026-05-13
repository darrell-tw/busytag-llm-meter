"""Refresh loop: read sources → render → push to device."""
from __future__ import annotations

import time
from typing import Optional

from busytag_meter.display.renderer import render
from busytag_meter.sources.base import UsageSnapshot, UsageSource

USAGE_FILENAME = "usage.png"
DEFAULT_FILENAME = "default.gif"


def run_once(device, sources: list[UsageSource]) -> None:
    """One refresh cycle: read all sources, render, upload + show on device."""
    snapshots: list[Optional[UsageSnapshot]] = [s.read() for s in sources]
    stale_marker: dict[str, int] = {}
    for snap, src in zip(snapshots, sources):
        if snap is not None:
            stale_marker[snap.source] = src.stale_after_seconds()

    png_bytes = render(snapshots, stale_marker)
    device.upload(USAGE_FILENAME, png_bytes)
    device.show(USAGE_FILENAME, pivot=DEFAULT_FILENAME)


def run_forever(interval: int = 120) -> None:
    """Poll loop: find device, refresh every `interval` seconds.

    Re-discovers device port each iteration so a USB re-plug is self-healing.
    Holds the serial lock only during the active refresh, not between cycles.
    """
    from busytag_meter.device import DeviceError, DeviceNotFound, BusytagDevice, find_device
    from busytag_meter.sources.claude_code import ClaudeCodeSource
    from busytag_meter.sources.codex import CodexSource

    sources: list[UsageSource] = [ClaudeCodeSource(), CodexSource()]

    while True:
        try:
            port = find_device()
            with BusytagDevice(port) as dev:
                run_once(dev, sources)
        except DeviceNotFound as e:
            print(f"[busytag-meter] device not found: {e}")
        except DeviceError as e:
            print(f"[busytag-meter] device error: {e}")
        except Exception as e:
            print(f"[busytag-meter] unexpected error: {e}")
        time.sleep(interval)
