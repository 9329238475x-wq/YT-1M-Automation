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


def generate_tin_roof_texture(
    seconds: float,
    sr: int = 48000,
    seed: int = 401,
) -> np.ndarray:
    """Main prominent tin/metal roof rain sound.

    - Mixes small crisp drops and big heavy drops with acoustic metallic resonance.
    - Periodic intensity surges: rain surges up (+35%) and returns to normal rhythm (22-30s cycle).
    - High-density cadence (~90 drops/sec) creating a continuous, satisfying white-noise blanket.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    # Kernel 1: Small crisp drops on tin (2600 - 4600 Hz, short 2.5ms decay)
    k1_len = int(0.008 * sr)
    t1 = np.arange(k1_len, dtype=np.float32) / sr
    raw1 = rng.normal(0, 1, k1_len).astype(np.float32)
    sos1 = butter(2, [2600, 4600], btype="bandpass", fs=sr, output="sos")
    k1 = sosfilt(sos1, raw1).astype(np.float32) * np.exp(-t1 / 0.0022)
    k1 /= max(float(np.max(np.abs(k1))), 1e-6)

    # Kernel 2: Big heavy drops with resonant metal ping (1100 - 2400 Hz, 4.8ms decay)
    k2_len = int(0.014 * sr)
    t2 = np.arange(k2_len, dtype=np.float32) / sr
    raw2 = rng.normal(0, 1, k2_len).astype(np.float32)
    sos2 = butter(2, [1100, 2400], btype="bandpass", fs=sr, output="sos")
    k2 = sosfilt(sos2, raw2).astype(np.float32) * np.exp(-t2 / 0.0042)
    k2 /= max(float(np.max(np.abs(k2))), 1e-6)

    # Kernel 3: Medium tin sheet impact (1700 - 3400 Hz, 3.2ms decay)
    k3_len = int(0.010 * sr)
    t3 = np.arange(k3_len, dtype=np.float32) / sr
    raw3 = rng.normal(0, 1, k3_len).astype(np.float32)
    sos3 = butter(2, [1700, 3400], btype="bandpass", fs=sr, output="sos")
    k3 = sosfilt(sos3, raw3).astype(np.float32) * np.exp(-t3 / 0.0030)
    k3 /= max(float(np.max(np.abs(k3))), 1e-6)

    # Dynamic intensity surge across the tin roof (period ~26s)
    t_arr = np.arange(n, dtype=np.float32) / sr
    surge_mod = 1.0 + 0.35 * (np.sin(2.0 * np.pi * (1.0 / 26.0) * t_arr)**2)

    # High density cadence: ~90 impacts per second across the tin roof!
    base_hits = int(90 * seconds)
    if base_hits <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    max_k = max(len(k1), len(k2), len(k3))
    pos = rng.integers(0, max(1, n - max_k), size=base_hits)
    amps = rng.exponential(scale=0.75, size=base_hits).astype(np.float32)
    amps = np.clip(amps, 0.20, 1.8)
    pans = rng.uniform(0.12, 0.88, size=base_hits).astype(np.float32)

    amps = amps * surge_mod[pos]

    # Partition drops: small (55%), medium (30%), big heavy drops (15%)
    rands = rng.random(base_hits)
    is_small = rands < 0.55
    is_big = rands > 0.85
    is_med = (~is_small) & (~is_big)

    imp1_l, imp1_r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
    imp2_l, imp2_r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
    imp3_l, imp3_r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)

    # Small drops
    np.add.at(imp1_l, pos[is_small], (amps * (1.0 - pans))[is_small])
    np.add.at(imp1_r, pos[is_small], (amps * pans)[is_small])
    # Big drops
    np.add.at(imp2_l, pos[is_big], (amps * 1.35 * (1.0 - pans))[is_big])
    np.add.at(imp2_r, pos[is_big], (amps * 1.35 * pans)[is_big])
    # Medium drops
    np.add.at(imp3_l, pos[is_med], (amps * 1.15 * (1.0 - pans))[is_med])
    np.add.at(imp3_r, pos[is_med], (amps * 1.15 * pans)[is_med])

    out_l = (
        fftconvolve(imp1_l, k1, mode="same") * 0.48 +
        fftconvolve(imp2_l, k2, mode="same") * 0.30 +
        fftconvolve(imp3_l, k3, mode="same") * 0.22
    )
    out_r = (
        fftconvolve(imp1_r, k1, mode="same") * 0.48 +
        fftconvolve(imp2_r, k2, mode="same") * 0.30 +
        fftconvolve(imp3_r, k3, mode="same") * 0.22
    )

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.90, out_r / peak * 0.90], axis=1).astype(np.float32)


def generate_subtle_outdoor_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 402,
) -> np.ndarray:
    """Soft background rainfall bed sitting quietly behind the tin roof sound."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, 4500.0, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 70.0, btype="highpass", fs=sr, output="sos")

    fl = sosfilt(sos_hp, sosfilt(sos_lp, raw_l)).astype(np.float32)
    fr = sosfilt(sos_hp, sosfilt(sos_lp, raw_r)).astype(np.float32)

    fft_l = np.fft.rfft(fl)
    fft_r = np.fft.rfft(fr)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    freqs[0] = 1.0
    fft_l /= np.sqrt(freqs)
    fft_r /= np.sqrt(freqs)

    bed_l = np.fft.irfft(fft_l, n).astype(np.float32)
    bed_r = np.fft.irfft(fft_r, n).astype(np.float32)

    peak = max(float(np.max(np.abs(bed_l))), float(np.max(np.abs(bed_r))), 1e-6)
    return np.stack([bed_l / peak * 0.50, bed_r / peak * 0.50], axis=1).astype(np.float32)


