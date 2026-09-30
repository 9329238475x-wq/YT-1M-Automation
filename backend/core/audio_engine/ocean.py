from __future__ import annotations

"""Immersive procedural ocean sound synthesis.

Recreates the true open-air acoustics of sitting on an ocean beach:
- Deep sub-bass oceanic swell (30 - 80 Hz mass)
- Wide panoramic breaking waves sweeping across the horizon
- Delicate effervescent seafoam fizzing on wet sand (NO enclosed drain gurgling)
- Gentle coastal sea breeze
- Vast 3D open-air stereo immersion
"""

import numpy as np
from scipy.signal import butter, sosfilt


def _bandpass_noise(rng: np.random.Generator, n: int, sr: int, lo: float, hi: float) -> np.ndarray:
    """Filtered noise in an acoustic frequency band."""
    raw = rng.normal(0, 1, n).astype(np.float32)
    lo_safe = max(25.0, lo)
    hi_safe = min(float(sr) * 0.45, hi)
    if lo_safe >= hi_safe:
        hi_safe = lo_safe + 120.0
    sos = butter(2, [lo_safe, hi_safe], btype="bandpass", fs=sr, output="sos")
    out = sosfilt(sos, raw).astype(np.float32)
    out /= max(float(np.max(np.abs(out))), 1e-6)
    return out


def _lowpass_rumble(rng: np.random.Generator, n: int, sr: int, cutoff: float) -> np.ndarray:
    """Deep natural oceanic mass and undertow."""
    raw = np.cumsum(rng.normal(0, 1, n).astype(np.float32))
    raw -= np.mean(raw)
    raw /= max(float(np.max(np.abs(raw))), 1e-6)
    cutoff_safe = min(cutoff, float(sr) * 0.45)
    sos = butter(2, cutoff_safe, btype="lowpass", fs=sr, output="sos")
    out = sosfilt(sos, raw).astype(np.float32)
    out /= max(float(np.max(np.abs(out))), 1e-6)
    return out


