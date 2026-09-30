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


def generate_steady_foreground_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 501,
) -> np.ndarray:
    """Foreground steady soft/medium continuous rain.
    
    - Rich pink-noise base with continuous soothing flow.
    - Naturally dispersed micro droplets (1500 - 3800 Hz) providing organic texture.
    - Sits comfortably in foreground as a peaceful sleep blanket.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    # 1. Wide continuous rain bed
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, 5600.0, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 85.0, btype="highpass", fs=sr, output="sos")

    fl = sosfilt(sos_hp, sosfilt(sos_lp, raw_l)).astype(np.float32)
    fr = sosfilt(sos_hp, sosfilt(sos_lp, raw_r)).astype(np.float32)

    # Pink spectral tilt (1 / sqrt(f))
    fft_l = np.fft.rfft(fl)
    fft_r = np.fft.rfft(fr)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    freqs[0] = 1.0
    fft_l /= np.sqrt(freqs)
    fft_r /= np.sqrt(freqs)

    bed_l = np.fft.irfft(fft_l, n).astype(np.float32)
    bed_r = np.fft.irfft(fft_r, n).astype(np.float32)

    # 2. Subtle foreground droplet texture (scattered micro impacts)
    k_len = int(0.009 * sr)
    t_k = np.arange(k_len, dtype=np.float32) / sr
    raw_k = rng.normal(0, 1, k_len).astype(np.float32)
    sos_k = butter(2, [1500, 3800], btype="bandpass", fs=sr, output="sos")
    k = sosfilt(sos_k, raw_k).astype(np.float32) * np.exp(-t_k / 0.0028)
    k /= max(float(np.max(np.abs(k))), 1e-6)

    hits_count = int(55 * seconds)
    if hits_count > 0:
        pos = rng.integers(0, max(1, n - k_len), size=hits_count)
        amps = rng.exponential(scale=0.55, size=hits_count).astype(np.float32)
        amps = np.clip(amps, 0.15, 1.3)
        pans = rng.uniform(0.15, 0.85, size=hits_count).astype(np.float32)

        imp_l = np.zeros(n, dtype=np.float32)
        imp_r = np.zeros(n, dtype=np.float32)
        np.add.at(imp_l, pos, amps * (1.0 - pans))
        np.add.at(imp_r, pos, amps * pans)

        drops_l = fftconvolve(imp_l, k, mode="same")
        drops_r = fftconvolve(imp_r, k, mode="same")
    else:
        drops_l = np.zeros(n, dtype=np.float32)
        drops_r = np.zeros(n, dtype=np.float32)

    out_l = bed_l * 0.72 + drops_l * 0.28
    out_r = bed_r * 0.72 + drops_r * 0.28

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.88, out_r / peak * 0.88], axis=1).astype(np.float32)


def generate_natural_distant_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 502,
) -> np.ndarray:
    """Natural distant thunder rumble sitting deep in the background.
    
    - Randomly auto-selects from the 3 real studio thunder recordings.
    - Distant air absorption filtering (480 Hz lowpass + sub-bass body).
    - Long raised-cosine fade-in (1.6s) to ensure NO sudden loud spikes.
    - Long random natural gaps between rumbles (38s to 65s).
    - First rumble at 4.8s - 6.2s for prompt testing audition.
    - Volume carefully controlled so it enhances the storm mood without fear or startling.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    # First event hits early for instant audition in test lab
    event_times = [float(rng.uniform(4.8, 8.5))]
    cur = event_times[0] + float(rng.uniform(15.0, 35.0))
    while cur < (seconds - 6.0):
        event_times.append(cur)
        # Organic stochastic weather:
        # 35% cluster burst (next rumble right after: 9s - 22s)
        # 45% active interval (26s - 55s)
        # 20% gentle rain lull (65s - 120s)
        roll = float(rng.uniform(0.0, 1.0))
        if roll < 0.35:
            gap = float(rng.uniform(9.0, 22.0))
        elif roll < 0.80:
            gap = float(rng.uniform(26.0, 55.0))
        else:
            gap = float(rng.uniform(65.0, 120.0))
        cur += gap

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

        # Distant atmospheric slowdown (deep pitch, slow roll, varied)
        speed = float(rng.uniform(0.79, 0.92))
        vol_scale = float(rng.uniform(0.70, 1.0))
        eff_sr = file_sr * speed
        n_out = int(len(data) * sr / eff_sr)
        if n_out <= 0:
            continue

        idx = np.linspace(0, len(data) - 1, n_out)
        orig_idx = np.arange(len(data))
        left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
        right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

        # Distant horizon filtering: 480 Hz lowpass removes all sharp crackles
        sos_lp = butter(2, 480.0, btype="lowpass", fs=sr, output="sos")
        left = sosfilt(sos_lp, left).astype(np.float32)
        right = sosfilt(sos_lp, right).astype(np.float32)

        # Deep sub-bass resonance (38 - 140 Hz)
        sos_bass = butter(2, [38.0, 140.0], btype="bandpass", fs=sr, output="sos")
        left += sosfilt(sos_bass, left).astype(np.float32) * 0.85
        right += sosfilt(sos_bass, right).astype(np.float32) * 0.85

        # Gentle 1.6s raised-cosine fade-in: NO sudden volume jump!
        fade_len = min(int(sr * 1.6), n_out // 3)
        if fade_len > 1:
            env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
            left[:fade_len] *= env
            right[:fade_len] *= env

        # Gentle fade-out envelope at tail
        fade_out_len = min(int(sr * 2.5), n_out // 3)
        if fade_out_len > 1:
            env_out = (0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out_len) / fade_out_len))).astype(np.float32)
            left[-fade_out_len:] *= env_out
            right[-fade_out_len:] *= env_out

        pan = float(rng.uniform(0.30, 0.70))
        out_l = left * np.cos(pan * np.pi / 2.0)
        out_r = right * np.sin(pan * np.pi / 2.0)

        strike = np.stack([out_l, out_r], axis=1).astype(np.float32)
        peak = max(float(np.max(np.abs(strike))), 1e-6)
        # Controlled amplitude with dynamic distance variation
        strike = (strike / peak) * 0.46 * vol_scale

        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.50:
        track = track / peak_total * 0.50
    return track


