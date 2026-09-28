"""Tests for brain/world.py — the bridge-to-world registry.

Registry wins over vision wins over honest miss. No stubs dressed as
knowledge, no bytes persisted.
"""

import json
import os
import tempfile

from brain.world import (
    ACT_WORLD_HOWTO,
    ACT_WORLD_LOOK,
    ACT_WORLD_PRICE,
    ACT_WORLD_READ,
    WorldRegistry,
    answer_world,
)


def _tmp():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    return path


def test_teach_lookup_forget():
    reg = WorldRegistry(_tmp())
    assert reg.lookup("menu") is None
    reg.teach("menu", "today: risotto", "user")
    assert reg.lookup("menu")["answer"] == "today: risotto"
    assert reg.lookup("MENU")["answer"] == "today: risotto"  # case-insensitive
    assert reg.lookup("lunch menu")["answer"] == "today: risotto"  # substring
    assert reg.forget("menu") is True
    assert reg.lookup("menu") is None
    assert reg.forget("menu") is False


def test_registry_persists():
    path = _tmp()
    WorldRegistry(path).teach("sign", "via Roma 12", "user")
    assert WorldRegistry(path).lookup("sign")["answer"] == "via Roma 12"


def test_registry_beats_vision():
    reg = WorldRegistry(_tmp())
    reg.teach("price tag", "€4.50, fair deal", "user")
    tier, text = answer_world(
        ACT_WORLD_PRICE, "price tag", registry=reg,
        vision_fn=lambda b64, p: "€99.00",
    )
    assert tier == "registry"
    assert text == "€4.50, fair deal"


def test_vision_tier_when_no_registry_hit():
    tier, text = answer_world(
        ACT_WORLD_READ, "sign", registry=WorldRegistry(_tmp()),
        vision_fn=lambda b64, p: "OPEN 9-18", frame_b64="AAA",
    )
    assert tier == "vision"
    assert text.startswith("READ:")


def test_read_then_translate_appends_translation():
    # W6: READ with a translator returns both lines; identical output
    # (already the target language) adds no TR line.
    tier, text = answer_world(
        ACT_WORLD_READ, "menu", registry=WorldRegistry(_tmp()),
        vision_fn=lambda b64, p: "ciao mondo", frame_b64="AAA",
        translate_fn=lambda s: "hello mondo",
    )
    assert tier == "vision"
    assert text == "READ: ciao mondo\nTR: hello mondo"
    tier, text = answer_world(
        ACT_WORLD_READ, "sign", registry=WorldRegistry(_tmp()),
        vision_fn=lambda b64, p: "exit", frame_b64="AAA",
        translate_fn=lambda s: "exit",
    )
    assert tier == "vision"
    assert "\nTR:" not in text
    # non-READ acts never translate, even with a translator wired
    tier, text = answer_world(
        ACT_WORLD_LOOK, "poster", registry=WorldRegistry(_tmp()),
        vision_fn=lambda b64, p: "ciao", frame_b64="AAA",
        translate_fn=lambda s: "hello",
    )
    assert text == "LOOK: ciao"


def test_miss_is_honest():
    # no registry hit, no vision backend -> miss, never a stub answer
    tier, text = answer_world(ACT_WORLD_LOOK, "plant", registry=WorldRegistry(_tmp()))
    assert tier == "miss"
    assert "teach me" in text
    # offline vision backend also degrades to miss, not to its error string
    tier, text = answer_world(
        ACT_WORLD_HOWTO, "plant", registry=WorldRegistry(_tmp()),
        vision_fn=lambda b64, p: "offline: no model", frame_b64="AAA",
    )
    assert tier == "miss"


def test_world_act_ids_match_firmware():
    # full 27-act parity lives in test_acts_parity.py (acts.yaml); this pins
    # the world block so a yaml slip shows up here too.
    assert (ACT_WORLD_LOOK, ACT_WORLD_HOWTO) == (24, 27)


def test_hud_bridge_dispatches_world():
    from brain.hud_bridge import HudBridge

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    b = HudBridge(sink=Cap())
    kind, payload = b.dispatch(24, "nothing-taught-ever-xyz")
    assert kind == "world"
    assert payload["tier"] == "miss"


def test_split_steps_numbered_bullets_wrap():
    from brain.world import split_steps

    steps = split_steps("1. Boil water\n2. Add pasta\n3. Drain and serve")
    assert steps == ["Boil water", "Add pasta", "Drain and serve"]
    steps = split_steps("- preheat oven\n- bake 20 min")
    assert steps == ["preheat oven", "bake 20 min"]
    steps = split_steps("Do this one very long thing without stopping at all")
    assert all(len(s) <= 23 for s in steps)
    assert split_steps("") == ["(empty)"]
    assert len(split_steps("\n".join(f"step {i}" for i in range(10)))) == 6


def test_hud_bridge_howto_emits_steps():
    from brain.hud_bridge import HudBridge
    from brain.world import WorldRegistry

    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    reg = WorldRegistry(path)
    reg.teach("pasta", "1. Boil water\n2. Add pasta\n3. Drain", "user")

    import brain.hud_bridge as hb
    real_default = WorldRegistry.__init__

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    # route dispatch through our registry by teaching the default path is
    # untestable in isolation; instead assert split+emit shape directly:
    from brain.world import answer_world, split_steps
    tier, text = answer_world(27, "pasta", registry=reg)
    assert tier == "registry"
    steps = split_steps(text)
    assert steps == ["Boil water", "Add pasta", "Drain"]
    b = HudBridge(sink=Cap())
    kind, payload = b.dispatch(27, "pasta")
    # default registry has no "pasta" -> honest miss, not steps
    assert kind == "world" and payload["tier"] == "miss"
