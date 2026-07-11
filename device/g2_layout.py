"""P0-C layout: map a Cyclops HUD model onto the EvenRealities G2 display.

The G2 is a 4-line x 18-char monochrome-green HUD (see premortem D7). This
module owns the *layout* — turning a HUD model (kind + lines + progress +
health) into the exact byte packets the G2 expects (control 0x01 + UTF-8,
<=18B each), reusing device.g2's `split_g2`. It is the missing half that lets
the desktop simulator (shells/hud_sim.py) and the wearable HUD model both
"render" on a real G2 without flashing hardware.

It pairs with the even_hub_sdk plugin in `g2-plugin/` (the renderer that runs
*inside* the G2 companion app and receives these packets over BLE).
"""

from __future__ import annotations

from device.g2 import G2_MAX_PAYLOAD, split_g2


def model_to_banner(
    kind: str, lines: list[str], progress=None, hr=None, spo2=None, batt=None
) -> str:
    """Flatten a HUD model into a G2-safe banner (each line <=18 chars)."""
    out: list[str] = []
    segs = []
    if kind and kind != "HOME":
        segs.append(kind[:5])
    if hr is not None:
        segs.append(f"H{hr}")
    if spo2 is not None:
        segs.append(f"S{spo2}")
    if batt is not None:
        segs.append(f"B{batt}")
    hdr = " ".join(segs)[:18]
    if hdr:
        out.append(hdr)
    for ln in (lines or [])[:3]:
        out.append(ln[:18])
    if progress is not None:
        out.append(f"[{progress}%]"[:18])
    out = out[:4]
    return "\n".join(out)


def render_to_g2(
    kind: str, lines: list[str], progress=None, hr=None, spo2=None, batt=None
) -> list[bytes]:
    """Produce the exact G2 BLE packet list for a HUD model.

    Each packet: 0x01 control byte + <=18B UTF-8. Mirrors what the G2 firmware
    draws, so the simulator and firmware agree on the wire.
    """
    banner = model_to_banner(kind, lines, progress, hr, spo2, batt)
    if not banner:
        from device.g2 import build_g2_packet

        return [build_g2_packet("")]  # blank screen packet
    return split_g2(banner)


def assert_g2_packets(pkts: list[bytes]):
    """Validation used by tests and the plugin: every packet is well-formed."""
    assert pkts, "no G2 packets"
    for p in pkts:
        assert p[0] == 0x01, f"missing control byte: {p!r}"
        assert 1 <= len(p) <= G2_MAX_PAYLOAD + 1, f"packet too long: {len(p)}B"
    return True
