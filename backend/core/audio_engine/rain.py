from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt


def _filtered_noise(rng: np.random.Generator, n: int, sr: int, low: float, high: float) -> np.ndarray:
    x = rng.normal(0, 1, n).astype(np.float32)
    sos = butter(4, [low, high], btype="bandpass", fs=sr, output="sos")
    return sosfilt(sos, x).astype(np.float32)


def generate_rain(seconds: float, sample_rate: int = 48000, seed: int | None = None, intensity: float = 0.85) -> np.ndarray:
    """Procedural rain bed. This is a foundation engine, not a sample library."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)

    soft = _filtered_noise(rng, n, sample_rate, 900, 6500) * 0.42
    medium = _filtered_noise(rng, n, sample_rate, 500, 8500) * 0.30
    heavy = _filtered_noise(rng, n, sample_rate, 180, 11000) * 0.28

    # Slow natural intensity movement without creating a repeating musical pattern.
    control_len = max(8, int(seconds * 8))
    control = rng.normal(0, 1, control_len).astype(np.float32)
    control = np.convolve(control, np.ones(17, dtype=np.float32) / 17, mode="same")
    control /= max(float(np.max(np.abs(control))), 1e-6)
    envelope = np.interp(np.linspace(0, control_len - 1, n), np.arange(control_len), control)
    envelope = 0.88 + 0.12 * envelope

    mono = (soft + medium + heavy) * envelope * float(np.clip(intensity, 0.0, 1.0))
    # Small independent stereo difference prevents a perfectly centered, synthetic bed.
    left = mono + _filtered_noise(rng, n, sample_rate, 2500, 9000) * 0.018
    right = mono + _filtered_noise(rng, n, sample_rate, 2300, 8800) * 0.018
    return np.stack([left, right], axis=1).astype(np.float32)
