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

# 3 Real Studio Thunder Assets (Auto-selected randomly)
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


def _load_and_process_window_thunder(
    filename: str,
    target_sr: int,
    speed: float,
    pan: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Loads a real studio thunder asset and processes it for clear, deep, audible window thunder."""
    p = _find_asset(filename)
    if not p or not p.exists():
        for alt in THUNDER_ASSETS:
            p = _find_asset(alt)
            if p and p.exists():
                break
    if not p or not p.exists():
        return np.zeros((int(4.0 * target_sr), 2), dtype=np.float32)

    data, file_sr = sf.read(p)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)

    eff_sr = file_sr * speed
    n_out = int(len(data) * target_sr / eff_sr)
    if n_out <= 0:
        return np.zeros((10, 2), dtype=np.float32)

    idx = np.linspace(0, len(data) - 1, n_out)
    orig_idx = np.arange(len(data))
    left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
    right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

    # Lowpass filter at 680 Hz: cuts digital screeching, preserves full heavy rolling cloud thunder
    sos_lp = butter(2, 680.0, btype="lowpass", fs=target_sr, output="sos")
    left = sosfilt(sos_lp, left).astype(np.float32)
    right = sosfilt(sos_lp, right).astype(np.float32)

    # Deep bass body resonance (42 - 200 Hz) for heavy chest rumble
    sos_bass = butter(2, [42.0, 200.0], btype="bandpass", fs=target_sr, output="sos")
    left += sosfilt(sos_bass, left).astype(np.float32) * 1.10
    right += sosfilt(sos_bass, right).astype(np.float32) * 1.10

    # Short 35ms attack envelope to prevent clicks
    fade_len = min(int(target_sr * 0.035), n_out // 4)
    if fade_len > 1:
        env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
        left[:fade_len] *= env
        right[:fade_len] *= env

    # Stereo trajectory
    t = np.linspace(0, 1, n_out, dtype=np.float32)
    drift = float(rng.uniform(-0.15, 0.15))
    cur_pan = np.clip(pan + drift * t, 0.15, 0.85)

    out_l = left * np.cos(cur_pan * np.pi / 2.0)
    out_r = right * np.sin(cur_pan * np.pi / 2.0)

    stereo = np.stack([out_l, out_r], axis=1).astype(np.float32)
    peak = max(float(np.max(np.abs(stereo))), 1e-6)
    # Powerful audible level: 0.86
    return (stereo / peak) * 0.86


def generate_window_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 204,
) -> np.ndarray:
    """Generates clearly audible, frequent, majestic thunder rumbles across the sky outside the window.

    - Randomly auto-selects from 3 real studio thunder recordings.
    - First thunder hits at 4.0s - 5.5s so user hears 'badal garajna' immediately in test!
    - Subsequent rumbles hit every 24 - 42s across the track.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    # First thunder event guaranteed early (4.0s - 5.5s)
    event_times: list[float] = [float(rng.uniform(4.0, 5.5))]
    cur = event_times[0] + float(rng.uniform(22.0, 36.0))
    while cur < (seconds - 5.0):
        event_times.append(cur)
        cur += float(rng.uniform(25.0, 42.0))

    for ev in event_times:
        start_idx = int(ev * sr)
        if start_idx >= n:
            break

        # Randomly auto-select from 3 real studio assets
        chosen = THUNDER_ASSETS[rng.integers(0, len(THUNDER_ASSETS))]
        speed = float(rng.uniform(0.85, 0.93))
        pan = float(rng.uniform(0.20, 0.80))

        strike = _load_and_process_window_thunder(chosen, sr, speed, pan, rng)
        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.88:
        track = track / peak_total * 0.88
    return track


def generate_window_outdoor_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 202,
) -> np.ndarray:
    """Soft continuous rainfall heard outside a room window.

    - Gentle double-pane glass acoustic transmission (lowpass at 4200 Hz).
    - Natural dynamic swelling & fading: rain intensity smoothly rises then slowly softens.
    - Velvety, lush body with zero harshness.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, min(4200.0, float(sr) * 0.45), btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 50.0, btype="highpass", fs=sr, output="sos")

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

    # Dynamic swelling and fading (22s to 36s gentle cycle)
    t = np.arange(n, dtype=np.float32) / sr
    swell_base = 0.76 + 0.18 * np.sin(2.0 * np.pi * (1.0 / 24.0) * t) + 0.06 * np.sin(2.0 * np.pi * (1.0 / 38.0) * t + 1.2)
    swell_l = np.clip(swell_base.astype(np.float32), 0.55, 1.0)
    swell_r = np.clip((swell_base + 0.04 * np.sin(2.0 * np.pi * 0.1 * t)).astype(np.float32), 0.55, 1.0)

    out_l = bed_l * swell_l * 0.55
    out_r = bed_r * swell_r * 0.55

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.72, out_r / peak * 0.72], axis=1).astype(np.float32)


def generate_window_glass_texture(
    seconds: float,
    sr: int = 48000,
    seed: int = 203,
) -> np.ndarray:
    """Subtle, delicate rain texture on the glass window pane."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    k_len1 = int(0.009 * sr)
    t1 = np.arange(k_len1, dtype=np.float32) / sr
    raw1 = rng.normal(0, 1, k_len1).astype(np.float32)
    sos1 = butter(2, [1800, 3600], btype="bandpass", fs=sr, output="sos")
    filt1 = sosfilt(sos1, raw1).astype(np.float32)
    attack_len1 = int(0.0012 * sr)
    env1 = np.ones(k_len1, dtype=np.float32)
    env1[:attack_len1] = 0.5 * (1.0 - np.cos(np.pi * np.arange(attack_len1) / attack_len1))
    env1 *= np.exp(-t1 / 0.0028)
    k1 = filt1 * env1
    k1 /= max(float(np.max(np.abs(k1))), 1e-6)

    k_len2 = int(0.012 * sr)
    t2 = np.arange(k_len2, dtype=np.float32) / sr
    raw2 = rng.normal(0, 1, k_len2).astype(np.float32)
    sos2 = butter(2, [1100, 2400], btype="bandpass", fs=sr, output="sos")
    filt2 = sosfilt(sos2, raw2).astype(np.float32)
    attack_len2 = int(0.0015 * sr)
    env2 = np.ones(k_len2, dtype=np.float32)
    env2[:attack_len2] = 0.5 * (1.0 - np.cos(np.pi * np.arange(attack_len2) / attack_len2))
    env2 *= np.exp(-t2 / 0.0038)
    k2 = filt2 * env2
    k2 /= max(float(np.max(np.abs(k2))), 1e-6)

    num_hits = int(22 * seconds)
    if num_hits <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    max_k = max(len(k1), len(k2))
    pos = rng.integers(0, max(1, n - max_k), size=num_hits)
    amps = rng.exponential(scale=0.55, size=num_hits).astype(np.float32)
    amps = np.clip(amps, 0.15, 1.2)
    pans = rng.uniform(0.20, 0.65, size=num_hits).astype(np.float32)

    imp1_l = np.zeros(n, dtype=np.float32)
    imp1_r = np.zeros(n, dtype=np.float32)
    imp2_l = np.zeros(n, dtype=np.float32)
    imp2_r = np.zeros(n, dtype=np.float32)

    split = rng.random(num_hits) > 0.4
    np.add.at(imp1_l, pos[split], (amps * (1.0 - pans))[split])
    np.add.at(imp1_r, pos[split], (amps * pans)[split])
    np.add.at(imp2_l, pos[~split], (amps * (1.0 - pans))[~split])
    np.add.at(imp2_r, pos[~split], (amps * pans)[~split])

    left = fftconvolve(imp1_l, k1, mode="same") + fftconvolve(imp2_l, k2, mode="same")
    right = fftconvolve(imp1_r, k1, mode="same") + fftconvolve(imp2_r, k2, mode="same")

    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-6)
    return np.stack([(left / peak) * 0.20, (right / peak) * 0.20], axis=1).astype(np.float32)


