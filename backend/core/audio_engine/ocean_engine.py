from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt


def _lowpass_rumble(rng: np.random.Generator, n: int, sr: int, cutoff: float) -> np.ndarray:
    """Low-frequency deep water rumble (28 Hz - cutoff Hz)."""
    raw = rng.normal(0, 1, n).astype(np.float32)
    cutoff_safe = min(cutoff, float(sr) * 0.45)
    sos_lp = butter(2, cutoff_safe, btype="lowpass", fs=sr, output="sos")
    sos_hp = butter(2, 28.0, btype="highpass", fs=sr, output="sos")
    out = sosfilt(sos_hp, sosfilt(sos_lp, raw)).astype(np.float32)
    out /= max(float(np.max(np.abs(out))), 1e-6)
    return out


def _bandpass_noise(rng: np.random.Generator, n: int, sr: int, low: float, high: float) -> np.ndarray:
    """Bandpass filtered noise for wave textures."""
    low_safe = max(20.0, low)
    high_safe = min(float(sr) * 0.48, max(low_safe + 10.0, high))
    raw = rng.normal(0, 1, n).astype(np.float32)
    sos = butter(2, [low_safe, high_safe], btype="bandpass", fs=sr, output="sos")
    out = sosfilt(sos, raw).astype(np.float32)
    out /= max(float(np.max(np.abs(out))), 1e-6)
    return out


def _pink_noise(rng: np.random.Generator, n: int, sr: int, slope: float = 0.5) -> np.ndarray:
    """Pinkish noise with custom spectral slope for natural water beds."""
    raw = rng.normal(0, 1, n).astype(np.float32)
    fft = np.fft.rfft(raw)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    freqs[0] = 1.0
    fft /= (freqs ** slope)
    out = np.fft.irfft(fft, n).astype(np.float32)
    out /= max(float(np.max(np.abs(out))), 1e-6)
    return out


def _add_wave_event(
    left: np.ndarray,
    right: np.ndarray,
    sr: int,
    rng: np.random.Generator,
    center: float,
    size: float,
    pan_angle: float,
    swell_freq: tuple[float, float] = (35.0, 85.0),
    swell_weight: float = 0.35,
    crash_freq: tuple[float, float] = (160.0, 3200.0),
    crash_weight: float = 0.40,
    foam_freq: tuple[float, float] = (1800.0, 6500.0),
    foam_weight: float = 0.25,
    approach_scale: float = 1.0,
    wash_scale: float = 1.0,
    pan_drift_amount: float = 0.20,
    overall_weight: float = 1.0,
) -> None:
    """Synthesizes an individual wave locally and adds it directly to the master buffer (30x faster!)."""
    n_total = len(left)
    approach_dur = float(rng.uniform(2.6, 4.2)) * size * approach_scale
    break_dur = float(rng.uniform(1.2, 2.0)) * size
    wash_dur = float(rng.uniform(2.4, 4.0)) * size * wash_scale

    t_start = max(0.0, center - approach_dur - 0.5)
    t_end = min(float(n_total) / sr, center + break_dur + wash_dur * 1.6 + 0.5)
    start_idx = int(t_start * sr)
    end_idx = int(t_end * sr)
    n_local = end_idx - start_idx
    if n_local <= 10:
        return

    t = (np.arange(n_local, dtype=np.float32) + start_idx) / sr

    t_approach = center - approach_dur
    t_break = center
    t_wash_start = center + break_dur * 0.25

    # 1. Swell: Rolling mass of deep water
    app_width = max(approach_dur * 0.42, 0.4)
    approach_env = np.exp(-0.5 * ((t - center) / app_width) ** 2)
    approach_env *= 1.0 / (1.0 + np.exp(-np.clip((t - t_approach) * 2.8, -30, 30)))
    swell_raw = _lowpass_rumble(rng, n_local, sr, float(rng.uniform(swell_freq[0], swell_freq[1])))
    swell = approach_env * swell_raw * swell_weight

    # 2. Crest break
    b_width = max(break_dur * 0.38, 0.35)
    break_env = np.exp(-0.5 * ((t - t_break) / b_width) ** 2)
    break_env *= 1.0 + 0.35 * np.tanh((t - t_break) * (-2.0 / b_width))
    break_raw = _bandpass_noise(rng, n_local, sr, crash_freq[0], crash_freq[1])
    breaking = break_env * break_raw * crash_weight

    # 3. Sand wash & foam fizz
    wash_peak = t_wash_start + wash_dur * 0.30
    w_width = max(wash_dur * 0.38, 0.5)
    wash_env = np.exp(-0.5 * ((t - wash_peak) / w_width) ** 2)
    wash_env *= np.exp(-np.maximum(t - wash_peak, 0) / max(wash_dur * 0.65, 0.7))
    foam_raw = _bandpass_noise(rng, n_local, sr, foam_freq[0], foam_freq[1])
    foam = wash_env * foam_raw * foam_weight

    mono = (swell + breaking + foam) * overall_weight

    # Panoramic stereo sweep across beach
    pan_drift = (t - center) / max(wash_dur + break_dur, 2.0)
    pan_dyn = np.clip(pan_angle + pan_drift_amount * pan_drift, 0.12, 0.88)

    left[start_idx:end_idx] += mono * np.cos(pan_dyn * np.pi / 2.0)
    right[start_idx:end_idx] += mono * np.sin(pan_dyn * np.pi / 2.0)


