"""Energy-based Voice Activity Detection (VAD).

Simple VAD that determines if audio frames contain voice based on
energy (RMS) exceeding a configurable threshold.

Gate (CY-003):
  python3 tests/run_tests.py tests/test_*.py, make test, make proto
"""
from __future__ import annotations

import math
from typing import Optional


class EnergyVAD:
    """Energy-based Voice Activity Detection.

    Uses RMS (Root Mean Square) amplitude to detect voice activity.
    A frame is considered "active" if its energy exceeds the threshold.

    Attributes:
        threshold: Energy threshold (0.0 - 1.0). Higher = less sensitive.
        frame_size: Number of samples per frame for energy calculation.
        sample_rate: Audio sample rate in Hz.
    """

    def __init__(
        self,
        threshold: float = 0.01,
        frame_size: int = 1024,
        sample_rate: int = 16000,
    ) -> None:
        """Initialize VAD with given parameters.

        Args:
            threshold: Energy threshold between 0.0 and 1.0.
                Default 0.01 provides a good balance for 16kHz audio.
            frame_size: Number of audio samples per frame.
                Default 1024 at 16kHz = ~64ms frames.
            sample_rate: Audio sample rate in Hz. Default 16000.
        """
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0.0, 1.0]")
        if frame_size <= 0:
            raise ValueError("frame_size must be positive")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")

        self.threshold = threshold
        self.frame_size = frame_size
        self.sample_rate = sample_rate

    def is_active(self, audio_frame: bytes) -> bool:
        """Determine if an audio frame contains voice activity.

        Args:
            audio_frame: Raw audio bytes (16-bit PCM, mono, little-endian).

        Returns:
            True if the frame energy exceeds the threshold (voice activity).
        """
        if len(audio_frame) < self.frame_size * 2:
            # Frame too short; treat as inactive
            return False

        # Convert 16-bit PCM bytes to amplitude values
        # Use only the first frame_size samples
        n_samples = min(len(audio_frame) // 2, self.frame_size)
        total_energy = 0.0

        for i in range(n_samples):
            # Little-endian 16-bit signed integer
            sample = int.from_bytes(
                audio_frame[i * 2 : i * 2 + 2], "little", signed=True
            )
            # Normalize to [-1, 1]
            normalized = sample / 32768.0
            total_energy += normalized * normalized

        # Calculate RMS (Root Mean Square)
        rms = math.sqrt(total_energy / n_samples) if n_samples > 0 else 0.0

        # Energy threshold: frame is active if RMS > threshold
        return rms > self.threshold

    def process_frame(self, audio_frame: bytes) -> dict:
        """Process an audio frame and return VAD result.

        Args:
            audio_frame: Raw audio bytes (16-bit PCM, mono, little-endian).

        Returns:
            Dict with VAD analysis:
                - "active": bool — whether voice activity detected
                - "rms": float — root-mean-square energy (0.0 - 1.0)
                - "energy": float — raw energy (rms^2)
        """
        active = self.is_active(audio_frame)
        n_samples = min(len(audio_frame) // 2, self.frame_size)
        total_energy = 0.0

        if n_samples > 0:
            for i in range(n_samples):
                sample = int.from_bytes(
                    audio_frame[i * 2 : i * 2 + 2], "little", signed=True
                )
                normalized = sample / 32768.0
                total_energy += normalized * normalized
            rms = math.sqrt(total_energy / n_samples)
        else:
            rms = 0.0

        return {
            "active": active,
            "rms": rms,
            "energy": rms ** 2,
        }