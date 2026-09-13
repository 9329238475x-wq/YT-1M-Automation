from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt


def generate_roof_rain(seconds: float, sample_rate: int = 48000, seed: int | None = None, level: float = 0.8) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    x = rng.normal(0, 1, n).astype(np.float32)
    sos = butter(3, [700, 9000], btype="bandpass", fs=sample_rate, output="sos")
    x = sosfilt(sos, x).astype(np.float32) * 0.22 * float(level)
    return np.stack([x, x], axis=1).astype(np.float32)
