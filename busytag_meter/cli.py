"""CLI entry point — typer app."""
from __future__ import annotations

import json
import sys

import typer

app = typer.Typer(help="Display Claude Code & Codex rate limits on your Busy Tag device.")


@app.command()
def daemon(interval: int = typer.Option(120, help="Refresh interval in seconds.")) -> None:
    """Run the refresh loop in foreground."""
    from busytag_meter.display.refresh import run_forever
    typer.echo(f"[busytag-meter] daemon starting (interval={interval}s) …")
    run_forever(interval=interval)


@app.command()
def refresh() -> None:
    """One-shot refresh: read sources, render, push to device."""
    from busytag_meter.device import BusytagDevice, DeviceNotFound, find_device
    from busytag_meter.display.refresh import run_once
    from busytag_meter.sources.claude_code import ClaudeCodeSource
    from busytag_meter.sources.codex import CodexSource

    try:
        port = find_device()
    except DeviceNotFound as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    sources = [ClaudeCodeSource(), CodexSource()]
    with BusytagDevice(port) as dev:
        run_once(dev, sources)
    typer.echo("[busytag-meter] refresh complete.")


@app.command()
def status() -> None:
    """Print current shared state JSON."""
    from busytag_meter.sources._shared_state import read_state
    state = read_state()
    typer.echo(json.dumps(state, indent=2))


@app.command("poll-codex")
def poll_codex() -> None:
    """Poll latest Codex rollout JSONL and dump to shared state."""
    from busytag_meter.sources.codex import poll_and_dump
    written = poll_and_dump()
    if written:
        typer.echo("[busytag-meter] codex state updated.")
    else:
        typer.echo("[busytag-meter] no new codex data (no sessions or already up-to-date).")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