def _synthesize_single_wave(
    n: int,
    sr: int,
    rng: np.random.Generator,
    wave_center: float,
    wave_size: float,
    pan_angle: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesize one complete natural beach wave: swell -> crest crash -> sand wash -> foam fizz."""
    t = np.arange(n, dtype=np.float32) / sr

    # Timing
    approach_dur = float(rng.uniform(2.8, 4.5)) * wave_size
    break_dur = float(rng.uniform(1.2, 2.2)) * wave_size
    wash_dur = float(rng.uniform(2.5, 4.0)) * wave_size

    t_approach = wave_center - approach_dur
    t_break = wave_center
    t_wash_start = wave_center + break_dur * 0.25

    # 1. DEEP OCEAN SWELL (30 Hz - 90 Hz): Massive volume of water rolling in
    approach_env = np.exp(-0.5 * ((t - wave_center) / max(approach_dur * 0.4, 0.5)) ** 2)
    approach_env *= 1.0 / (1.0 + np.exp(-np.clip((t - t_approach) * 2.8, -30, 30)))
    swell = approach_env * _lowpass_rumble(rng, n, sr, float(rng.uniform(70.0, 95.0))) * 0.38

    # 2. WAVE CREST CRASH (150 Hz - 3800 Hz): Wide broadband wave impact
    break_width = max(break_dur * 0.40, 0.4)
    break_env = np.exp(-0.5 * ((t - t_break) / break_width) ** 2)
    # Natural crest asymmetry
    break_env *= 1.0 + 0.4 * np.tanh((t - t_break) * (-2.0 / break_width))
    break_noise = _bandpass_noise(rng, n, sr, float(rng.uniform(140.0, 220.0)), float(rng.uniform(2800.0, 3800.0)))
    breaking = break_env * break_noise * float(rng.uniform(0.35, 0.50))

    # 3. SAND WASH & EFFERVESCENT FOAM (1800 Hz - 7000 Hz):
    # Delicate seafoam spreading and soaking into the beach (NO gurgling drain noise!)
    wash_peak = t_wash_start + wash_dur * 0.3
    wash_width = max(wash_dur * 0.4, 0.6)
    wash_env = np.exp(-0.5 * ((t - wash_peak) / wash_width) ** 2)
    wash_env *= np.exp(-np.maximum(t - wash_peak, 0) / max(wash_dur * 0.6, 0.8))
    foam_noise = _bandpass_noise(rng, n, sr, float(rng.uniform(1800.0, 2400.0)), float(rng.uniform(5500.0, 7200.0)))
    foam = wash_env * foam_noise * float(rng.uniform(0.18, 0.28))

    mono_wave = swell + breaking + foam

    # Panoramic stereo sweep across the beach (waves break across wide space)
    pan_drift = (t - wave_center) / max(wash_dur + break_dur, 2.0)
    pan_dyn = np.clip(pan_angle + 0.20 * pan_drift, 0.12, 0.88)

    left = mono_wave * np.cos(pan_dyn * np.pi / 2.0)
    right = mono_wave * np.sin(pan_dyn * np.pi / 2.0)
    return left, right


def generate_ocean(
    seconds: float,
    sample_rate: int = 48000,
    seed: int | None = None,
    audio_cfg: dict | None = None,
) -> np.ndarray:
    """Generates an open, expansive, realistic beach ocean soundscape."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n, dtype=np.float32) / sample_rate
    cfg = audio_cfg or {}
    layers_cfg = cfg.get("layers", {})

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    # ────────────────────────────────────────────────────────────
    # LAYER 1: Natural rolling beach waves (individual events)
    # ────────────────────────────────────────────────────────────
    wave_lo = float(cfg.get("wave_interval_seconds", {}).get("min", 7))
    wave_hi = float(cfg.get("wave_interval_seconds", {}).get("max", 14))

    pos = float(rng.uniform(1.2, 2.8))
    while pos < seconds - 2.5:
        interval = float(rng.uniform(wave_lo, wave_hi))
        wave_size = float(rng.uniform(0.75, 1.25))
        pan = float(rng.uniform(0.25, 0.75))

        wl, wr = _synthesize_single_wave(n, sample_rate, rng, pos, wave_size, pan)
        left += wl * float(layers_cfg.get("rolling_waves", 0.45))
        right += wr * float(layers_cfg.get("rolling_waves", 0.45))

        pos += interval

    # ────────────────────────────────────────────────────────────
    # LAYER 2: Deep ocean bed & undertow (30 Hz - 85 Hz)
    # ────────────────────────────────────────────────────────────
    deep_bed_l = _lowpass_rumble(rng, n, sample_rate, float(rng.uniform(70.0, 90.0)))
    deep_bed_r = _lowpass_rumble(rng, n, sample_rate, float(rng.uniform(70.0, 90.0)))
    # Slow 25-45 second ocean breath
    deep_swell = 0.80 + 0.20 * np.sin(2.0 * np.pi * 0.025 * t + float(rng.uniform(0, 6.28))).astype(np.float32)
    deep_level = float(layers_cfg.get("deep_surf", 0.28)) * 0.85
    left += deep_bed_l * deep_swell * deep_level
    right += deep_bed_r * deep_swell * deep_level

    # ────────────────────────────────────────────────────────────
    # LAYER 3: Distant open ocean ambient wash (160 Hz - 2400 Hz)
    # Soft background roar of distant ocean surf
    # ────────────────────────────────────────────────────────────
    raw_dist_l = rng.normal(0, 1, n).astype(np.float32)
    raw_dist_r = rng.normal(0, 1, n).astype(np.float32)
    sos_dist = butter(2, [150, 2200], btype="bandpass", fs=sample_rate, output="sos")
    dist_l = sosfilt(sos_dist, raw_dist_l).astype(np.float32)
    dist_r = sosfilt(sos_dist, raw_dist_r).astype(np.float32)

    fft_l = np.fft.rfft(dist_l)
    fft_r = np.fft.rfft(dist_r)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate)
    freqs[0] = 1.0
    fft_l /= np.sqrt(freqs)
    fft_r /= np.sqrt(freqs)
    dist_pink_l = np.fft.irfft(fft_l, n).astype(np.float32)
    dist_pink_r = np.fft.irfft(fft_r, n).astype(np.float32)
    dist_pink_l /= max(float(np.max(np.abs(dist_pink_l))), 1e-6)
    dist_pink_r /= max(float(np.max(np.abs(dist_pink_r))), 1e-6)

    dist_swell = 0.82 + 0.18 * np.sin(2.0 * np.pi * 0.05 * t + float(rng.uniform(0, 6.28))).astype(np.float32)
    dist_level = float(layers_cfg.get("shore_wash", 0.24)) * 0.55
    left += dist_pink_l * dist_swell * dist_level
    right += dist_pink_r * dist_swell * dist_level

    # ────────────────────────────────────────────────────────────
    # LAYER 4: Gentle coastal breeze (120 Hz - 800 Hz)
    # ────────────────────────────────────────────────────────────
    wind = _bandpass_noise(rng, n, sample_rate, 120.0, 750.0)
    wind_level = float(layers_cfg.get("distant_wind", 0.02)) * 0.8
    wind_swell = 0.6 + 0.4 * np.sin(2.0 * np.pi * 0.04 * t + float(rng.uniform(0, 6.28))).astype(np.float32)
    left += wind * wind_swell * wind_level
    right += wind * wind_swell * wind_level

    # ────────────────────────────────────────────────────────────
    # FINAL MIX: spacious analog warmth
    # ────────────────────────────────────────────────────────────
    stereo = np.stack([left, right], axis=1).astype(np.float32)
    stereo = np.tanh(stereo * 1.15) * 0.90
    peak = float(np.max(np.abs(stereo)))
    if peak > 0.94:
        stereo *= 0.94 / peak

    return stereo
