from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

# Audio asset search paths
ASSET_SEARCH_DIRS = [
    Path(__file__).resolve().parents[3] / "Assets",
    Path(__file__).resolve().parents[2] / "assets" / "audio" / "thunder",
    Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/Assets"),
    Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/backend/assets/audio/thunder"),
    Path("C:/YT-1M-Automation/Assets"),
]

# 3 Real Studio Thunder Assets (Auto-selected randomly on every thunder strike)
THUNDER_ASSETS = [
    "universfield-loud-thunder-192165.mp3",
    "universfield-peals-of-thunder-191992.mp3",
    "universfield-thunder-strike-124463.mp3",
]


def _find_asset(filename: str) -> Path | None:
    for d in ASSET_SEARCH_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None


def _load_and_process_thunder(
    filename: str,
    target_sr: int,
    speed: float,
    pan: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Loads a real studio thunder asset and processes it for clear, powerful, deep audible thunder."""
    p = _find_asset(filename)
    if not p or not p.exists():
        # Fallback to secondary asset if primary not found
        for alt in THUNDER_ASSETS:
            p = _find_asset(alt)
            if p and p.exists():
                break
    if not p or not p.exists():
        return np.zeros((int(4.0 * target_sr), 2), dtype=np.float32)

    data, file_sr = sf.read(p)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)

    # Resample with speed factor (0.86 - 0.94) for heavy, thick ('mota') bass weight
    eff_sr = file_sr * speed
    n_out = int(len(data) * target_sr / eff_sr)
    if n_out <= 0:
        return np.zeros((10, 2), dtype=np.float32)

    idx = np.linspace(0, len(data) - 1, n_out)
    orig_idx = np.arange(len(data))
    left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
    right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

    # Lowpass filter at 780 Hz: cuts digital screeching/harshness, but preserves full audible thunder crack & rolling roar!
    sos_lp = butter(2, 780.0, btype="lowpass", fs=target_sr, output="sos")
    left = sosfilt(sos_lp, left).astype(np.float32)
    right = sosfilt(sos_lp, right).astype(np.float32)

    # Deep bass body resonance (45 - 220 Hz) for powerful chest-thumping rumble
    sos_bass = butter(2, [45.0, 220.0], btype="bandpass", fs=target_sr, output="sos")
    left += sosfilt(sos_bass, left).astype(np.float32) * 1.05
    right += sosfilt(sos_bass, right).astype(np.float32) * 1.05

    # Gentle initial attack envelope (25ms) to prevent audio click
    fade_len = min(int(target_sr * 0.025), n_out // 4)
    if fade_len > 1:
        env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
        left[:fade_len] *= env
        right[:fade_len] *= env

    # Panoramic stereo spread across the sky
    t = np.linspace(0, 1, n_out, dtype=np.float32)
    drift = float(rng.uniform(-0.15, 0.15))
    cur_pan = np.clip(pan + drift * t, 0.15, 0.85)

    l_w = np.cos(cur_pan * np.pi / 2.0)
    r_w = np.sin(cur_pan * np.pi / 2.0)
    out_l = left * l_w
    out_r = right * r_w

    stereo = np.stack([out_l, out_r], axis=1).astype(np.float32)
    peak = max(float(np.max(np.abs(stereo))), 1e-6)
    # Powerful audible level: 0.88!
    return (stereo / peak) * 0.88


def generate_cabin_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 45,
    thunder_cfg: dict | None = None,
) -> np.ndarray:
    """Generates clearly audible, frequent, majestic thunder rumbles across the sky.

    - Randomly auto-selects from 3 real studio thunder recordings.
    - First thunder hits at 4 - 6s so the user hears 'badal garajna' right away in testing!
    - Subsequent rumbles hit every 25 - 45s across the track.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    # First thunder event is guaranteed between 4.0s and 6.0s
    event_times: list[float] = [float(rng.uniform(4.0, 6.0))]
    cur = event_times[0] + float(rng.uniform(25.0, 42.0))
    while cur < (seconds - 6.0):
        event_times.append(cur)
        cur += float(rng.uniform(28.0, 46.0))

    for ev in event_times:
        start_idx = int(ev * sr)
        if start_idx >= n:
            break

        # Randomly auto-select from the 3 real studio recordings
        chosen_file = THUNDER_ASSETS[rng.integers(0, len(THUNDER_ASSETS))]
        speed = float(rng.uniform(0.86, 0.94))
        pan = float(rng.uniform(0.25, 0.75))

        strike = _load_and_process_thunder(chosen_file, sr, speed, pan, rng)
        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.88:
        track = track / peak_total * 0.88
    return track


def generate_cabin_outdoor_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 42,
    intensity: float = 0.88,
) -> np.ndarray:
    """Continuous dense outdoor rainfall texture heard from inside the wooden cabin."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, 5000.0, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 60.0, btype="highpass", fs=sr, output="sos")
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
    bed_l /= max(float(np.max(np.abs(bed_l))), 1e-6)
    bed_r /= max(float(np.max(np.abs(bed_r))), 1e-6)

    t = np.arange(n, dtype=np.float32) / sr
    swell_l = 0.88 + 0.12 * np.sin(2.0 * np.pi * 0.08 * t + float(rng.uniform(0, 6.28))).astype(np.float32)
    swell_r = 0.88 + 0.12 * np.sin(2.0 * np.pi * 0.08 * t + float(rng.uniform(0, 6.28)) + 0.45).astype(np.float32)

    k_len = int(0.012 * sr)
    tk = np.arange(k_len, dtype=np.float32) / sr
    sos_k = butter(2, [1400, 3600], btype="bandpass", fs=sr, output="sos")
    k_drop = sosfilt(sos_k, rng.normal(0, 1, k_len).astype(np.float32)) * np.exp(-tk / 0.003)
    k_drop /= max(float(np.max(np.abs(k_drop))), 1e-6)

    num_drops = int(22 * seconds * intensity)
    pos = rng.integers(0, max(1, n - k_len), size=num_drops)
    amps = rng.exponential(scale=0.6, size=num_drops).astype(np.float32)
    pans = rng.uniform(0.12, 0.88, size=num_drops).astype(np.float32)

    imp_l = np.zeros(n, dtype=np.float32)
    imp_r = np.zeros(n, dtype=np.float32)
    np.add.at(imp_l, pos, amps * (1.0 - pans))
    np.add.at(imp_r, pos, amps * pans)

    drops_l = fftconvolve(imp_l, k_drop, mode="same")
    drops_r = fftconvolve(imp_r, k_drop, mode="same")
    drops_peak = max(float(np.max(np.abs(drops_l))), float(np.max(np.abs(drops_r))), 1e-6)
    drops_l = (drops_l / drops_peak) * 0.25
    drops_r = (drops_r / drops_peak) * 0.25

    out_l = bed_l * swell_l * 0.58 + drops_l
    out_r = bed_r * swell_r * 0.58 + drops_r

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.80, out_r / peak * 0.80], axis=1).astype(np.float32)


def generate_wooden_roof_resonance(
    seconds: float,
    sr: int = 48000,
    seed: int = 43,
    level: float = 0.75,
) -> np.ndarray:
    """Acoustic patter of raindrops falling on the wooden cabin roof overhead."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    k_len1 = int(0.010 * sr)
    t1 = np.arange(k_len1, dtype=np.float32) / sr
    raw1 = rng.normal(0, 1, k_len1).astype(np.float32)
    sos1 = butter(2, [220, 520], btype="bandpass", fs=sr, output="sos")
    k1 = sosfilt(sos1, raw1).astype(np.float32) * np.exp(-t1 / 0.0035)
    k1 = (k1 / max(float(np.max(np.abs(k1))), 1e-6)).astype(np.float32)

    k_len2 = int(0.007 * sr)
    t2 = np.arange(k_len2, dtype=np.float32) / sr
    raw2 = rng.normal(0, 1, k_len2).astype(np.float32)
    sos2 = butter(2, [650, 1500], btype="bandpass", fs=sr, output="sos")
    k2 = sosfilt(sos2, raw2).astype(np.float32) * np.exp(-t2 / 0.0022)
    k2 = (k2 / max(float(np.max(np.abs(k2))), 1e-6)).astype(np.float32)

    hits_per_sec = int(28 * float(np.clip(level, 0.4, 1.1)))
    num_hits = int(hits_per_sec * seconds)
    if num_hits <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    max_k = max(len(k1), len(k2))
    pos = rng.integers(0, max(1, n - max_k), size=num_hits)
    amps = rng.exponential(scale=0.65, size=num_hits).astype(np.float32)
    amps = np.clip(amps, 0.2, 1.4)
    pans = rng.uniform(0.18, 0.82, size=num_hits).astype(np.float32)

    imp1_l = np.zeros(n, dtype=np.float32)
    imp1_r = np.zeros(n, dtype=np.float32)
    imp2_l = np.zeros(n, dtype=np.float32)
    imp2_r = np.zeros(n, dtype=np.float32)

    split = rng.random(num_hits) > 0.45
    np.add.at(imp1_l, pos[split], (amps * (1.0 - pans))[split])
    np.add.at(imp1_r, pos[split], (amps * pans)[split])
    np.add.at(imp2_l, pos[~split], (amps * (1.0 - pans))[~split])
    np.add.at(imp2_r, pos[~split], (amps * pans)[~split])

    left = fftconvolve(imp1_l, k1, mode="same") + fftconvolve(imp2_l, k2, mode="same")
    right = fftconvolve(imp1_r, k1, mode="same") + fftconvolve(imp2_r, k2, mode="same")

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    scale = 0.24 * float(np.clip(level, 0.3, 1.0))
    return np.stack([(left / peak) * scale, (right / peak) * scale], axis=1).astype(np.float32)


