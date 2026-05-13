"""BusytagDevice: serial I/O driver with flock, AT+UF/AT+SP ack, and retry.

See docs/serial-survival-guide.md for all the AT protocol traps handled here.
Lock path is /tmp/busytag-meter-serial.lock (distinct from private setup's lock).
"""
import fcntl
import os
import time
from typing import Optional

import serial

LOCK_PATH = "/tmp/busytag-meter-serial.lock"
SERIAL_BAUD = 115200


class DeviceError(Exception):
    pass


class BusytagDevice:
    def __init__(self, port: str):
        self._port = port
        self._ser: Optional[serial.Serial] = None
        self._lock_fd: Optional[int] = None

    def __enter__(self) -> "BusytagDevice":
        self._lock_fd = os.open(LOCK_PATH, os.O_CREAT | os.O_WRONLY)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self._lock_fd)
            self._lock_fd = None
            raise DeviceError("serial port locked by another process; skipping cycle")
        self._ser = serial.Serial(self._port, SERIAL_BAUD, timeout=2)
        time.sleep(0.5)
        self._drain()
        return self

    def __exit__(self, *_) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                os.close(self._lock_fd)
            except Exception:
                pass
            self._lock_fd = None

    def ping(self) -> bool:
        """Return True if device responds OK to AT."""
        self._drain()
        self._ser.write(b"AT\r\n")
        return self._wait_for(b"OK", timeout=2.0)

    def upload(self, filename: str, data: bytes) -> None:
        """Upload bytes to device flash as filename.

        Waits for full +evn:PP,0 / OK ack before returning (trap #1).
        Retries once on ack timeout after verifying device is still alive (trap #5).
        """
        for attempt in range(2):
            try:
                self._upload_once(filename, data)
                return
            except TimeoutError:
                if attempt == 0:
                    if not self.ping():
                        raise DeviceError("device not responding after ack timeout")
                    # small pause before retry
                    time.sleep(0.5)
                else:
                    raise

    def show(self, filename: str, pivot: str = "default.gif") -> None:
        """Display filename on device using force-reload via pivot.

        AT+SP with same filename is silently ignored (trap #3), so we first
        switch to pivot then back to target, waiting for +evn:SP each time (trap #2, #4).
        """
        self._ser.write(f"AT+SP={pivot}\r\n".encode())
        self._wait_for_sp_evn(pivot, timeout=3.0)
        self._ser.write(f"AT+SP={filename}\r\n".encode())
        self._wait_for_sp_evn(filename, timeout=3.0)

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _upload_once(self, filename: str, data: bytes) -> None:
        self._ser.write(f"AT+UF={filename},{len(data)}\r\n".encode())
        if not self._wait_for(b">", timeout=3.0):
            raise TimeoutError("no '>' prompt within 3s")
        self._ser.write(data)
        if not self._wait_for(b"OK", timeout=8.0):
            raise TimeoutError(f"no OK ack within 8s after uploading {filename}")

    def _wait_for(self, token: bytes, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            if self._ser.in_waiting:
                buf += self._ser.read(self._ser.in_waiting)
                if token in buf:
                    return True
            time.sleep(0.05)
        return False

    def _wait_for_sp_evn(self, name: str, timeout: float) -> bool:
        """Wait for +evn:SP,<name> frame-buffer-swap event (trap #2)."""
        token = f"+evn:SP,{name}".encode()
        return self._wait_for(token, timeout)

    def _drain(self) -> None:
        try:
            while self._ser and self._ser.in_waiting:
                self._ser.read(self._ser.in_waiting)
        except Exception:
            pass
