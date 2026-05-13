# Architecture

> Placeholder — fill in once core modules are implemented.

## Planned component overview

```
sources/          # poll rate-limit data (Claude Code statusline, Codex API, …)
   └─ claude.py   # reads /tmp/claude-rate-limits.json (written by hook/statusline)
   └─ codex.py    # TODO

display/          # render PNG frames for the Busy Tag screen
   └─ renderer.py # Pillow-based 240×280 canvas

device/           # serial driver wrapping AT commands
   └─ serial.py   # AT+UF, AT+SP, AT+SC, force-reload logic

hooks/            # Claude Code Stop hook integration
   └─ dump.py     # write rate_limits to /tmp/claude-rate-limits.json

installer/        # launchd plist generation + install
   └─ launchd.py  # write + load com.busytag-llm-meter.plist

cli.py            # typer CLI tying it all together
```

## Data flow

```
Claude Code / Codex
      │  (rate_limits snapshot via Stop hook or statusline)
      ▼
/tmp/claude-rate-limits.json   ← single-writer, max() dedup
      │
      ▼
sources/claude.py  ──►  display/renderer.py  ──►  device/serial.py  ──►  Busy Tag
```

## Key design decisions

- **Single writer** for the shared state file — prevents null-clobber race.
- **force-reload via pivot file** — `AT+SP=same_filename` does not reload the frame buffer; a two-step `AT+SP=pivot → wait +evn:SP → AT+SP=target → wait +evn:SP` is required.
- **flock on serial port** — only one process touches the USB CDC serial at a time.
- See `docs/serial-survival-guide.md` for the full AT protocol trap list.