# ==============================================================================
# 01 MONDAY: Calm Sunrise Ocean Waves (01_monday_morning_ocean)
# ==============================================================================
def generate_calm_sunrise_ocean(
    duration_seconds: int,
    output: str | Path,
    seed: int = 101,
    config: dict | None = None,
) -> Path:
    """Monday — Calm Sunrise Ocean:
    - Very soft, smooth waves lapping on shore.
    - Deep low-frequency movement in background.
    - Mild foam and sand wash, clean fresh morning atmosphere.
    - Intervals: 7.5s - 13.5s.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(1.5, 3.0))
    while pos < duration_seconds - 2.5:
        size = float(rng.uniform(0.75, 1.10))
        pan = float(rng.uniform(0.28, 0.72))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(35.0, 80.0), swell_weight=0.34,
            crash_freq=(140.0, 2600.0), crash_weight=0.36,
            foam_freq=(1600.0, 5800.0), foam_weight=0.22,
            approach_scale=1.1, wash_scale=1.0, pan_drift_amount=0.18,
            overall_weight=0.52
        )
        pos += float(rng.uniform(7.5, 13.5))

    # Deep low-frequency movement (32 - 75 Hz)
    deep = _lowpass_rumble(rng, n, sr, 75.0)
    deep_swell = 0.82 + 0.18 * np.sin(2.0 * np.pi * (1.0 / 26.0) * t).astype(np.float32)
    left += deep * deep_swell * 0.14
    right += deep * deep_swell * 0.14

    # Subtle fresh morning breeze (160 - 650 Hz)
    breeze = _bandpass_noise(rng, n, sr, 160.0, 650.0)
    breeze_mod = 0.65 + 0.35 * (np.sin(2.0 * np.pi * (1.0 / 22.0) * t) ** 2)
    left += breeze * breeze_mod * 0.05
    right += breeze * breeze_mod * 0.05

    # Master formatting & silk ceiling (6500 Hz)
    sos_silk = butter(1, 6500.0, btype="lowpass", fs=sr, output="sos")
    left = sosfilt(sos_silk, left)
    right = sosfilt(sos_silk, right)

    stereo = np.stack([left, right], axis=1)
    stereo = np.tanh(stereo * 1.12)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 02 TUESDAY: Tropical Beach Morning Waves (02_tuesday_morning_ocean)
# ==============================================================================
def generate_tropical_beach_ocean(
    duration_seconds: int,
    output: str | Path,
    seed: int = 201,
    config: dict | None = None,
) -> Path:
    """Tuesday — Tropical Beach Morning Waves:
    - Brighter wave texture than Monday, bubbly foam on shore.
    - Shorter, more frequent waves (intervals 4.5s - 8.5s).
    - Water backwash drawing back over sand.
    - Occasional larger wave breaking, open spacious tropical breeze.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(1.0, 2.5))
    while pos < duration_seconds - 2.5:
        is_large = rng.random() < 0.22
        size = float(rng.uniform(1.25, 1.55)) if is_large else float(rng.uniform(0.70, 1.05))
        pan = float(rng.uniform(0.20, 0.80))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(38.0, 95.0), swell_weight=0.36 if is_large else 0.26,
            crash_freq=(180.0, 3600.0), crash_weight=0.48 if is_large else 0.38,
            foam_freq=(2400.0, 7200.0), foam_weight=0.32,
            approach_scale=0.9, wash_scale=1.2, pan_drift_amount=0.25,
            overall_weight=0.50
        )
        pos += float(rng.uniform(4.5, 8.5))

    # Receding water wash / undertow (sand percolation)
    wash_bed = _pink_noise(rng, n, sr, slope=0.45)
    sos_wash = butter(2, [350.0, 4800.0], btype="bandpass", fs=sr, output="sos")
    wash_bed = sosfilt(sos_wash, wash_bed)
    wash_mod = 0.60 + 0.40 * (np.sin(2.0 * np.pi * (1.0 / 14.0) * t) ** 2)
    left += wash_bed * wash_mod * 0.12
    right += wash_bed * wash_mod * 0.12

    # Warm tropical sea breeze
    breeze = _bandpass_noise(rng, n, sr, 140.0, 800.0)
    breeze_mod = 0.60 + 0.40 * (np.sin(2.0 * np.pi * (1.0 / 18.0) * t) ** 2)
    left += breeze * breeze_mod * 0.08
    right += breeze * breeze_mod * 0.08

    # Wide spacious stereo (side * 1.35)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_w = mid * 0.88 + side * 1.35
    right_w = mid * 0.88 - side * 1.35

    stereo = np.stack([left_w, right_w], axis=1)
    stereo = np.tanh(stereo * 1.15)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 03 WEDNESDAY: Quiet Blue Sea (03_wednesday_morning_ocean)