def generate_cushioned_distant_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 403,
) -> np.ndarray:
    """Very distant thunder cushioned behind the prominent tin roof sound (no sudden blast)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    # First thunder at 4.8s - 6.2s for prompt testing audition
    event_times = [float(rng.uniform(4.8, 6.2))]
    cur = event_times[0] + float(rng.uniform(26.0, 42.0))
    while cur < (seconds - 6.0):
        event_times.append(cur)
        cur += float(rng.uniform(30.0, 48.0))

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

        speed = float(rng.uniform(0.83, 0.89))
        eff_sr = file_sr * speed
        n_out = int(len(data) * sr / eff_sr)
        if n_out <= 0:
            continue

        idx = np.linspace(0, len(data) - 1, n_out)
        orig_idx = np.arange(len(data))
        left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
        right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

        # CUSHIONED FILTER: 520 Hz lowpass removes sharp claps and blasts, leaving deep rolling body
        sos_lp = butter(2, 520.0, btype="lowpass", fs=sr, output="sos")
        left = sosfilt(sos_lp, left).astype(np.float32)
        right = sosfilt(sos_lp, right).astype(np.float32)

        # Sub-bass rumble (38 - 180 Hz)
        sos_bass = butter(2, [38.0, 180.0], btype="bandpass", fs=sr, output="sos")
        left += sosfilt(sos_bass, left).astype(np.float32) * 0.85
        right += sosfilt(sos_bass, right).astype(np.float32) * 0.85

        # Long 1.4s raised-cosine fade-in so there is NO sudden blast
        fade_len = min(int(sr * 1.4), n_out // 3)
        if fade_len > 1:
            env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
            left[:fade_len] *= env
            right[:fade_len] *= env

        pan = float(rng.uniform(0.25, 0.75))
        out_l = left * np.cos(pan * np.pi / 2.0)
        out_r = right * np.sin(pan * np.pi / 2.0)

        strike = np.stack([out_l, out_r], axis=1).astype(np.float32)
        peak = max(float(np.max(np.abs(strike))), 1e-6)
        strike = (strike / peak) * 0.52

        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.58:
        track = track / peak_total * 0.58
    return track


def generate_subtle_breeze(
    seconds: float,
    sr: int = 48000,
    seed: int = 404,
) -> np.ndarray:
    """Very subtle ambient breeze (40 - 150 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos = butter(2, [40.0, 150.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos, raw_l).astype(np.float32)
    wr = sosfilt(sos, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod = 0.5 + 0.5 * (np.sin(2.0 * np.pi * (1.0 / 18.0) * t)**2)
    peak = max(float(np.max(np.abs(wl))), float(np.max(np.abs(wr))), 1e-6)
    return np.stack([(wl * mod / peak) * 0.10, (wr * mod / peak) * 0.10], axis=1).astype(np.float32)


def generate_tin_roof_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int = 401,
    config: dict | None = None,
) -> Path:
    """Generates Thursday — Heavy Rain on Tin Roof soundscape:

    1. Main prominent tin roof rain (small & big drops naturally mixed, weight 0.65).
    2. Periodic intensity surges on the roof (surges up and returns to normal rhythm).
    3. Soft background outdoor rain bed (weight 0.20).
    4. Gentle ambient breeze (weight 0.08).
    5. Distant thunder cushioned behind the roof sound (zero sudden blast, weight 0.48).
    6. Satisfying white-noise replacement for deep sleep and relaxation.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    roof = generate_tin_roof_texture(seconds, sr, seed)
    bed = generate_subtle_outdoor_rain(seconds, sr, seed + 1)
    thunder = generate_cushioned_distant_thunder(seconds, sr, seed + 2)
    breeze = generate_subtle_breeze(seconds, sr, seed + 3)

    # Tin Roof is the STAR LAYER (0.65)!
    length = min(len(roof), len(bed), len(thunder), len(breeze))
    mix = (
        roof[:length] * 0.65 +
        bed[:length] * 0.20 +
        thunder[:length] * 0.48 +
        breeze[:length] * 0.08
    )

    # 3D Overhead Immersion (rain on overhead metal ceiling)
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_3d = mid * 0.90 + side * 1.35
    right_3d = mid * 0.90 - side * 1.35

    # Sub-bass warmth (35 - 130 Hz)
    sos_warm = butter(2, [35.0, 130.0], btype="bandpass", fs=sr, output="sos")
    left_3d += sosfilt(sos_warm, left_3d) * 0.28
    right_3d += sosfilt(sos_warm, right_3d) * 0.28

    # Smooth silk high shield (7800 Hz) - preserves crisp tin texture while preventing fatigue
    sos_silk = butter(1, 7800.0, btype="lowpass", fs=sr, output="sos")
    left_3d = left_3d * 0.76 + sosfilt(sos_silk, left_3d) * 0.24
    right_3d = right_3d * 0.76 + sosfilt(sos_silk, right_3d) * 0.24

    final_mix = np.stack([left_3d, right_3d], axis=1)

    # Warm analog body thickening saturation (makes the rain sound rich and satisfying!)
    final_mix = np.tanh(final_mix * 1.8)

    # Master normalization (-1.4 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
