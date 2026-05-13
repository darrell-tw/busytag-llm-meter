# busytag-llm-meter

**The first AI usage meter for Busy Tag — see your Claude Code & Codex rate limits glow on your desk in real time.**

Display your Claude Code and Codex API usage directly on a [Busy Tag](https://busytag.com) device, refreshed automatically in the background.

---

<!-- Demo GIF goes here -->
> 📸 Demo GIF coming soon

---

## Hardware requirement

A [Busy Tag](https://busytag.com) USB device. The device exposes a USB CDC serial port and accepts AT commands — no proprietary driver needed.

## Install

> **TODO** — package not yet published to PyPI.

```
pipx install busytag-llm-meter
```

## Quick start

> **TODO** — CLI not yet implemented. Steps below are planned.

1. Plug in your Busy Tag device.
2. Run `busytag-meter install` to set up the launchd background service.
3. Run `busytag-meter status` to verify data is flowing.

## Features

- **Claude Code usage display** — reads the 5-hour token rate-limit window and renders it as a progress bar on the device screen.
- **Codex usage display** — planned; same pipeline, different source.
- **Multi-writer safe** — concurrent Claude Code sessions each hold a partial snapshot; a `resets_at`-first max rule prevents stale data from overwriting fresh data.
- **launchd integration** — runs a background refresh loop on macOS without keeping a terminal open.
- **force-reload-aware** — works around the Busy Tag firmware quirk where `AT+SP=<same_filename>` silently no-ops; uses a two-step pivot to guarantee the frame buffer actually updates.
- **Stale indicator** — displays a "~N min ago" label when the data source has not been updated for 30+ minutes.

## Status

**alpha** — under active development. API and config format will change without notice.

## Contributing

Issues and PRs welcome. Before touching the serial driver, read `docs/serial-survival-guide.md` — it will save you several hours of debugging.

## Acknowledgements

- [Busy Tag USB CDC command reference](https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide) — official AT command reference
- [busytag_tool](https://github.com/acoster/busytag_tool) — community Python driver, original inspiration
- [busylight](https://github.com/JnyJny/busylight) — multi-device USB light library, useful reference for serial handling patterns

## License

MIT © 2026 Darrell Wang