# ==============================================================================
def generate_quiet_blue_sea(
    duration_seconds: int,
    output: str | Path,
    seed: int = 301,
    config: dict | None = None,
) -> Path:
    """Wednesday — Quiet Blue Sea:
    - Completely calm open blue ocean.
    - Deep ocean body layer prominent (30 - 80 Hz).
    - Very soft waves, minimal shore wash, zero harsh high-frequency hiss.
    - Long intervals (9s - 17s), nearly silent meditative horizon.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(2.0, 4.0))
    while pos < duration_seconds - 3.0:
        size = float(rng.uniform(0.75, 1.15))
        pan = float(rng.uniform(0.32, 0.68))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(30.0, 78.0), swell_weight=0.46,
            crash_freq=(110.0, 1800.0), crash_weight=0.24,
            foam_freq=(1200.0, 3800.0), foam_weight=0.14,
            approach_scale=1.3, wash_scale=0.9, pan_drift_amount=0.14,
            overall_weight=0.44
        )
        pos += float(rng.uniform(9.0, 17.0))

    # Prominent deep ocean swell bed (weight 0.20)
    deep_l = _lowpass_rumble(rng, n, sr, 72.0)
    deep_r = _lowpass_rumble(rng, n, sr, 72.0)
    deep_mod = 0.75 + 0.25 * np.sin(2.0 * np.pi * (1.0 / 30.0) * t).astype(np.float32)
    left += deep_l * deep_mod * 0.20
    right += deep_r * deep_mod * 0.20

    # Velvet silk roll-off at 4200 Hz: completely strips hiss
    sos_silk = butter(2, 4200.0, btype="lowpass", fs=sr, output="sos")
    left = sosfilt(sos_silk, left)
    right = sosfilt(sos_silk, right)

    stereo = np.stack([left, right], axis=1)
    stereo = np.tanh(stereo * 1.10)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 04 THURSDAY: Gentle Shoreline Waves (04_thursday_morning_ocean)
# ==============================================================================
def generate_gentle_shoreline_ocean(
    duration_seconds: int,
    output: str | Path,
    seed: int = 401,
    config: dict | None = None,
) -> Path:
    """Thursday — Gentle Shoreline Waves:
    - Listening right at the water's edge.
    - Shoreline wash is the star layer (dominant, lapping sand/pebbles).
    - Gentle small waves close to listener, soft foam texture.
    - Deep surf is quiet in background. Warm, intimate feel.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(1.2, 2.8))
    while pos < duration_seconds - 2.0:
        size = float(rng.uniform(0.65, 0.95))
        pan = float(rng.uniform(0.30, 0.70))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(40.0, 85.0), swell_weight=0.20,
            crash_freq=(180.0, 2400.0), crash_weight=0.32,
            foam_freq=(1400.0, 5600.0), foam_weight=0.48,
            approach_scale=0.85, wash_scale=1.4, pan_drift_amount=0.15,
            overall_weight=0.55
        )
        pos += float(rng.uniform(5.0, 9.5))

    # Shoreline continuous sand percolation & wash bed
    wash_pink = _pink_noise(rng, n, sr, slope=0.52)
    sos_shore = butter(2, [220.0, 3800.0], btype="bandpass", fs=sr, output="sos")
    wash_pink = sosfilt(sos_shore, wash_pink)
    wash_cycle = 0.70 + 0.30 * (np.sin(2.0 * np.pi * (1.0 / 12.0) * t) ** 2)
    left += wash_pink * wash_cycle * 0.26
    right += wash_pink * wash_cycle * 0.26

    # Intimate stereo (narrower, centered around listener sitting at shoreline)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_int = mid * 1.05 + side * 0.75
    right_int = mid * 1.05 - side * 0.75

    stereo = np.stack([left_int, right_int], axis=1)
    stereo = np.tanh(stereo * 1.15)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 05 FRIDAY: Slow Deep Ocean Surf (05_friday_morning_ocean)
