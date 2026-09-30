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


def generate_muffled_outdoor_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 601,
) -> np.ndarray:
    """Soft muffled outdoor rain heard through closed car windows and insulated doors."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    # Automotive acoustic glass insulation: cuts highs above 3200 Hz
    sos_lp = butter(2, 3200.0, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 75.0, btype="highpass", fs=sr, output="sos")

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

    # Very slow gentle breathing modulation (period ~24s)
    t = np.arange(n, dtype=np.float32) / sr
    mod = 0.88 + 0.12 * (np.sin(2.0 * np.pi * (1.0 / 24.0) * t)**2)
    bed_l *= mod
    bed_r *= mod

    peak = max(float(np.max(np.abs(bed_l))), float(np.max(np.abs(bed_r))), 1e-6)
    return np.stack([bed_l / peak * 0.45, bed_r / peak * 0.45], axis=1).astype(np.float32)


def generate_car_body_drops(
    seconds: float,
    sr: int = 48000,
    seed: int = 602,
) -> np.ndarray:
    """Subtle rain texture on car windshield and upholstered roof.
    
    - Soft windshield trickle/ticks (1800 - 3200 Hz).
    - Padded roof taps (850 - 1900 Hz, damped thud of drops hitting headliner).
    - No sudden loud drops: tightly controlled organic envelope.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    # Kernel 1: Windshield glass drops (1800 - 3200 Hz, short 2.5ms decay)
    k1_len = int(0.007 * sr)
    t1 = np.arange(k1_len, dtype=np.float32) / sr
    raw1 = rng.normal(0, 1, k1_len).astype(np.float32)
    sos1 = butter(2, [1800, 3200], btype="bandpass", fs=sr, output="sos")
    k1 = sosfilt(sos1, raw1).astype(np.float32) * np.exp(-t1 / 0.0022)
    k1 /= max(float(np.max(np.abs(k1))), 1e-6)

    # Kernel 2: Insulated upholstered roof tap (850 - 1900 Hz, damped 3.8ms decay)
    k2_len = int(0.010 * sr)
    t2 = np.arange(k2_len, dtype=np.float32) / sr
    raw2 = rng.normal(0, 1, k2_len).astype(np.float32)
    sos2 = butter(2, [850, 1900], btype="bandpass", fs=sr, output="sos")
    k2 = sosfilt(sos2, raw2).astype(np.float32) * np.exp(-t2 / 0.0034)
    k2 /= max(float(np.max(np.abs(k2))), 1e-6)

    base_hits = int(48 * seconds)
    if base_hits <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    max_k = max(len(k1), len(k2))
    pos = rng.integers(0, max(1, n - max_k), size=base_hits)
    # Strictly controlled amplitude - NO sudden loud spikes!
    amps = rng.exponential(scale=0.50, size=base_hits).astype(np.float32)
    amps = np.clip(amps, 0.15, 0.85)
    pans = rng.uniform(0.20, 0.80, size=base_hits).astype(np.float32)

    # 60% windshield, 40% padded roof
    is_glass = rng.random(base_hits) < 0.60

    imp1_l, imp1_r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)
    imp2_l, imp2_r = np.zeros(n, dtype=np.float32), np.zeros(n, dtype=np.float32)

    np.add.at(imp1_l, pos[is_glass], (amps * (1.0 - pans))[is_glass])
    np.add.at(imp1_r, pos[is_glass], (amps * pans)[is_glass])

    np.add.at(imp2_l, pos[~is_glass], (amps * 0.90 * (1.0 - pans))[~is_glass])
    np.add.at(imp2_r, pos[~is_glass], (amps * 0.90 * pans)[~is_glass])

    out_l = fftconvolve(imp1_l, k1, mode="same") * 0.55 + fftconvolve(imp2_l, k2, mode="same") * 0.45
    out_r = fftconvolve(imp1_r, k1, mode="same") * 0.55 + fftconvolve(imp2_r, k2, mode="same") * 0.45

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.70, out_r / peak * 0.70], axis=1).astype(np.float32)


