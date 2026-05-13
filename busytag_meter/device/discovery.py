"""Device discovery: scan /dev/cu.usbmodem* and AT-ping each candidate."""
from typing import Optional

import serial.tools.list_ports


class DeviceNotFound(Exception):
    pass


def find_device() -> str:
    """Return the first /dev/cu.usbmodem* port that answers AT with OK.

    Raises DeviceNotFound if zero or multiple responsive devices are found
    (multiple: ask user to specify port explicitly).
    """
    candidates = [
        p.device
        for p in serial.tools.list_ports.comports()
        if p.device.startswith("/dev/cu.usbmodem")
        or "BUSY TAG" in (p.description or "").upper()
    ]

    responsive: list[str] = []
    for port in candidates:
        if _ping_port(port):
            responsive.append(port)

    if len(responsive) == 1:
        return responsive[0]
    if len(responsive) == 0:
        raise DeviceNotFound(
            "No responsive Busy Tag device found. "
            "Check USB connection and ensure the desktop app is closed."
        )
    raise DeviceNotFound(
        f"Multiple responsive devices found: {responsive}. "
        "Specify port explicitly with --port."
    )


def _ping_port(port: str) -> bool:
    """Open port briefly, send AT, check for OK. Returns False on any error."""
    import time
    import serial

    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(0.3)
        # drain
        while ser.in_waiting:
            ser.read(ser.in_waiting)
        ser.write(b"AT\r\n")
        deadline = time.monotonic() + 1.5
        buf = b""
        while time.monotonic() < deadline:
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting)
                if b"OK" in buf:
                    ser.close()
                    return True
            time.sleep(0.05)
        ser.close()
        return False
    except Exception:
        return False