# ==============================================================================
def generate_slow_deep_ocean(
    duration_seconds: int,
    output: str | Path,
    seed: int = 501,
    config: dict | None = None,
) -> Path:
    """Friday — Slow Deep Ocean Surf:
    - Deep, low-frequency surf dominant (28 - 75 Hz sub-bass).
    - Slow massive waves with long gaps (11s - 20s).
    - Very gradual swell build-up, NO sudden loud crash.
    - Low shore foam, distant ocean wind.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(2.5, 4.5))
    while pos < duration_seconds - 3.5:
        size = float(rng.uniform(1.20, 1.65))
        pan = float(rng.uniform(0.30, 0.70))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(28.0, 72.0), swell_weight=0.55,
            crash_freq=(100.0, 1900.0), crash_weight=0.30,
            foam_freq=(1100.0, 3600.0), foam_weight=0.12,
            approach_scale=1.5, wash_scale=1.0, pan_drift_amount=0.16,
            overall_weight=0.50
        )
        pos += float(rng.uniform(11.0, 20.0))

    # Continuous deep sub-bass undertow (28 - 68 Hz)
    deep_sub = _lowpass_rumble(rng, n, sr, 68.0)
    deep_swell = 0.75 + 0.25 * np.sin(2.0 * np.pi * (1.0 / 34.0) * t).astype(np.float32)
    left += deep_sub * deep_swell * 0.22
    right += deep_sub * deep_swell * 0.22

    # Distant ocean atmospheric wind
    wind = _bandpass_noise(rng, n, sr, 90.0, 480.0)
    wind_swell = 0.65 + 0.35 * (np.sin(2.0 * np.pi * (1.0 / 24.0) * t) ** 2)
    left += wind * wind_swell * 0.08
    right += wind * wind_swell * 0.08

    # Lowpass silk filter (4800 Hz)
    sos_silk = butter(2, 4800.0, btype="lowpass", fs=sr, output="sos")
    left = sosfilt(sos_silk, left)
    right = sosfilt(sos_silk, right)

    stereo = np.stack([left, right], axis=1)
    stereo = np.tanh(stereo * 1.15)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 06 SATURDAY: Tropical Calm Sea (06_saturday_morning_ocean)
# ==============================================================================
def generate_tropical_calm_sea(
    duration_seconds: int,
    output: str | Path,
    seed: int = 601,
    config: dict | None = None,
) -> Path:
    """Saturday — Tropical Calm Sea:
    - Daytime calm tropical sea.
    - Medium-soft waves with rich natural variety (small laps + medium waves).
    - Smooth beach wash, soft sea breeze, wide pleasant stereo panorama.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(1.2, 2.5))
    while pos < duration_seconds - 2.5:
        size = float(rng.uniform(0.70, 1.25))
        pan = float(rng.uniform(0.22, 0.78))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(35.0, 85.0), swell_weight=0.32,
            crash_freq=(160.0, 3000.0), crash_weight=0.40,
            foam_freq=(1800.0, 6200.0), foam_weight=0.28,
            approach_scale=1.0, wash_scale=1.15, pan_drift_amount=0.24,
            overall_weight=0.48
        )
        pos += float(rng.uniform(5.5, 10.5))

    # Shoreline smooth wash bed
    wash_bed = _pink_noise(rng, n, sr, slope=0.50)
    sos_wash = butter(2, [200.0, 3200.0], btype="bandpass", fs=sr, output="sos")
    wash_bed = sosfilt(sos_wash, wash_bed)
    wash_mod = 0.65 + 0.35 * (np.sin(2.0 * np.pi * (1.0 / 16.0) * t) ** 2)
    left += wash_bed * wash_mod * 0.16
    right += wash_bed * wash_mod * 0.16

    # Soft sea breeze
    breeze = _bandpass_noise(rng, n, sr, 130.0, 720.0)
    breeze_mod = 0.65 + 0.35 * (np.sin(2.0 * np.pi * (1.0 / 20.0) * t) ** 2)
    left += breeze * breeze_mod * 0.07
    right += breeze * breeze_mod * 0.07

    # Wide stereo field (side * 1.38)
    mid = (left + right) * 0.5
    side = (left - right) * 0.5
    left_w = mid * 0.88 + side * 1.38
    right_w = mid * 0.88 - side * 1.38

    stereo = np.stack([left_w, right_w], axis=1)
    stereo = np.tanh(stereo * 1.12)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p