def generate_distant_car_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 603,
) -> np.ndarray:
    """Distant thunder heard outside closed car windows.
    
    - Muffled through automotive glass (420 Hz lowpass).
    - Deep sub-bass rumble (35 - 120 Hz).
    - Smooth 1.6s fade-in (no sudden strikes).
    - First thunder at 4.8s - 6.2s for prompt test audition.
    - Long peaceful gaps (35s - 60s).
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    event_times = [float(rng.uniform(4.8, 6.2))]
    cur = event_times[0] + float(rng.uniform(32.0, 52.0))
    while cur < (seconds - 6.0):
        event_times.append(cur)
        cur += float(rng.uniform(35.0, 60.0))

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

        speed = float(rng.uniform(0.82, 0.88))
        eff_sr = file_sr * speed
        n_out = int(len(data) * sr / eff_sr)
        if n_out <= 0:
            continue

        idx = np.linspace(0, len(data) - 1, n_out)
        orig_idx = np.arange(len(data))
        left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
        right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

        # Muffled automotive insulation filter: 420 Hz lowpass
        sos_lp = butter(2, 420.0, btype="lowpass", fs=sr, output="sos")
        left = sosfilt(sos_lp, left).astype(np.float32)
        right = sosfilt(sos_lp, right).astype(np.float32)

        # Deep sub-bass resonance (35 - 120 Hz)
        sos_bass = butter(2, [35.0, 120.0], btype="bandpass", fs=sr, output="sos")
        left += sosfilt(sos_bass, left).astype(np.float32) * 0.85
        right += sosfilt(sos_bass, right).astype(np.float32) * 0.85

        # Smooth 1.6s fade-in so there is NO sudden clap or scare
        fade_len = min(int(sr * 1.6), n_out // 3)
        if fade_len > 1:
            env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
            left[:fade_len] *= env
            right[:fade_len] *= env

        # Smooth tail fade-out
        fade_out = min(int(sr * 2.0), n_out // 3)
        if fade_out > 1:
            env_out = (0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out) / fade_out))).astype(np.float32)
            left[-fade_out:] *= env_out
            right[-fade_out:] *= env_out

        pan = float(rng.uniform(0.30, 0.70))
        out_l = left * np.cos(pan * np.pi / 2.0)
        out_r = right * np.sin(pan * np.pi / 2.0)

        strike = np.stack([out_l, out_r], axis=1).astype(np.float32)
        peak = max(float(np.max(np.abs(strike))), 1e-6)
        strike = (strike / peak) * 0.48

        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.52:
        track = track / peak_total * 0.52
    return track


def generate_subtle_outside_wind(
    seconds: float,
    sr: int = 48000,
    seed: int = 604,
) -> np.ndarray:
    """Very subtle low-frequency air movement outside closed car windows."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos = butter(2, [35.0, 110.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos, raw_l).astype(np.float32)
    wr = sosfilt(sos, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod = 0.6 + 0.4 * (np.sin(2.0 * np.pi * (1.0 / 22.0) * t)**2)
    peak = max(float(np.max(np.abs(wl))), float(np.max(np.abs(wr))), 1e-6)
    return np.stack([(wl * mod / peak) * 0.08, (wr * mod / peak) * 0.08], axis=1).astype(np.float32)


def generate_car_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int = 601,
    config: dict | None = None,
) -> Path:
    """Generates Saturday — Cozy Car Rain soundscape:
    
    1. Soft muffled outdoor rain through closed windows (weight 0.58).
    2. Subtle windshield & upholstered roof patter (weight 0.36).
    3. Distant muffled thunder outside the car windows (weight 0.42).
    4. Very subtle outside breeze (weight 0.07).
    5. Intimate enclosed car cabin acoustic space (not overly wide).
    6. Extremely cozy, peaceful, sleep-friendly.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    bed = generate_muffled_outdoor_rain(seconds, sr, seed)
    drops = generate_car_body_drops(seconds, sr, seed + 1)
    thunder = generate_distant_car_thunder(seconds, sr, seed + 2)
    wind = generate_subtle_outside_wind(seconds, sr, seed + 3)

    length = min(len(bed), len(drops), len(thunder), len(wind))
    mix = (
        bed[:length] * 0.52 +
        drops[:length] * 0.38 +
        thunder[:length] * 0.42 +
        wind[:length] * 0.08
    )

    # Intimate enclosed cabin imaging (focused, close, not excessively wide!)
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    # Cozy enclosed interior: side * 0.72 keeps it intimate inside the car
    left_car = mid * 1.06 + side * 0.72
    right_car = mid * 1.06 - side * 0.72

    # Car cabin interior cavity warmth (120 - 280 Hz)
    sos_warm = butter(2, [120.0, 280.0], btype="bandpass", fs=sr, output="sos")
    left_car += sosfilt(sos_warm, left_car) * 0.22
    right_car += sosfilt(sos_warm, right_car) * 0.22

    # Automotive glass ceiling filter (6800 Hz) - velvety, zero high sizzle
    sos_silk = butter(1, 6800.0, btype="lowpass", fs=sr, output="sos")
    left_car = left_car * 0.80 + sosfilt(sos_silk, left_car) * 0.20
    right_car = right_car * 0.80 + sosfilt(sos_silk, right_car) * 0.20

    final_mix = np.stack([left_car, right_car], axis=1)

    # Gentle analog saturation
    final_mix = np.tanh(final_mix * 1.10)

    # Master normalization (-1.3 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
