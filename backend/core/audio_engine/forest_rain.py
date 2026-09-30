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


def generate_forest_canopy_rain(
    seconds: float,
    sr: int = 48000,
    seed: int = 301,
) -> np.ndarray:
    """Spacious forest canopy rain with dynamic density (breathing between thin and dense).

    - Open, diffused natural acoustics across tall trees.
    - Density smoothly undulates between 0.50 and 0.95 over 24-36s cycles.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_lp = butter(2, min(5500.0, float(sr) * 0.45), btype="lowpass", fs=sr, output="sos")
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

    # Dynamic density modulation
    t = np.arange(n, dtype=np.float32) / sr
    density = 0.70 + 0.18 * np.sin(2.0 * np.pi * (1.0 / 26.0) * t) + 0.05 * np.sin(2.0 * np.pi * (1.0 / 40.0) * t + 0.8)
    density = np.clip(density.astype(np.float32), 0.50, 0.95)

    out_l = bed_l * density * 0.58
    out_r = bed_r * (density + 0.03 * np.sin(2.0 * np.pi * 0.07 * t)).astype(np.float32) * 0.58

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([out_l / peak * 0.76, out_r / peak * 0.76], axis=1).astype(np.float32)


def generate_forest_tree_wind(
    seconds: float,
    sr: int = 48000,
    seed: int = 302,
) -> np.ndarray:
    """Subtle texture of night breeze whispering through wet pine trees and tree canopy (85 Hz - 420 Hz)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    raw_l = rng.normal(0, 1, n).astype(np.float32)
    raw_r = rng.normal(0, 1, n).astype(np.float32)

    sos_wind = butter(2, [85.0, 420.0], btype="bandpass", fs=sr, output="sos")
    wl = sosfilt(sos_wind, raw_l).astype(np.float32)
    wr = sosfilt(sos_wind, raw_r).astype(np.float32)

    t = np.arange(n, dtype=np.float32) / sr
    mod_l = 0.5 + 0.5 * (np.sin(2.0 * np.pi * (1.0 / 14.0) * t)**2)
    mod_r = 0.5 + 0.5 * (np.sin(2.0 * np.pi * (1.0 / 14.0) * t + 0.5)**2)

    out_l = wl * mod_l
    out_r = wr * mod_r

    peak = max(float(np.max(np.abs(out_l))), float(np.max(np.abs(out_r))), 1e-6)
    return np.stack([(out_l / peak) * 0.16, (out_r / peak) * 0.16], axis=1).astype(np.float32)