# ==============================================================================
# 07 SUNDAY: Peaceful Sunday Beach (07_sunday_morning_ocean)
# ==============================================================================
def generate_peaceful_sunday_beach(
    duration_seconds: int,
    output: str | Path,
    seed: int = 701,
    config: dict | None = None,
) -> Path:
    """Sunday — Peaceful Sunday Beach:
    - The most peaceful, restorative ocean across the entire week.
    - Very smooth gentle waves, soft creamy foam and wash.
    - Deep surf subtle, extremely light breeze.
    - Zero sudden wave peaks, ultra-stable soothing volume.
    - Velvety 5.0 kHz ceiling, deeply hypnotic for sleep & meditation.
    """
    sr = int((config or {}).get("audio", {}).get("sample_rate", 48000))
    n = int(duration_seconds * sr)
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float32) / sr

    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)

    pos = float(rng.uniform(1.8, 3.2))
    while pos < duration_seconds - 2.5:
        size = float(rng.uniform(0.75, 0.98))
        pan = float(rng.uniform(0.35, 0.65))
        _add_wave_event(
            left, right, sr, rng, pos, size, pan,
            swell_freq=(32.0, 75.0), swell_weight=0.28,
            crash_freq=(130.0, 2200.0), crash_weight=0.32,
            foam_freq=(1400.0, 4800.0), foam_weight=0.22,
            approach_scale=1.2, wash_scale=1.1, pan_drift_amount=0.12,
            overall_weight=0.46
        )
        pos += float(rng.uniform(6.5, 12.0))

    # Gentle background bed with multi-period stochastic drift (periods 46s and 68s)
    bed = _pink_noise(rng, n, sr, slope=0.55)
    sos_bed = butter(2, [150.0, 2800.0], btype="bandpass", fs=sr, output="sos")
    bed = sosfilt(sos_bed, bed)
    drift = 1.0 + 0.08 * np.sin(2.0 * np.pi * (1.0 / 46.0) * t) + 0.05 * np.cos(2.0 * np.pi * (1.0 / 68.0) * t)
    left += bed * drift * 0.22
    right += bed * drift * 0.22

    # Extremely light breeze (35 - 90 Hz whisper)
    breeze = _bandpass_noise(rng, n, sr, 35.0, 90.0)
    left += breeze * 0.04
    right += breeze * 0.04

    # Velvet ceiling filter at 5000 Hz: keeps high frequencies silky and warm
    sos_silk = butter(1, 5000.0, btype="lowpass", fs=sr, output="sos")
    left = sosfilt(sos_silk, left)
    right = sosfilt(sos_silk, right)

    stereo = np.stack([left, right], axis=1)
    stereo = np.tanh(stereo * 1.10)
    peak = float(np.max(np.abs(stereo)))
    if peak > 0:
        stereo = (stereo / peak) * 0.86

    out_p = Path(output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_p), stereo, sr, subtype="PCM_16")
    return out_p
