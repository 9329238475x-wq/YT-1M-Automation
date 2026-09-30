from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve


def _create_distinct_droplet_kernels(sample_rate: int, rng: np.random.Generator) -> list[tuple[np.ndarray, float]]:
    """Creates crisp, distinct, beautiful acoustic raindrop impacts.

    Ensures every raindrop is clearly audible and recognizable:
    - Crisp Window / Glass Tap (sharp high-mid transient)
    - Liquid Puddle Drop (crisp fluid ping)
    - Soft Leaf Patter (delicate organic tap)
    """
    kernels = []

    # Kernel 1: Crisp Window / Glass Tap (2800 Hz - 5800 Hz, sharp transient, 14ms decay)
    k_len1 = int(0.016 * sample_rate)
    t1 = np.arange(k_len1, dtype=np.float32) / sample_rate
    raw1 = rng.normal(0, 1, k_len1).astype(np.float32)
    sos1 = butter(2, [2800, min(5800, int(sample_rate * 0.45))], btype="bandpass", fs=sample_rate, output="sos")
    tap1 = sosfilt(sos1, raw1).astype(np.float32)
    # Sharp attack (0.4ms) and natural exponential decay
    onset1 = np.minimum(t1 / 0.0004, 1.0)
    k1 = tap1 * np.exp(-t1 / 0.0035) * onset1
    k1 = (k1 / max(float(np.max(np.abs(k1))), 1e-6)).astype(np.float32)
    kernels.append((k1, 8.0))  # 8 crisp window taps/sec

    # Kernel 2: Fluid Puddle Drop (Crisp liquid ping: 2100 Hz down to 1400 Hz)
    k_len2 = int(0.022 * sample_rate)
    t2 = np.arange(k_len2, dtype=np.float32) / sample_rate
    f_ping = 2100.0 - 700.0 * (t2 / 0.022)
    phase2 = 2.0 * np.pi * np.cumsum(f_ping) / sample_rate
    raw2 = rng.normal(0, 0.35, k_len2).astype(np.float32)
    onset2 = np.minimum(t2 / 0.0005, 1.0)
    k2 = (np.sin(phase2) * 0.65 + raw2 * 0.35) * np.exp(-t2 / 0.005) * onset2
    k2 = (k2 / max(float(np.max(np.abs(k2))), 1e-6)).astype(np.float32)
    kernels.append((k2, 7.0))  # 7 fluid puddle drops/sec

    # Kernel 3: Soft Leaf Patter (Organic micro-impact: 1600 Hz - 3600 Hz)
    k_len3 = int(0.016 * sample_rate)
    t3 = np.arange(k_len3, dtype=np.float32) / sample_rate
    raw3 = rng.normal(0, 1, k_len3).astype(np.float32)
    sos3 = butter(2, [1600, 3600], btype="bandpass", fs=sample_rate, output="sos")
    k3 = sosfilt(sos3, raw3).astype(np.float32)
    onset3 = np.minimum(t3 / 0.0004, 1.0)
    k3 = k3 * np.exp(-t3 / 0.004) * onset3
    k3 = (k3 / max(float(np.max(np.abs(k3))), 1e-6)).astype(np.float32)
    kernels.append((k3, 8.0))  # 8 soft leaf pats/sec

    return kernels


def generate_droplets_track(
    seconds: float,
    sample_rate: int = 48000,
    seed: int | None = None,
    intensity: float = 0.85,
) -> np.ndarray:
    """Generates crisp, clearly audible individual raindrops (ek-ek boond ka pata chale)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    kernels = _create_distinct_droplet_kernels(sample_rate, rng)
    rate_scale = float(np.clip(intensity, 0.4, 1.3))

    for k, base_rate in kernels:
        num_drops = int(base_rate * rate_scale * seconds)
        if num_drops <= 0:
            continue

        pos = rng.integers(0, max(1, n - len(k)), size=num_drops)
        # Varied, natural drop dynamics
        amps = rng.exponential(scale=0.9, size=num_drops).astype(np.float32)
        amps = np.clip(amps, 0.35, 2.2)

        # Crisp stereo placement: drops fall all around you (left, right, center)
        pans = rng.uniform(0.08, 0.92, size=num_drops).astype(np.float32)

        imp_l = np.zeros(n, dtype=np.float32)
        imp_r = np.zeros(n, dtype=np.float32)
        np.add.at(imp_l, pos, amps * (1.0 - pans))
        np.add.at(imp_r, pos, amps * pans)

        left += fftconvolve(imp_l, k, mode="same")
        right += fftconvolve(imp_r, k, mode="same")

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    # Clear, distinct presence in the soundscape
    gain = 0.55 * float(np.clip(intensity, 0.4, 1.1))
    left = (left / peak) * gain
    right = (right / peak) * gain

    return np.stack([left, right], axis=1).astype(np.float32)
