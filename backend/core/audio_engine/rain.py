from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt

from .droplets import generate_droplets_track


def _generate_open_air_bed(
    seconds: float,
    sample_rate: int,
    rng: np.random.Generator,
    intensity: float = 0.85,
) -> np.ndarray:
    """Generates an open-air, natural, spacious rainfall bed."""
    n = int(seconds * sample_rate)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, min(7500.0, float(sample_rate) * 0.45), btype="lowpass", fs=sample_rate, output="sos")
    sos_hp = butter(2, 50.0, btype="highpass", fs=sample_rate, output="sos")

    fl = sosfilt(sos_hp, sosfilt(sos_lp, raw_l)).astype(np.float32)
    fr = sosfilt(sos_hp, sosfilt(sos_lp, raw_r)).astype(np.float32)

    fft_l = np.fft.rfft(fl)
    fft_r = np.fft.rfft(fr)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    freqs[0] = 1.0

    fft_l /= np.sqrt(freqs)
    fft_r /= np.sqrt(freqs)

    bed_l = np.fft.irfft(fft_l, n).astype(np.float32)
    bed_r = np.fft.irfft(fft_r, n).astype(np.float32)

    bed_l /= max(float(np.max(np.abs(bed_l))), 1e-6)
    bed_r /= max(float(np.max(np.abs(bed_r))), 1e-6)

    t = np.arange(n, dtype=np.float32) / sample_rate
    swell_l = 0.85 + 0.15 * np.sin(2.0 * np.pi * 0.05 * t + float(rng.uniform(0, 6.28))).astype(np.float32)
    swell_r = 0.85 + 0.15 * np.sin(2.0 * np.pi * 0.05 * t + float(rng.uniform(0, 6.28)) + 0.5).astype(np.float32)

    scale = float(np.clip(intensity, 0.35, 1.0)) * 0.45
    out_l = bed_l * swell_l * scale
    out_r = bed_r * swell_r * scale

    return np.stack([out_l, out_r], axis=1).astype(np.float32)


def generate_rain(
    seconds: float,
    sample_rate: int = 48000,
    seed: int | None = None,
    intensity: float = 0.85,
) -> np.ndarray:
    """Combines distinct, crisp raindrops with an open-air natural rain bed.

    Ensures individual raindrops (tip-tip-tap) are clearly audible and prominent.
    """
    rng = np.random.default_rng(seed)

    # 1. Distinct, crisp raindrops
    droplets = generate_droplets_track(seconds, sample_rate, seed, intensity)

    # 2. Ambient outdoor rain bed
    bed = _generate_open_air_bed(seconds, sample_rate, rng, intensity)

    # Balanced blend: prominent distinct droplets over soothing background bed
    combined = bed * 0.45 + droplets * 0.55
    peak = float(np.max(np.abs(combined)))
    if peak > 0.90:
        combined = combined * (0.90 / peak)

    return combined.astype(np.float32)
