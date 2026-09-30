from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

# Search paths for audio assets
ASSET_SEARCH_DIRS = [
    Path(__file__).resolve().parents[3] / "Assets",
    Path(__file__).resolve().parents[2] / "assets" / "audio" / "thunder",
    Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/Assets"),
    Path("C:/Users/HDD WORK/Downloads/YT-1M-Automation-main/backend/assets/audio/thunder"),
    Path("C:/YT-1M-Automation/Assets"),
]


def _find_asset(filename: str) -> Path | None:
    """Finds an asset across candidate directories."""
    for d in ASSET_SEARCH_DIRS:
        p = d / filename
        if p.exists():
            return p
    return None


def _load_and_process_strike(
    filename: str,
    target_sr: int,
    speed_factor: float,
    pan_pos: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Loads a real studio thunder recording and processes it to be:
    - Clearly audible and powerful
    - Thick, heavy, and deep ('mota' low-end bass resonance)
    - Zero thinness or sharp crackles (lowpass filtered at 680 Hz)
    - 100% natural, majestic rolling cloud thunder
    """
    file_path = _find_asset(filename)
    if not file_path or not file_path.exists():
        return np.zeros((int(4.0 * target_sr), 2), dtype=np.float32)

    data, sr = sf.read(file_path)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)

    # 1. Pitch down via analog speed scaling (0.86 - 0.90) for deep 'mota' body
    eff_sr = sr * speed_factor
    n_out = int(len(data) * target_sr / eff_sr)
    if n_out <= 0:
        return np.zeros((10, 2), dtype=np.float32)

    idx = np.linspace(0, len(data) - 1, n_out)
    orig_idx = np.arange(len(data))
    left = np.interp(idx, orig_idx, data[:, 0]).astype(np.float32)
    right = np.interp(idx, orig_idx, data[:, 1]).astype(np.float32)

    # 2. Warm lowpass filter at 680 Hz: cuts ALL sharp treble/crackle ('patla' sound), keeps full rich body!
    sos_lp = butter(3, 680.0, btype="lowpass", fs=target_sr, output="sos")
    left = sosfilt(sos_lp, left).astype(np.float32)
    right = sosfilt(sos_lp, right).astype(np.float32)

    # 3. Heavy bass body boost (45 - 220 Hz) for deep chest-rumble resonance
    sos_bass = butter(2, [45.0, 220.0], btype="bandpass", fs=target_sr, output="sos")
    left = left + sosfilt(sos_bass, left).astype(np.float32) * 0.85
    right = right + sosfilt(sos_bass, right).astype(np.float32) * 0.85

    # 4. Smooth 0.3s fade-in (prevents clicks, ensures natural gentle arrival)
    fade_len = min(int(target_sr * 0.30), n_out // 3)
    if fade_len > 1:
        fade_env = (0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))).astype(np.float32)
        left[:fade_len] *= fade_env
        right[:fade_len] *= fade_env

    # 5. Panoramic stereo trajectory across the sky
    t = np.linspace(0, 1, n_out, dtype=np.float32)
    pan_drift = float(rng.uniform(-0.15, 0.15))
    pan_curve = np.clip(pan_pos + pan_drift * t, 0.20, 0.80)

    l_weight = np.cos(pan_curve * np.pi / 2.0)
    r_weight = np.sin(pan_curve * np.pi / 2.0)

    out_l = left * l_weight
    out_r = right * r_weight

    stereo = np.stack([out_l, out_r], axis=1).astype(np.float32)
    peak = max(float(np.max(np.abs(stereo))), 1e-6)
    # Peak normalized so thunder has clear, full-bodied audible authority
    return (stereo / peak) * 0.88


def generate_thunder(
    seconds: float,
    sample_rate: int = 48000,
    seed: int | None = None,
    thunder_cfg: dict | None = None,
) -> np.ndarray:
    """Generates authentic, clearly audible, deep atmospheric thunder."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    track = np.zeros((n, 2), dtype=np.float32)

    preferred = [
        ("universfield-peals-of-thunder-191992.mp3", "peal"),
        ("universfield-thunder-strike-124463.mp3", "strike_roll"),
        ("universfield-peals-of-thunder-191992.mp3", "peal"),
        ("universfield-loud-thunder-192165.mp3", "loud_strike"),
    ]

    available = [f for f, k in preferred if _find_asset(f) is not None]
    if not available:
        available = ["thunder_roll_10.ogg", "thunder_roll_11.ogg"]

    event_times: list[float] = []

    if seconds <= 60.0:
        # In test previews (<=60s): thunder starts at ~3.5s so you hear it right away!
        if seconds >= 8.0:
            event_times.append(3.8)
    else:
        # Dynamic Nature Storm Physics (Organic unpredictable intervals)
        # First thunder rumble starts naturally between 15s to 45s
        cur = float(rng.uniform(15.0, 45.0))
        while cur < (seconds - 12.0):
            event_times.append(cur)

            # Stochastic weather pattern (unpredictable natural clouds):
            # 35% chance: Cluster strike (Next strike happens quickly right after: 8s - 22s)
            # 45% chance: Active storm interval (28s - 65s)
            # 20% chance: Natural gentle lull (75s - 140s)
            rand_roll = float(rng.uniform(0.0, 1.0))
            if rand_roll < 0.35:
                gap = float(rng.uniform(8.0, 22.0))
            elif rand_roll < 0.80:
                gap = float(rng.uniform(28.0, 65.0))
            else:
                gap = float(rng.uniform(75.0, 140.0))

            cur += gap

    for ev_time in event_times:
        start_idx = int(ev_time * sample_rate)
        if start_idx >= n:
            break

        filename = available[rng.integers(0, len(available))]
        speed = float(rng.uniform(0.80, 0.94))
        pan = float(rng.uniform(0.15, 0.85))
        volume_scale = float(rng.uniform(0.68, 1.0))

        strike = _load_and_process_strike(filename, sample_rate, speed, pan, rng) * volume_scale
        strike_len = min(len(strike), n - start_idx)

        track[start_idx : start_idx + strike_len] += strike[:strike_len]

    peak = max(float(np.max(np.abs(track))), 1e-6)
    if peak > 0.88:
        track = track / peak * 0.88

    return track
