# busytag-llm-meter

[繁體中文](README.zh-TW.md) | English

**Display your Claude Code & Codex rate limits on a [Busy Tag](https://busytag.com) USB device — in real time, on your desk.**

![CI](https://github.com/darrell-tw/busytag-llm-meter/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: alpha](https://img.shields.io/badge/status-alpha-orange)

> 📸 Demo GIF coming soon

---

## Hardware requirement

A [Busy Tag](https://busytag.com) USB device. It speaks USB CDC serial and accepts AT commands — no proprietary driver needed on macOS or Linux.

---

## Install

Not yet on PyPI. Install from source:

```bash
git clone https://github.com/darrell-tw/busytag-llm-meter
cd busytag-llm-meter
pip install -e .
```

---

## Data sources

| Source | How it works | Requires |
|--------|-------------|----------|
| **Claude Code** | Reads `/tmp/busytag-meter-usage.json` written by the Claude Code Stop hook | Claude Code CLI |
| **Codex** | Scans `~/.codex/sessions/**/rollout-*.jsonl` for the latest `token_count` event | Codex CLI |

### Set up the Claude Code hook

Add this to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python -m busytag_meter dump-claude-stdin"
          }
        ]
      }
    ]
  }
}
```

Verify it works:

```bash
echo '{"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":9999999999}}}' \
  | python -m busytag_meter dump-claude-stdin
busytag-meter status
```

---

## Usage

```bash
busytag-meter status        # print current usage JSON
busytag-meter poll-codex    # manually pull latest Codex session data
busytag-meter refresh       # one-shot render + push to device
busytag-meter daemon        # run refresh loop in foreground (every 120s)
```

Auto-start in background (adds a crontab entry, runs every 2 minutes):

```bash
busytag-meter install       # registers cron job + Claude Code hook
```

> ⚠️ `busytag-meter install` is not yet implemented — see [task-tracker.md](task-tracker.md).

---

## Current status

| Component | Status |
|-----------|--------|
| `sources/claude_code.py` | ✅ reads shared state, `dump_from_stdin()` works |
| `sources/codex.py` | ✅ scans `~/.codex/sessions/` JSONL |
| `device/` serial driver | ✅ AT+UF / AT+SP / AT+SC with force-reload pivot |
| `display/renderer.py` | ✅ Pillow 240×280 PNG, dual provider layout |
| `display/refresh.py` | ✅ hash-diff → skip upload if unchanged |
| `hooks/` | 🔴 stub |
| `installer/` | 🔴 stub — cron + settings.json merge not yet implemented |
| `busytag-meter install` | 🔴 not yet implemented |
| PyPI release | 🔴 pending |

---

## Architecture

```
Claude Code Stop hook
      │  (stdin JSON with rate_limits)
      ▼
python -m busytag_meter dump-claude-stdin
      │  writes /tmp/busytag-meter-usage.json
      ▼
sources/claude_code.py ──┐
                          ├──► display/renderer.py ──► device/serial_io.py ──► Busy Tag
sources/codex.py ────────┘     (Pillow 240×280)        (AT commands)
      ▲
~/.codex/sessions/**/rollout-*.jsonl
```

Key design decisions — read before touching these modules:

- **Single writer + `resets_at`-first dedup**: multiple concurrent Claude Code sessions each carry a stale snapshot. The newer `resets_at` block wins, not the higher `used_percentage`. Details in `sources/_shared_state.py`.
- **Force-reload pivot**: `AT+SP=same_filename` silently no-ops on Busy Tag firmware. The driver uploads to an alternate slot and pivots. Full trap list in `docs/serial-survival-guide.md`.
- **flock on serial**: only one process holds `/tmp/busytag-serial.lock` at a time.

File map:

```
busytag_meter/
  cli.py              — typer CLI entry point
  sources/
    _shared_state.py  — atomic read/write for /tmp/busytag-meter-usage.json
    base.py           — UsageSource ABC + UsageSnapshot dataclass
    claude_code.py    — ClaudeCodeSource + dump_from_stdin()
    codex.py          — CodexSource + poll_and_dump()
  display/
    renderer.py       — render_frame(claude, codex) → PNG bytes
    refresh.py        — run_once() / run_forever() orchestration
  device/
    discovery.py      — find_device() → serial port path
    serial_io.py      — BusytagDevice context manager (AT commands)
  hooks/              — stub (future home of hook scripts)
  installer/          — stub (future: cron + settings.json merger)
docs/
  serial-survival-guide.md  — AT protocol trap list
  architecture.md           — component overview
  adding-sources.md         — how to add a new usage source
```

---

## For AI assistants

If you are helping implement missing parts of this project, read this section first.

**Already implemented and tested:**
- `sources/claude_code.py` — `ClaudeCodeSource.read()` and `dump_from_stdin()`
- `sources/codex.py` — `CodexSource.read()` and `poll_and_dump()`
- `sources/_shared_state.py` — `read_state()` / `write_state()` with atomic tmp+mv and `resets_at`-first dedup
- `device/serial_io.py` — AT+UF upload, AT+SP display, AT+SC LED, force-reload pivot
- `display/renderer.py` — dual-provider 240×280 Pillow render
- `display/refresh.py` — hash-diff loop

**What needs to be built (priority order):**

1. **`installer/cron.py`** — read current crontab (`crontab -l`), append `*/2 * * * * /absolute/path/to/busytag-meter refresh`, write back (`crontab -`). Must be idempotent.
2. **`installer/settings_merger.py`** — merge the Stop hook entry into `~/.claude/settings.json` without destroying existing hooks. Use `json.load` / `json.dump`, never regex.
3. **`cli.py` `install` command** — call both installers, print ✅/❌ per step.
4. **`hooks/` standalone script** — a zero-dependency script usable as the hook command before `pip install`.

**Constraints:**
- Do not break the `resets_at`-first dedup in `_shared_state.py`.
- Cron entry must use the absolute path from `shutil.which("busytag-meter")`.
- All new code must pass `pytest tests/ -v` with Python 3.10+.
- Read `docs/serial-survival-guide.md` before any changes to `device/`.

---

## Acknowledgements

- [Busy Tag USB CDC command reference](https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide)
- [busytag_tool](https://github.com/acoster/busytag_tool) — community Python driver, original inspiration
- [busylight](https://github.com/JnyJny/busylight) — multi-device USB light library

## License

MIT © 2026 Darrell Wang
