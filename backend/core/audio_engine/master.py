from __future__ import annotations

from pathlib import Path
import soundfile as sf

from .rain import generate_rain
from .roof import generate_roof_rain
from .mixer import mix_and_write


def generate_master_audio(duration_seconds: int, output: str | Path, seed: int, config: dict) -> Path:
    sr = int(config["audio"]["sample_rate"])
    intensity = float(config["audio"]["rain_intensity"]["max"])
    rain = generate_rain(duration_seconds, sr, seed, intensity)
    roof = generate_roof_rain(duration_seconds, sr, seed + 1, config["audio"]["roof_resonance"])
    return mix_and_write(
        {"rain": rain, "roof": roof},
        output,
        {"rain": config["audio"]["mix"]["rain"], "roof": config["audio"]["mix"]["roof"]},
    )
