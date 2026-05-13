# Troubleshooting

> Placeholder — expand as bugs are reported.

## Device unresponsive / no AT ping reply

Symptom: `AT` command returns nothing; all subsequent commands time out.

Most likely causes:
1. Two processes wrote to the serial port simultaneously without a `flock`.
2. A file upload (`AT+UF`) was started but the port was closed before receiving `+evn:PP,0\r\nOK\r\n`.

Fix: unplug and re-plug the USB cable. Then ensure only one process holds the serial port at a time (see `docs/serial-survival-guide.md`).

## Display stuck on old content

The frame buffer is not refreshed even though new data was uploaded.

Cause: `AT+SP=<same_filename>` after `AT+UF` does not trigger a frame reload. See the "Same-filename no-reload" trap in `docs/serial-survival-guide.md`.

Fix: implement the two-step force-reload (`AT+SP=pivot → wait +evn:SP → AT+SP=target → wait +evn:SP`).

## Usage percentage frozen at old value

Symptom: display shows e.g. 24% even after the rate-limit window has reset.

Cause: an older session's snapshot (with an earlier `resets_at`) overwrote a newer session's data in the shared state file.

Fix: apply the `resets_at`-first max rule in the writer. See `docs/serial-survival-guide.md` — "Multi-writer state file deduplication".

## Port already in use

```
serial.serialutil.SerialException: [Errno 16] Resource busy: '/dev/tty.usbmodemXXXX'
```

The Busy Tag desktop app or another instance of `busytag-meter` is holding the port. Close the desktop app, or check for stale processes with `lsof | grep usbmodem`.