def generate_cabin_low_wind(
    seconds: float,
    sr: int = 48000,
    seed: int = 44,
) -> np.ndarray:
    """Very subtle low-frequency background wind outside the cabin (38 - 155 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_wind = butter(2, [38.0, 155.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos_wind, raw_l).astype(np.float32)
    wr = sosfilt(sos_wind, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod_l = 0.5 + 0.5 * (np.sin(2.0 * np.pi * 0.09 * t)**2)
    mod_r = 0.5 + 0.5 * (np.sin(2.0 * np.pi * 0.09 * t + 0.6)**2)

    out_l = wl * mod_l
    out_r = wr * mod_r

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([(out_l / peak) * 0.16, (out_r / peak) * 0.16], axis=1).astype(np.float32)


def generate_cabin_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int,
    config: dict,
) -> Path:
    """Generates Monday — Midnight Cabin Heavy Rain with clearly audible, powerful thunder.

    1. Continuous dense rain bed (weight 0.42).
    2. Wooden roof resonance (weight 0.15).
    3. Low-frequency night cabin wind (weight 0.10).
    4. CLEAR, PROMINENT THUNDER (weight 0.68) - Auto-selected from 3 real studio recordings!
    5. Rain is 100% continuous and never drops or ducks.
    6. 3D Binaural spatialization tuned for cozy headphone immersion.
    """
    sr = int(config.get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)
    audio_cfg = config.get("audio", {})

    intensity = float(audio_cfg.get("rain_intensity", 0.88))
    roof_level = float(audio_cfg.get("roof_resonance", 0.75))

    rain = generate_cabin_outdoor_rain(seconds, sr, seed, intensity=intensity)
    roof = generate_wooden_roof_resonance(seconds, sr, seed + 1, level=roof_level)
    wind = generate_cabin_low_wind(seconds, sr, seed + 2)
    thunder = generate_cabin_thunder(seconds, sr, seed + 3, audio_cfg.get("thunder"))

    # Balance: Thunder has full prominent weight (0.68) so badal garajna is loud & clear!
    length = min(len(rain), len(roof), len(wind), len(thunder))
    mix = (
        rain[:length] * 0.42 +
        roof[:length] * 0.15 +
        wind[:length] * 0.10 +
        thunder[:length] * 0.68
    )

    # 3D Binaural Spatialization
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    side_w = side * 1.35
    mid_w = mid * 0.90
    left_3d = mid_w + side_w
    right_3d = mid_w - side_w

    del_s = max(int(sr * 0.0003), 1)
    sos_sh = butter(1, 1600.0, btype="lowpass", fs=sr, output="sos")
    sh_r = np.pad(right_3d[:-del_s], (del_s, 0))
    sh_l = np.pad(left_3d[:-del_s], (del_s, 0))
    left_3d += sosfilt(sos_sh, sh_r) * 0.16
    right_3d += sosfilt(sos_sh, sh_l) * 0.16

    # Sub-bass chest warmth (35 - 140 Hz)
    sos_sub = butter(2, [35.0, 140.0], btype="bandpass", fs=sr, output="sos")
    left_3d += sosfilt(sos_sub, left_3d) * 0.35
    right_3d += sosfilt(sos_sub, right_3d) * 0.35

    # Gentle silk top filter (7500 Hz)
    sos_silk = butter(1, 7500.0, btype="lowpass", fs=sr, output="sos")
    left_3d = left_3d * 0.75 + sosfilt(sos_silk, left_3d) * 0.25
    right_3d = right_3d * 0.75 + sosfilt(sos_silk, right_3d) * 0.25

    final_mix = np.stack([left_3d, right_3d], axis=1)

    # Soft analog tape warming saturation
    final_mix = np.tanh(final_mix * 1.05)

    # Master normalization (-1.4 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), final_mix, sr, subtype="PCM_16")
    return out_path
