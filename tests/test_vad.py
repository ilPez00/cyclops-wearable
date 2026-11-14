import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root
from brain.vad import EnergyVAD


def make_test_audio(energy_level: float, frame_size: int = 1024) -> bytes:
    """Create synthetic audio bytes with a given RMS energy level.

    Args:
        energy_level: Desired RMS energy (normalized 0.0 - 1.0).
        frame_size: Number of 16-bit samples in the frame.

    Returns:
        Raw 16-bit PCM bytes (mono, little-endian) with the specified energy.
    """
    # Generate samples with the desired RMS
    samples = []
    for i in range(frame_size):
        # Create a sine-like amplitude that gives the desired RMS
        # amplitude = energy_level * 32767 (max 16-bit)
        amplitude = int(energy_level * 32767)
        # Clamp to valid range
        amplitude = max(-32767, min(32767, amplitude))
        samples.append(struct.pack("<h", amplitude))

    # Return concatenated frames (just one frame)
    return b"".join(samples)


def test_vad_above_threshold():
    """VAD should detect voice above threshold."""
    vad = EnergyVAD(threshold=0.01, frame_size=1024)
    # Create audio with high energy (well above threshold)
    high_energy_audio = make_test_audio(energy_level=0.5)  # 50% of max
    result = vad.is_active(high_energy_audio)
    assert result is True, "VAD should detect high energy as active"


def test_vad_below_threshold():
    """VAD should not detect voice below threshold."""
    vad = EnergyVAD(threshold=0.1, frame_size=1024)
    # Create audio with low energy (well below threshold)
    low_energy_audio = make_test_audio(energy_level=0.001)  # 0.1% of max
    result = vad.is_active(low_energy_audio)
    assert result is False, "VAD should not detect low energy as active"


def test_vad_custom_threshold():
    """VAD should respect custom threshold setting."""
    vad = EnergyVAD(threshold=0.5, frame_size=1024)
    # Audio at 0.3 energy should be below threshold 0.5
    audio_03 = make_test_audio(energy_level=0.3)
    result = vad.is_active(audio_03)
    assert result is False, "Audio at 0.3 energy should be below threshold 0.5"

    # Audio at 0.7 energy should be above threshold 0.5
    audio_07 = make_test_audio(energy_level=0.7)
    result = vad.is_active(audio_07)
    assert result is True, "Audio at 0.7 energy should be above threshold 0.5"


def test_vad_short_frame():
    """VAD should handle frames shorter than frame_size."""
    vad = EnergyVAD(threshold=0.5, frame_size=1024)
    # Create a very short frame (only 1 sample)
    short_audio = struct.pack("<h", 32767)  # max amplitude, 1 sample
    result = vad.is_active(short_audio)
    # Short frames are treated as inactive
    assert result is False, "Short frames should be inactive"


def test_vad_empty_frame():
    """VAD should handle empty frames."""
    vad = EnergyVAD(threshold=0.5, frame_size=1024)
    result = vad.is_active(b"")
    assert result is False, "Empty frames should be inactive"


def test_vad_rmscalculation():
    """Test that RMS energy is calculated correctly for known values."""
    vad = EnergyVAD(threshold=0.5, frame_size=2)

    # Create audio with 2 samples at max amplitude (32767)
    # Each normalized sample = 32767/32768 ≈ 0.99997
    # RMS = sqrt((0.99997^2 + 0.99997^2)/2) ≈ sqrt(0.99994) ≈ 0.99997
    # This should be above threshold 0.5
    audio = struct.pack("<h", 32767) + struct.pack("<h", 32767)
    result = vad.process_frame(audio)
    assert result["active"] is True, "Frame with max amplitude should be active"
    assert result["rms"] > 0, "RMS should be greater than 0"
    assert 0.0 <= result["rms"] <= 1.0, "RMS should be in [0, 1]"
    # RMS should be close to 1.0 for max amplitude
    assert result["rms"] > 0.9, f"RMS for max amplitude should be > 0.9, got {result['rms']}"


def test_vad_process_frame_returns_dict():
    """Test that process_frame returns the expected dict structure."""
    vad = EnergyVAD(threshold=0.01, frame_size=1024)
    audio = make_test_audio(energy_level=0.5)
    result = vad.process_frame(audio)

    assert "active" in result, "result should contain 'active' key"
    assert "rms" in result, "result should contain 'rms' key"
    assert "energy" in result, "result should contain 'energy' key"
    assert isinstance(result["active"], bool), "'active' should be bool"
    assert isinstance(result["rms"], float), "'rms' should be float"
    assert isinstance(result["energy"], float), "'energy' should be float"
    assert 0.0 <= result["rms"] <= 1.0, "RMS should be in [0, 1]"
    assert result["energy"] == result["rms"] ** 2, "energy should be rms squared"


if __name__ == "__main__":
    # Run all tests
    import traceback

    tests = [
        test_vad_above_threshold,
        test_vad_below_threshold,
        test_vad_custom_threshold,
        test_vad_short_frame,
        test_vad_empty_frame,
        test_vad_rmscalculation,
        test_vad_process_frame_returns_dict,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)