def generate_window_low_wind(
    seconds: float,
    sr: int = 48000,
    seed: int = 205,
) -> np.ndarray:
    """Very subtle background night breeze outside the window (35 - 130 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_wind = butter(2, [35.0, 130.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos_wind, raw_l).astype(np.float32)
    wr = sosfilt(sos_wind, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod = 0.5 + 0.5 * (np.sin(2.0 * np.pi * (1.0 / 16.0) * t)**2)

    out_l = wl * mod
    out_r = wr * mod

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([(out_l / peak) * 0.10, (out_r / peak) * 0.10], axis=1).astype(np.float32)


def generate_window_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int = 202,
    config: dict | None = None,
) -> Path:
    """Generates Tuesday — Rainy Window Night with clearly audible, powerful thunder:

    1. Soft outdoor rainfall with natural organic swells & fades (weight 0.40).
    2. Subtle rain texture on the glass window pane (weight 0.20).
    3. CLEAR, PROMINENT THUNDER (weight 0.65) - Auto-selected from 3 real studio recordings!
    4. Subtle background night breeze (weight 0.10).
    5. Rain is continuous (NO ducking or cutting).
    6. 3D Binaural spatialization tuned for cozy bedroom window immersion.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    # 1. Soft outdoor rain bed with natural swelling & fading
    rain = generate_window_outdoor_rain(seconds, sr, seed)

    # 2. Subtle glass window pane texture
    glass = generate_window_glass_texture(seconds, sr, seed + 1)

    # 3. Clearly audible, powerful rolling thunder (from 3 real assets!)
    thunder = generate_window_thunder(seconds, sr, seed + 2)

    # 4. Subtle night breeze
    wind = generate_window_low_wind(seconds, sr, seed + 3)

    # Mix with prominent thunder weight (0.65) so badal garajna is loud & clear!
    length = min(len(rain), len(glass), len(thunder), len(wind))
    mix = (
        rain[:length] * 0.40 +
        glass[:length] * 0.20 +
        thunder[:length] * 0.65 +
        wind[:length] * 0.10
    )

    # 3D Binaural Immersion
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_3d = mid * 0.92 + side * 1.30
    right_3d = mid * 0.92 - side * 1.30

    # Bedroom warmth
    sos_warm = butter(2, [35.0, 130.0], btype="bandpass", fs=sr, output="sos")
    left_3d += sosfilt(sos_warm, left_3d) * 0.32
    right_3d += sosfilt(sos_warm, right_3d) * 0.32

    # Silk highs
    sos_silk = butter(1, 7000.0, btype="lowpass", fs=sr, output="sos")
    left_3d = left_3d * 0.75 + sosfilt(sos_silk, left_3d) * 0.25
    right_3d = right_3d * 0.75 + sosfilt(sos_silk, right_3d) * 0.25

    final_mix = np.stack([left_3d, right_3d], axis=1)

    # Soft analog saturation
    final_mix = np.tanh(final_mix * 1.04)

    # Normalization (-1.4 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