def generate_gentle_wind_ambience(
    seconds: float,
    sr: int = 48000,
    seed: int = 503,
) -> np.ndarray:
    """Gentle storm wind ambience (45 - 220 Hz) with slow, soothing ebb and flow."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos = butter(2, [45.0, 220.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos, raw_l).astype(np.float32)
    wr = sosfilt(sos, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    # Slow gentle swell (period ~20s)
    mod = 0.55 + 0.45 * (np.sin(2.0 * np.pi * (1.0 / 20.0) * t)**2)
    peak = max(float(np.max(np.abs(wl))), float(np.max(np.abs(wr))), 1e-6)
    return np.stack([(wl * mod / peak) * 0.12, (wr * mod / peak) * 0.12], axis=1).astype(np.float32)


def generate_distant_thunder_storm(
    duration_seconds: int,
    output: str | Path,
    seed: int = 501,
    config: dict | None = None,
) -> Path:
    """Generates Friday — Distant Thunder Storm soundscape:
    
    1. Steady soft/medium continuous rain in the foreground (weight 0.64).
    2. Distant thunder rumble in the background using studio assets (weight 0.42).
    3. Natural long gaps between rumbles (38s to 68s).
    4. Gentle storm wind ambience (weight 0.11).
    5. Zero sudden volume spikes, zero tension: deep, cinematic, sleep-friendly.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    rain = generate_steady_foreground_rain(seconds, sr, seed)
    thunder = generate_natural_distant_thunder(seconds, sr, seed + 1)
    wind = generate_gentle_wind_ambience(seconds, sr, seed + 2)

    length = min(len(rain), len(thunder), len(wind))
    # Rain foreground (0.64), Thunder background (0.42), Wind (0.11)
    mix = (
        rain[:length] * 0.64 +
        thunder[:length] * 0.42 +
        wind[:length] * 0.11
    )

    # Wide atmospheric stereo field
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_wide = mid * 0.88 + side * 1.35
    right_wide = mid * 0.88 - side * 1.35

    # Sub-bass warmth (35 - 130 Hz)
    sos_warm = butter(2, [35.0, 130.0], btype="bandpass", fs=sr, output="sos")
    left_wide += sosfilt(sos_warm, left_wide) * 0.25
    right_wide += sosfilt(sos_warm, right_wide) * 0.25

    # Silk ceiling filter (7500 Hz) to keep the sound warm and sleep-friendly
    sos_silk = butter(1, 7500.0, btype="lowpass", fs=sr, output="sos")
    left_wide = left_wide * 0.78 + sosfilt(sos_silk, left_wide) * 0.22
    right_wide = right_wide * 0.78 + sosfilt(sos_silk, right_wide) * 0.22

    final_mix = np.stack([left_wide, right_wide], axis=1)

    # Soft analog warmth saturation
    final_mix = np.tanh(final_mix * 1.2)

    # Master normalization (-1.3 dBFS)
    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
