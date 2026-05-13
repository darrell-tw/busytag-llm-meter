# Busy Tag Serial Survival Guide

Lessons learned from production deployment. None of this is in the official AT reference — consider this the missing appendix.

**Official reference:** [Busy Tag USB CDC command reference](https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide)

---

## Table of contents

1. [AT+UF: you must wait for the full ack before closing](#1-atuf-you-must-wait-for-the-full-ack-before-closing)
2. [AT+SP: OK ≠ frame updated](#2-atsp-ok--frame-updated)
3. [AT+SP with the same filename is silently ignored](#3-atsp-with-the-same-filename-is-silently-ignored)
4. [force-reload: sleep + flush is not good enough](#4-force-reload-sleep--flush-is-not-good-enough)
5. [Firmware occasionally drops an ack entirely](#5-firmware-occasionally-drops-an-ack-entirely)
6. [Concurrent writers will brick the device](#6-concurrent-writers-will-brick-the-device)
7. [When in doubt: checklist](#7-when-in-doubt-checklist)

---

## 1. AT+UF: you must wait for the full ack before closing

**Symptom.** After uploading a file the device becomes completely unresponsive — `AT` ping returns nothing. Recovery requires unplugging and re-plugging the USB cable.

**Root cause.** The `AT+UF` upload sequence is:

```
>>> AT+UF=filename,<size_in_bytes>
<<< >
>>> <raw binary data>
<<< +evn:PP,0\r\n\r\nOK\r\n
```

Closing the serial port before receiving `+evn:PP,0\r\nOK\r\n` interrupts the firmware's flash write mid-operation. The firmware state machine then hangs. A fixed `time.sleep()` after sending data is not safe — flash write time varies with file size and load.

**Solution.** Poll for the completion event:

```python
def upload_file(ser, name: str, data: bytes) -> None:
    ser.write(f"AT+UF={name},{len(data)}\r\n".encode())
    _wait_for_prompt(ser, b">", timeout=3.0)
    ser.write(data)
    _wait_for_response(ser, b"OK", timeout=8.0)  # 8s: allow for flash write
    # only now is it safe to proceed or close

def _wait_for_response(ser, token: bytes, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        buf += ser.read(ser.in_waiting or 1)
        if token in buf:
            return
    raise TimeoutError(f"no {token!r} within {timeout}s; buf={buf!r}")
```

---

## 2. AT+SP: OK ≠ frame updated

**Symptom.** `AT+SP=image.png` returns `OK` immediately, but the display still shows the previous image for an unpredictable amount of time.

**Root cause.** `OK` means the command was accepted. The actual frame buffer swap is asynchronous — the firmware sends a separate event when rendering is complete:

```
>>> AT+SP=image.png
<<< OK
<<< +evn:SP,image.png      ← frame buffer actually updated now
```

The gap between `OK` and `+evn:SP` can be hundreds of milliseconds for a GIF (firmware decodes the first frame). Code that proceeds after `OK` and immediately issues another `AT+SP` will race against the async render.

**Also:** `AT+SP=?` (query current image) returns `ERROR:2`. There is no way to ask the device which image is currently displayed — track it in your application layer.

**Solution.** Always wait for `+evn:SP,<filename>` before proceeding:

```python
def show_image(ser, name: str, timeout: float = 3.0) -> None:
    ser.write(f"AT+SP={name}\r\n".encode())
    _wait_for_sp_evn(ser, name, timeout)

def _wait_for_sp_evn(ser, name: str, timeout: float) -> None:
    token = f"+evn:SP,{name}".encode()
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        buf += ser.read(ser.in_waiting or 1)
        if token in buf:
            return
    raise TimeoutError(f"+evn:SP,{name} not received; buf={buf!r}")
```

---

## 3. AT+SP with the same filename is silently ignored

**Symptom.** You upload new content with `AT+UF=usage.png,...`, then call `AT+SP=usage.png`. The device returns `OK` but never sends `+evn:SP,usage.png`. The display stays frozen on whatever it showed before the upload.

**Root cause.** The firmware skips the frame buffer swap when the requested filename is the same as what is already displayed. It considers this a no-op. The `+evn:SP` event is not emitted.

**Solution.** Use a two-step "force-reload" via a pivot file (any file that is already on the device):

```python
def force_reload(ser, target: str, pivot: str = "default.gif") -> None:
    """Reload target even if it is already the currently displayed file."""
    show_image(ser, pivot)    # switch away — waits for +evn:SP,pivot
    show_image(ser, target)   # switch back  — waits for +evn:SP,target
```

Important: the pivot must be a file that actually exists on the device (e.g., the default startup image). The `show_image` call waits for `+evn:SP` as described in trap #2.

---

## 4. force-reload: sleep + flush is not good enough

**Symptom.** The two-step force-reload is implemented, logs show both `AT+SP` commands were sent and `OK` was received for each, but the display never actually changes. The frame hash cycles between a small set of stale values for hours.

**Root cause.** A common naive implementation looks like:

```python
# WRONG
ser.write(b"AT+SP=default.gif\r\n")
time.sleep(0.8)
ser.reset_input_buffer()   # flushes +evn:SP,default.gif away
ser.write(b"AT+SP=usage.png\r\n")
time.sleep(0.8)
ser.reset_input_buffer()
```

Two problems:
1. `0.8s` is not enough for the firmware to finish rendering the first frame of a GIF (async, varies).
2. `reset_input_buffer()` discards the `+evn:SP,default.gif` event before it is read — the application never confirms the first swap completed. The firmware receives the second `AT+SP` while still processing the first, enqueues both, then the second overwrites the first in the render queue before either frame actually renders.

**Solution.** Use the `_wait_for_sp_evn()` helper from trap #2 for each step. Never flush the buffer between the two `AT+SP` calls.

---

## 5. Firmware occasionally drops an ack entirely

**Symptom.** `AT+UF` completes sending the full binary payload, but `_wait_for_response()` times out with `buf=b''`. The device is not crashed — a bare `AT` ping still returns `OK`.

**Root cause.** Intermittent firmware state machine bug. Occurs roughly once every 20–50 uploads under launchd-driven periodic refresh. Not reproducible on demand.

**Solution.** Implement a single retry after an ack timeout:

```python
def upload_with_retry(ser, name: str, data: bytes) -> None:
    for attempt in range(2):
        try:
            upload_file(ser, name, data)
            return
        except TimeoutError:
            if attempt == 0:
                # confirm device is still alive before retrying
                _ping(ser)
            else:
                raise

def _ping(ser, timeout: float = 2.0) -> None:
    ser.write(b"AT\r\n")
    _wait_for_response(ser, b"OK", timeout)
```

Raise the ack timeout to 8 seconds before declaring failure — flash write time can spike under load.

---

## 6. Concurrent writers will brick the device

**Symptom.** Running two processes (or two threads) that each open the serial port independently causes the device to become unresponsive within seconds. Recovery requires a USB re-plug.

**Root cause.** The USB CDC serial port is not multiplexed. Interleaved `AT+UF` binary payloads corrupt the firmware's receive buffer and trigger the same state machine hang described in trap #1.

This is especially dangerous with:
- A launchd daemon running a periodic refresh every N seconds
- A Claude Code Stop hook that also tries to push content on every API call
- Any desktop application that holds the port in the background

**Solution.** Enforce a single writer at the OS level:

```python
import fcntl, os

LOCK_PATH = "/tmp/busytag-serial.lock"

def acquire_serial_lock() -> int:
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_WRONLY)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # raises BlockingIOError if locked
    return fd

def release_serial_lock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
```

All processes that open the serial port must acquire this lock first. If your hook or daemon cannot acquire the lock, skip the cycle — do not retry in a tight loop.

**Corollary:** close the Busy Tag desktop application before running any scripts that access the serial port directly.

---

## 7. When in doubt: checklist

Before writing any code that touches the serial port or a shared state file:

1. **How many writers exist?** List every process that can open the serial port or write the shared state file (daemons, hooks, CLI, desktop app). If more than one, you need `flock`.

2. **Is my ack complete?** For `AT+UF` — have you received `+evn:PP,0\r\nOK`? For `AT+SP` — have you received `+evn:SP,<filename>`? `OK` alone is not enough for either command.

3. **Is the filename the same as what is already displayed?** If yes, use `force_reload()` (trap #3). Do not assume `AT+SP` will work.

4. **Am I flushing the input buffer?** If yes, stop. Flushing discards ack events you need to read (trap #4).

5. **Did I handle the intermittent ack drop?** Add a single retry with a liveness ping after timeout (trap #5). Do not loop indefinitely.
