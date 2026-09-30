from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

# Audio asset search paths
def _get_asset_dirs() -> list[Path]:
    dirs = [
        Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/Assets"),
        Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/backend/assets/audio/thunder"),
        Path("C:/YT-1M-Automation/Assets"),
    ]
    here = Path(__file__).resolve()
    for parent in here.parents:
        dirs.append(parent / "Assets")
        dirs.append(parent / "assets" / "audio" / "thunder")
        dirs.append(parent / "backend" / "assets" / "audio" / "thunder")
    return [d for d in dirs if d.exists()]


# 3 Real Studio Thunder Assets (Auto-selected randomly)
THUNDER_ASSETS = [
    "universfield-peals-of-thunder-191992.mp3",
    "universfield-thunder-strike-124463.mp3",
    "universfield-loud-thunder-192165.mp3",
]


def _find_asset(filename: str) -> Path | None:
    for d in _get_asset_dirs():
        p = d / filename
        if p.exists():
            return p
    return None


def generate_peaceful_sleep_rain_bed(
    seconds: float,
    sr: int = 48000,
    seed: int = 701,
) -> np.ndarray:
    """Soft, smooth, continuous rain without harshness or hard surface effects.
    
    - Warm brown-pink spectral slope (1 / f^1.15) eliminates high sizzle.
    - Rich low/medium texture (180 - 950 Hz) creating an enveloping sleep cocoon.
    - Ultra-slow organic intensity drift (periods ~52s and ~76s) with subtle ±12% variation.
    - Scattered soft micro mist drops with zero sharp transients.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    # 1. Warm continuous rain bed
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    # Lowpass at 4800 Hz strips all high-frequency harshness
    sos_lp = butter(2, 4800.0, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 65.0, btype="highpass", fs=sr, output="sos")

    fl = sosfilt(sos_hp, sosfilt(sos_lp, raw_l)).astype(np.float32)
    fr = sosfilt(sos_hp, sosfilt(sos_lp, raw_r)).astype(np.float32)

    # Warm brown-pink spectral tilt (1 / f^0.58)
    fft_l = np.fft.rfft(fl)
    fft_r = np.fft.rfft(fr)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    freqs[0] = 1.0
    fft_l /= (freqs ** 0.58)
    fft_r /= (freqs ** 0.58)

    bed_l = np.fft.irfft(fft_l, n).astype(np.float32)
    bed_r = np.fft.irfft(fft_r, n).astype(np.float32)

    # Warm body resonance (180 - 850 Hz)
    sos_body = butter(2, [180.0, 850.0], btype="bandpass", fs=sr, output="sos")
    bed_l += sosfilt(sos_body, bed_l) * 0.35
    bed_r += sosfilt(sos_body, bed_r) * 0.35

    # Ultra-slow organic breathing drift (periods ~52s and ~76s)
    t = np.arange(n, dtype=np.float32) / sr
    drift = 1.0 + 0.08 * np.sin(2.0 * np.pi * (1.0 / 52.0) * t) + 0.05 * np.cos(2.0 * np.pi * (1.0 / 76.0) * t)
    bed_l *= drift
    bed_r *= drift

    # 2. Soft micro-droplet mist (gentle wet diffused texture, NO clicks)
    k_len = int(0.008 * sr)
    t_k = np.arange(k_len, dtype=np.float32) / sr
    raw_k = rng.normal(0, 1, k_len).astype(np.float32)
    sos_k = butter(2, [1200, 2600], btype="bandpass", fs=sr, output="sos")
    k = sosfilt(sos_k, raw_k).astype(np.float32) * np.exp(-t_k / 0.0032)
    k /= max(float(np.max(np.abs(k))), 1e-6)

    hits_count = int(35 * seconds)
    if hits_count > 0:
        pos = rng.integers(0, max(1, n - k_len), size=hits_count)
        amps = rng.exponential(scale=0.40, size=hits_count).astype(np.float32)
        amps = np.clip(amps, 0.10, 0.65)
        pans = rng.uniform(0.30, 0.70, size=hits_count).astype(np.float32)

        imp_l = np.zeros(n, dtype=np.float32)
        imp_r = np.zeros(n, dtype=np.float32)
        np.add.at(imp_l, pos, amps * (1.0 - pans))
        np.add.at(imp_r, pos, amps * pans)

        drops_l = fftconvolve(imp_l, k, mode="same")
        drops_r = fftconvolve(imp_r, k, mode="same")
    else:
        drops_l = np.zeros(n, dtype=np.float32)
        drops_r = np.zeros(n, dtype=np.float32)

    out_l = bed_l * 0.80 + drops_l * 0.20
    out_r = bed_r * 0.80 + drops_r * 0.20

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.65, out_r / peak * 0.65], axis=1).astype(np.float32)


def generate_rare_distant_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 702,
) -> np.ndarray:
    """Very rare and distant thunder rumble (360 Hz lowpass, long 2.2s fade-in, no sudden shock)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    # First event hits at 5.2s - 6.2s for prompt testing audition
    event_times = [float(rng.uniform(5.2, 6.2))]
    cur = event_times[0] + float(rng.uniform(50.0, 75.0))
    while cur < (seconds - 8.0):
        event_times.append(cur)
        cur += float(rng.uniform(55.0, 95.0))

    for ev in event_times:
        start_idx = int(ev * sr)
        if start_idx >= n:
            break

        chosen = THUNDER_ASSETS[rng.integers(0, len(THUNDER_ASSETS))]
        fpath = _find_asset(chosen)
        if not fpath or not fpath.exists():
            continue

        data, file_sr = sf.read(fpath)
        if data.ndim == 1:
            data = np.stack([data, data], axis=1)

        speed = float(rng.uniform(0.80, 0.86))
        eff_sr = file_sr * speed
        n_out = int(len(data) * sr / eff_sr)
        if n_out <= 0:
            continue

        idx = np.linspace(0, len(data) - 1, n_out)
        orig_idx = np.arange(len(data))
        left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
        right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

        # Ultra-distant horizon filter: 360 Hz lowpass
        sos_lp = butter(2, 360.0, btype="lowpass", fs=sr, output="sos")
        left = sosfilt(sos_lp, left).astype(np.float32)
        right = sosfilt(sos_lp, right).astype(np.float32)

        # Deep rolling sub-bass (32 - 110 Hz)
        sos_bass = butter(2, [32.0, 110.0], btype="bandpass", fs=sr, output="sos")
        left += sosfilt(sos_bass, left).astype(np.float32) * 0.85
        right += sosfilt(sos_bass, right).astype(np.float32) * 0.85

        # Very long 2.2s raised-cosine fade-in so there is ZERO sudden event
        fade_len = min(int(sr * 2.2), n_out // 3)
        if fade_len > 1:
            env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
            left[:fade_len] *= env
            right[:fade_len] *= env

        # Smooth 3.0s fade-out
        fade_out = min(int(sr * 3.0), n_out // 3)
        if fade_out > 1:
            env_out = (0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out) / fade_out))).astype(np.float32)
            left[-fade_out:] *= env_out
            right[-fade_out:] *= env_out

        pan = float(rng.uniform(0.35, 0.65))
        out_l = left * np.cos(pan * np.pi / 2.0)
        out_r = right * np.sin(pan * np.pi / 2.0)

        strike = np.stack([out_l, out_r], axis=1).astype(np.float32)
        peak = max(float(np.max(np.abs(strike))), 1e-6)
        # Soft and gentle (0.42 peak inside thunder track)
        strike = (strike / peak) * 0.42

        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.45:
        track = track / peak_total * 0.45
    return track


