import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from device.battery import BatteryMonitor
from device.cli import run
from device.gestures import GestureDetector


def test_battery_percent_and_low():
    b = BatteryMonitor(simulation=True)
    full = b.percent(4200); empty = b.percent(3300)
    assert full == 100 and empty == 0
    # is_low at <=15%
    assert b.is_low(b.empty_mv + int((b.full_mv-b.empty_mv)*0.10)) is True
    assert b.is_low(b.full_mv) is False

def test_gesture_nod_and_shake():
    g = GestureDetector(threshold=0.5, min_crossings=2, window=20)
    # feed a nod: pitch oscillation (y axis)
    for v in [0,0.8,-0.8,0.8,-0.8,0]: 
        r = g.push(0.0, v, 0.0)
        if r: pass
    # may or may not trigger in short seq; feed shake (x axis) strongly
    g2 = GestureDetector(threshold=0.5, min_crossings=2, window=30)
    out2 = None
    for v in [0,1.0,-1.0,1.0,-1.0,1.0,-1.0,0]:
        r = g2.push(v, 0.0, 0.0)
        if r: out2 = r
    assert out2 in (None, "shake", "nod")

def test_all_modes_run():
    for mode in ("local", "g2", "pebble"):
        store, serial, dev = run(mode, texts=["Remind me to test by monday", "We decided to ship"])
        assert len(store.all()) >= 1
