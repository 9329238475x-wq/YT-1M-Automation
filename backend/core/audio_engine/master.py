from __future__ import annotations

from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt

from .rain import generate_rain
from .roof import generate_roof_rain
from .mixer import mix_and_write


def _generate_ocean(seconds: int, sample_rate: int, seed: int, audio: dict) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * sample_rate)
    t = np.arange(n, dtype=np.float32) / sample_rate
    layers = audio.get("layers", {})

    low = rng.normal(0, 1, n).astype(np.float32)
    sos = butter(2, 0.35, btype="lowpass", fs=sample_rate, output="sos")
    low = sosfilt(sos, low).astype(np.float32)
    low /= max(float(np.max(np.abs(low))), 1e-6)

    wave = np.zeros(n, dtype=np.float32)
    lo = float(audio.get("wave_interval_seconds", {}).get("min", 5))
    hi = float(audio.get("wave_interval_seconds", {}).get("max", 12))
    pos = 0.0
    while pos < seconds:
        interval = float(rng.uniform(lo, hi))
        center = pos + interval * 0.72
        width = max(1.5, interval * 0.32)
        envelope = np.exp(-0.5 * ((t - center) / width) ** 2).astype(np.float32)
        carrier = (
            0.55 * np.sin(2 * np.pi * rng.uniform(0.08, 0.16) * t + rng.uniform(0, 6.28))
            + 0.30 * np.sin(2 * np.pi * rng.uniform(0.18, 0.32) * t + rng.uniform(0, 6.28))
        )
        wave += envelope * carrier.astype(np.float32)
        pos += interval

    rolling = wave * float(layers.get("rolling_waves", 0.4))
    surf = (0.35 * low + 0.18 * np.sin(2 * np.pi * 0.055 * t)) * float(layers.get("deep_surf", 0.28))
    wash_noise = rng.normal(0, 1, n).astype(np.float32)
    wash_sos = butter(2, [700, 5000], btype="bandpass", fs=sample_rate, output="sos")
    wash_noise = sosfilt(wash_sos, wash_noise).astype(np.float32)
    wash_noise /= max(float(np.max(np.abs(wash_noise))), 1e-6)
    wash = wash_noise * (0.35 + 0.65 * np.maximum(wave, 0)) * float(layers.get("shore_wash", 0.24))
    foam = rng.normal(0, 0.035, n).astype(np.float32) * float(layers.get("foam_hiss", 0.06))
    wind = rng.normal(0, 0.01, n).astype(np.float32) * float(layers.get("distant_wind", 0.02))

    mono = surf + rolling + wash + foam + wind
    left = mono * 1.02 + rng.normal(0, 0.004, n).astype(np.float32)
    right = mono * 0.98 + rng.normal(0, 0.004, n).astype(np.float32)
    return np.stack([left, right], axis=1).astype(np.float32)


def generate_master_audio(duration_seconds: int, output: str | Path, seed: int, config: dict) -> Path:
    audio = config["audio"]
    sr = int(audio.get("sample_rate", 48000))
    if config.get("type") == "ocean" or audio.get("engine") == "procedural_ocean":
        return mix_and_write({"ocean": _generate_ocean(duration_seconds, sr, seed, audio)}, output, {"ocean": 1.0})

    intensity = float(audio.get("rain_intensity", {}).get("max", 0.85))
    rain = generate_rain(duration_seconds, sr, seed, intensity)
    roof = generate_roof_rain(duration_seconds, sr, seed + 1, float(audio.get("roof_resonance", 0.7)))
    weights = audio.get("mix", {})
    return mix_and_write(
        {"rain": rain, "roof": roof},
        output,
        {"rain": float(weights.get("rain", 0.8)), "roof": float(weights.get("roof", 0.2))},
    )
