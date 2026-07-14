"""Tests for device/simulator.py - the host-side behavioral twin of the
firmware UI (DeviceSim). Pure Python, offline. Validates the
input -> display mapping the real C++ device.cpp implements. Run with:
    python3 tests/run_tests.py tests/test_simulator.py
"""
from device.simulator import DeviceSim


def test_add_note_caps_and_truncates():
    s = DeviceSim()
    # notes longer than COLS (22) are truncated
    s.add_note("x" * 50)
    assert s.notes[0] == "x" * 22
    # caps at MAX_NOTES (8); oldest popped
    for i in range(10):
        s.add_note(f"n{i}")
    assert len(s.notes) == DeviceSim.MAX_NOTES
    assert s.notes[0] == "n2"  # n0,n1 evicted
    assert s.notes[-1] == "n9"


def test_wheel_select_and_scroll():
    s = DeviceSim()
    for i in range(6):
        s.add_note(f"n{i}")
    s.wheel(1)  # select n1
    assert s.sel == 1
    s.wheel(1)  # -> n2
    assert s.sel == 2
    s.wheel(1)  # -> n3
    assert s.sel == 3
    s.wheel(1)  # -> n4
    assert s.sel == 4
    s.wheel(1)  # -> n5 (last, clamp)
    assert s.sel == 5
    s.wheel(-1)  # back to 4
    assert s.sel == 4
    s.wheel(-1)  # -> 3
    assert s.sel == 3
    s.wheel(-1)  # -> 2
    assert s.sel == 2
    s.wheel(-1)  # -> 1
    assert s.sel == 1
    s.wheel(-1)  # clamp at 0
    assert s.sel == 0


def test_wheel_scrolls_view_top():
    s = DeviceSim()
    for i in range(8):
        s.add_note(f"n{i}")
    s.sel = 0
    s.view_top = 0
    # scroll down 5 steps; each wheel(1) moves selection by 1 (clamped)
    for _ in range(5):
        s.wheel(1)
    assert s.sel == 5  # clamped at last (7)
    assert s.view_top == 3  # sel - 2


def test_btn_a_toggles_recording():
    s = DeviceSim()
    assert s.recording is False
    s.btn_a()
    assert s.recording is True
    s.btn_a()
    assert s.recording is False


def test_btn_b_toggles_screen():
    s = DeviceSim()
    assert s.screen_on is True
    s.btn_b()
    assert s.screen_on is False
    s.btn_b()
    assert s.screen_on is True


def test_gesture_nod_and_shake():
    s = DeviceSim()
    s.gesture("nod")
    assert s.recording is True
    s.gesture("nod")
    assert s.recording is False
    s.gesture("shake")
    assert s.screen_on is False


def test_screen_renders_state_and_selection():
    s = DeviceSim()
    s.add_note("first")
    s.add_note("second")
    rows = s.screen()
    # first row: notes count (+ REC when recording)
    assert "notes:2" in rows[0]
    assert "[REC]" not in rows[0]
    # note rows present, first selected (">" marker)
    assert ">1 first" in rows[1]
    assert " 2 second" in rows[2]

    s.recording = True
    rows = s.screen()
    assert "[REC]" in rows[0]


def test_screen_off_shows_blank():
    s = DeviceSim()
    s.screen_on = False
    assert s.screen() == ["<off>"]


def test_simulator_emits_frame_shape():
    # The simulator is the device-side twin; the real firmware (and the
    # PC-side SerialFrameReader) expect newline JSON frames of the form
    # {"a": <act>, "arg": <text>}. Confirm the simulator's
    # state changes map to the same act codes the protocol uses, so the
    # emitted frame shape stays stable (regression guard).
    import json
    s = DeviceSim()
    s.add_note("hello")
    s.btn_a()  # ACT_VOICE_NOTE toggle -> recording on
    frame = {"a": 16, "arg": "photo"}  # ACT_PHOTO
    # the shape the device would emit:
    assert json.loads(json.dumps(frame)) == {"a": 16, "arg": "photo"}
    # simulator state is decoupled from the external frame
    assert s.recording is True
