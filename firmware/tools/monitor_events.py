#!/usr/bin/env python3
"""Raw-serial event monitor for the CyclUno controller (bringup tool).

Pairs with the `cycluno_debug` firmware build (-DDEBUG_INPUT), which prints one
plain-text line per input instead of the binary v2 frames:

    AXES <a0> <a1> <a2> <a3>     5 Hz raw ADC dump (J1x J1y J2x J2y)
    STEP joy1 +1 / -1            a joystick Y flick past the center-lock
    STEP joy2 +1 / -1
    BTN A press                  joystick-1 click
    BTN B press                  joystick-2 click

Flash it first:
    cd firmware && pio run -e cycluno_debug -t upload

Then run this:
    python3 firmware/tools/monitor_events.py            # auto-pick the port
    python3 firmware/tools/monitor_events.py --port /dev/ttyUSB0
    python3 firmware/tools/monitor_events.py --no-axes  # hide the 5 Hz dump

Move a stick / press a click and you should see events immediately. If AXES
never changes on a pin, that axis is mis-wired; if a click prints nothing, the
SW pin is wrong (should be D2 for A, D3 for B).
"""
from __future__ import annotations

import argparse
import glob
import sys
import time


def pick_port() -> str | None:
    for pat in ("/dev/ttyACM*", "/dev/ttyUSB*", "/dev/cu.usbmodem*", "/dev/cu.usbserial*"):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="CyclUno controller event monitor")
    ap.add_argument("--port", help="serial port (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--no-axes", action="store_true", help="hide AXES lines")
    args = ap.parse_args()

    try:
        import serial  # pyserial
    except ImportError:
        print("pyserial not installed. Install: pip install pyserial", file=sys.stderr)
        return 2

    port = args.port or pick_port()
    if not port:
        print("No serial port found (looked for ttyACM*/ttyUSB*/cu.usb*).\n"
              "Plug the Uno in, or pass --port.", file=sys.stderr)
        return 1

    try:
        ser = serial.Serial(port, args.baud, timeout=1)
    except Exception as e:  # noqa: BLE001 - report and exit cleanly
        print(f"Cannot open {port} @ {args.baud}: {e}", file=sys.stderr)
        return 1

    # ANSI colors when writing to a terminal.
    tty = sys.stdout.isatty()
    def c(code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if tty else s

    print(f"Listening on {port} @ {args.baud}. Move a stick / press a click. Ctrl-C to quit.")
    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("ascii", "replace").strip()
            if not line:
                continue
            if line.startswith("AXES"):
                if args.no_axes:
                    continue
                print(c("90", line))                      # dim
            elif line.startswith("STEP"):
                print(c("36", line))                       # cyan
            elif line.startswith("BTN"):
                print(c("32;1", f"{time.strftime('%H:%M:%S')}  {line}"))  # bright green
            else:
                print(line)                                # anything else (boot msgs)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