def generate_extremely_subtle_breeze(
    seconds: float,
    sr: int = 48000,
    seed: int = 703,
) -> np.ndarray:
    """Extremely subtle low-frequency background air movement (35 - 90 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos = butter(2, [35.0, 90.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos, raw_l).astype(np.float32)
    wr = sosfilt(sos, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod = 0.7 + 0.3 * (np.sin(2.0 * np.pi * (1.0 / 28.0) * t)**2)
    peak = max(float(np.max(np.abs(wl))), float(np.max(np.abs(wr))), 1e-6)
    return np.stack([(wl * mod / peak) * 0.05, (wr * mod / peak) * 0.05], axis=1).astype(np.float32)


def generate_peaceful_sleep_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int = 701,
    config: dict | None = None,
) -> Path:
    """Generates Sunday — Peaceful Rain for Deep Sleep soundscape:
    
    1. The most sleep-oriented and tranquil rain across the entire week.
    2. Very soft, smooth continuous rain (weight 0.75).
    3. Ultra-slow organic intensity drift (52s / 76s periods, no distracting pattern).
    4. Rare and ultra-distant cushioned thunder (weight 0.28).
    5. Extremely subtle background breeze (weight 0.05).
    6. Low stereo movement (subtle, coherent, centered immersion).
    7. Zero high-frequency harshness, rich low-mid warmth, deep hypnotic sleep audio.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    rain = generate_peaceful_sleep_rain_bed(seconds, sr, seed)
    thunder = generate_rare_distant_thunder(seconds, sr, seed + 1)
    breeze = generate_extremely_subtle_breeze(seconds, sr, seed + 2)

    length = min(len(rain), len(thunder), len(breeze))
    mix = (
        rain[:length] * 0.75 +
        thunder[:length] * 0.28 +
        breeze[:length] * 0.05
    )

    # Subtle coherent stereo field (no distracting panning, gently wrapping listener)
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    # Subtle side width (0.62) keeps it centered and non-distracting
    left_sleep = mid * 1.02 + side * 0.62
    right_sleep = mid * 1.02 - side * 0.62

    # Sub-bass warmth (35 - 120 Hz)
    sos_warm = butter(2, [35.0, 120.0], btype="bandpass", fs=sr, output="sos")
    left_sleep += sosfilt(sos_warm, left_sleep) * 0.24
    right_sleep += sosfilt(sos_warm, right_sleep) * 0.24

    # Velvet sleep silk ceiling (5400 Hz) - removes all high hiss/sizzle
    sos_silk = butter(1, 5400.0, btype="lowpass", fs=sr, output="sos")
    left_sleep = left_sleep * 0.78 + sosfilt(sos_silk, left_sleep) * 0.22
    right_sleep = right_sleep * 0.78 + sosfilt(sos_silk, right_sleep) * 0.22

    final_mix = np.stack([left_sleep, right_sleep], axis=1)

    # Analog tape saturation
    final_mix = np.tanh(final_mix * 1.12)

    # Master normalization (-1.3 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