def generate_foliage_droplets(
    seconds: float,
    sr: int = 48000,
    seed: int = 303,
) -> np.ndarray:
    """Soft raindrops falling on wet broad forest leaves, pine needles, and mossy ground."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)

    k_len = int(0.010 * sr)
    tk = np.arange(k_len, dtype=np.float32) / sr
    raw = rng.normal(0, 1, k_len).astype(np.float32)
    sos = butter(2, [900, 2600], btype="bandpass", fs=sr, output="sos")
    filt = sosfilt(sos, raw).astype(np.float32)
    env = np.exp(-tk / 0.0032).astype(np.float32)
    k = filt * env
    k /= max(float(np.max(np.abs(k))), 1e-6)

    num_drops = int(24 * seconds)
    if num_drops <= 0:
        return np.zeros((n, 2), dtype=np.float32)

    pos = rng.integers(0, max(1, n - k_len), size=num_drops)
    amps = rng.exponential(scale=0.6, size=num_drops).astype(np.float32)
    amps = np.clip(amps, 0.15, 1.3)
    pans = rng.uniform(0.06, 0.94, size=num_drops).astype(np.float32)

    imp_l = np.zeros(n, dtype=np.float32)
    imp_r = np.zeros(n, dtype=np.float32)
    np.add.at(imp_l, pos, amps * (1.0 - pans))
    np.add.at(imp_r, pos, amps * pans)

    drops_l = fftconvolve(imp_l, k, mode="same")
    drops_r = fftconvolve(imp_r, k, mode="same")

    peak = max(float(np.max(np.abs(drops_l))), float(np.max(np.abs(drops_r))), 1e-6)
    return np.stack([(drops_l / peak) * 0.24, (drops_r / peak) * 0.24], axis=1).astype(np.float32)


def generate_distant_forest_thunder(
    seconds: float,
    sr: int = 48000,
    seed: int = 304,
) -> np.ndarray:
    """Distant muffled thunder rumble rolling behind the deep forest tree line.

    - Randomly auto-selected from 3 real studio thunder recordings.
    - First thunder hits at 5.5s - 6.8s so user hears it early in test!
    - Subsequent rolls spaced every 34s - 52s (soft, less frequent, majestic).
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    track = np.zeros((n, 2), dtype=np.float32)

    event_times = [float(rng.uniform(5.5, 6.8))]
    cur = event_times[0] + float(rng.uniform(32.0, 48.0))
    while cur < (seconds - 6.0):
        event_times.append(cur)
        cur += float(rng.uniform(34.0, 52.0))

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

        speed = float(rng.uniform(0.84, 0.90))
        eff_sr = file_sr * speed
        n_out = int(len(data) * sr / eff_sr)
        if n_out <= 0:
            continue

        idx = np.linspace(0, len(data) - 1, n_out)
        orig_idx = np.arange(len(data))
        left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
        right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

        # Muffled forest tree-line filter: steep 420 Hz lowpass
        sos_lp = butter(3, 420.0, btype="lowpass", fs=sr, output="sos")
        left = sosfilt(sos_lp, left).astype(np.float32)
        right = sosfilt(sos_lp, right).astype(np.float32)

        # Deep sub-bass body boost (40 - 180 Hz)
        sos_bass = butter(2, [40.0, 180.0], btype="bandpass", fs=sr, output="sos")
        left += sosfilt(sos_bass, left).astype(np.float32) * 1.05
        right += sosfilt(sos_bass, right).astype(np.float32) * 1.05

        fade_len = min(int(sr * 0.08), n_out // 4)
        if fade_len > 1:
            env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
            left[:fade_len] *= env
            right[:fade_len] *= env

        t = np.linspace(0, 1, n_out, dtype=np.float32)
        drift = float(rng.uniform(-0.15, 0.15))
        cur_pan = np.clip(float(rng.uniform(0.25, 0.75)) + drift * t, 0.12, 0.88)

        out_l = left * np.cos(cur_pan * np.pi / 2.0)
        out_r = right * np.sin(cur_pan * np.pi / 2.0)

        strike = np.stack([out_l, out_r], axis=1).astype(np.float32)
        peak = max(float(np.max(np.abs(strike))), 1e-6)
        strike = (strike / peak) * 0.84

        strike_len = min(len(strike), n - start_idx)
        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak_total = max(float(np.max(np.abs(track))), 1e-6)
    if peak_total > 0.85:
        track = track / peak_total * 0.85
    return track


def generate_forest_rain(
    duration_seconds: int,
    output: str | Path,
    seed: int = 301,
    config: dict | None = None,
) -> Path:
    """Generates Wednesday — Forest Rain at Midnight soundscape:

    1. Soft-to-medium spacious canopy rain with breathing density transitions.
    2. Subtle night wind whispering through the trees.
    3. Soft organic raindrops falling on wet forest foliage.
    4. Distant muffled thunder rumble rolling behind the tree line.
    5. Ultra-wide 3D stereo soundstage (side * 1.55) evoking an expansive midnight forest.
    6. Rain remains 100% continuous (zero ducking).
    7. 100% pure sleep ambience: ZERO birds, ZERO insects.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    seconds = float(duration_seconds)

    rain = generate_forest_canopy_rain(seconds, sr, seed)
    wind = generate_forest_tree_wind(seconds, sr, seed + 1)
    drops = generate_foliage_droplets(seconds, sr, seed + 2)
    thunder = generate_distant_forest_thunder(seconds, sr, seed + 3)

    length = min(len(rain), len(wind), len(drops), len(thunder))
    mix = (
        rain[:length] * 0.44 +
        drops[:length] * 0.22 +
        wind[:length] * 0.14 +
        thunder[:length] * 0.52
    )

    # Ultra-wide 3D spatialization for vast forest feeling (side * 1.55)
    left = mix[:, 0].copy()
    right = mix[:, 1].copy()

    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_3d = mid * 0.88 + side * 1.55
    right_3d = mid * 0.88 - side * 1.55

    # Early forest reflections delay (0.42ms cross-feed)
    del_s = max(int(sr * 0.00042), 1)
    sos_sh = butter(1, 1400.0, btype="lowpass", fs=sr, output="sos")
    sh_r = np.pad(right_3d[:-del_s], (del_s, 0))
    sh_l = np.pad(left_3d[:-del_s], (del_s, 0))
    left_3d += sosfilt(sos_sh, sh_r) * 0.18
    right_3d += sosfilt(sos_sh, sh_l) * 0.18

    # Earth warmth (35 - 130 Hz)
    sos_warm = butter(2, [35.0, 130.0], btype="bandpass", fs=sr, output="sos")
    left_3d += sosfilt(sos_warm, left_3d) * 0.30
    right_3d += sosfilt(sos_warm, right_3d) * 0.30

    # Silk highs (7200 Hz)
    sos_silk = butter(1, 7200.0, btype="lowpass", fs=sr, output="sos")
    left_3d = left_3d * 0.74 + sosfilt(sos_silk, left_3d) * 0.26
    right_3d = right_3d * 0.74 + sosfilt(sos_silk, right_3d) * 0.26

    final_mix = np.stack([left_3d, right_3d], axis=1)
    final_mix = np.tanh(final_mix * 1.04)

    peak = float(np.max(np.abs(final_mix)))
    if peak > 0:
        final_mix = (final_mix / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), final_mix, sr, subtype="PCM_16")
    return out_p
