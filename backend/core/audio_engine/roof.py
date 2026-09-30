from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve


def generate_roof_rain(
    seconds: float,
    sample_rate: int = 48000,
    seed: int | None = None,
    level: float = 0.8,
) -> np.ndarray:
    """Generates warm, gentle acoustic rain patter on an overhead roof.

    Uses damped acoustic impulses (NO pure sine waves or hollow pipe rings)
    to create the cozy feeling of sitting safely indoors under roof tiles.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)

    # Kernel 1: Soft attic tile thud (muffled low-mid impulse: 350 - 1100 Hz)
    k_len1 = int(0.008 * sample_rate)
    t1 = np.arange(k_len1, dtype=np.float32) / sample_rate
    raw1 = rng.normal(0, 1, k_len1).astype(np.float32)
    sos1 = butter(2, [350, 1100], btype="bandpass", fs=sample_rate, output="sos")
    k1 = sosfilt(sos1, raw1).astype(np.float32) * np.exp(-t1 / 0.0025)
    k1 = (k1 / max(float(np.max(np.abs(k1))), 1e-6)).astype(np.float32)

    # Kernel 2: Gentle wooden patter (soft mid-frequency impact: 700 - 2000 Hz)
    k_len2 = int(0.006 * sample_rate)
    t2 = np.arange(k_len2, dtype=np.float32) / sample_rate
    raw2 = rng.normal(0, 1, k_len2).astype(np.float32)
    sos2 = butter(2, [700, 2000], btype="bandpass", fs=sample_rate, output="sos")
    k2 = sosfilt(sos2, raw2).astype(np.float32) * np.exp(-t2 / 0.0020)
    k2 = (k2 / max(float(np.max(np.abs(k2))), 1e-6)).astype(np.float32)

    # Relaxed natural cadence (28 hits/sec rather than harsh machine-gunning)
    drum_rate = int(28 * float(np.clip(level, 0.3, 1.2)))
    num_hits = int(drum_rate * seconds)
    if num_hits <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    max_k = max(len(k1), len(k2))
    pos = rng.integers(0, max(1, n - max_k), size=num_hits)
    amps = rng.exponential(scale=0.7, size=num_hits).astype(np.float32)
    amps = np.clip(amps, 0.2, 1.6)
    pans = rng.uniform(0.15, 0.85, size=num_hits).astype(np.float32)

    imp1_l = np.zeros(n, dtype=np.float32)
    imp1_r = np.zeros(n, dtype=np.float32)
    imp2_l = np.zeros(n, dtype=np.float32)
    imp2_r = np.zeros(n, dtype=np.float32)

    split = rng.random(num_hits) > 0.5
    np.add.at(imp1_l, pos[split], (amps * (1.0 - pans))[split])
    np.add.at(imp1_r, pos[split], (amps * pans)[split])
    np.add.at(imp2_l, pos[~split], (amps * (1.0 - pans))[~split])
    np.add.at(imp2_r, pos[~split], (amps * pans)[~split])

    left = fftconvolve(imp1_l, k1, mode="same") + fftconvolve(imp2_l, k2, mode="same")
    right = fftconvolve(imp1_r, k1, mode="same") + fftconvolve(imp2_r, k2, mode="same")

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    scale = 0.25 * float(np.clip(level, 0.2, 1.0))
    left = (left / peak) * scale
    right = (right / peak) * scale

    return np.stack([left, right], axis=1).astype(np.float32)
