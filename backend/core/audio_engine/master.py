from __future__ import annotations

from pathlib import Path
import numpy as np

from .rain import generate_rain
from .roof import generate_roof_rain
from .thunder import generate_thunder
from .ocean import generate_ocean
from .mixer import mix_and_write
from .cabin_rain import generate_cabin_rain
from .window_rain import generate_window_rain
from .forest_rain import generate_forest_rain
from .tin_roof_rain import generate_tin_roof_rain
from .distant_thunder_storm import generate_distant_thunder_storm
from .car_rain import generate_car_rain
from .peaceful_sleep_rain import generate_peaceful_sleep_rain
from .ocean_engine import (
    generate_calm_sunrise_ocean,
    generate_tropical_beach_ocean,
    generate_quiet_blue_sea,
    generate_gentle_shoreline_ocean,
    generate_slow_deep_ocean,
    generate_tropical_calm_sea,
    generate_peaceful_sunday_beach,
)


def generate_master_audio(duration_seconds: int, output: str | Path, seed: int, config: dict) -> Path:
    audio = config.get("audio", {})
    sr = int(audio.get("sample_rate", 48000))
    theme_id = str(config.get("id", "")).lower()
    theme_name = str(config.get("name", "")).lower()

    # ─── 7-DAY OCEAN AMBIENCE SUITE ───
    # 01 Monday Morning Ocean: Calm Sunrise Ocean
    if (
        audio.get("engine") == "sunrise_ocean"
        or ("01_monday" in theme_id and "ocean" in theme_id)
        or "sunrise" in theme_name
    ):
        return generate_calm_sunrise_ocean(duration_seconds, output, seed, config)

    # 02 Tuesday Morning Ocean: Tropical Beach Morning Waves
    if (
        audio.get("engine") == "tropical_beach_ocean"
        or ("02_tuesday" in theme_id and "ocean" in theme_id)
        or "tropical beach" in theme_name
    ):
        return generate_tropical_beach_ocean(duration_seconds, output, seed, config)

    # 03 Wednesday Morning Ocean: Quiet Blue Sea
    if (
        audio.get("engine") == "quiet_blue_sea"
        or ("03_wednesday" in theme_id and "ocean" in theme_id)
        or "quiet blue" in theme_name
        or "quiet" in theme_name
    ):
        return generate_quiet_blue_sea(duration_seconds, output, seed, config)

    # 04 Thursday Morning Ocean: Gentle Shoreline Waves
    if (
        audio.get("engine") == "gentle_shoreline_ocean"
        or ("04_thursday" in theme_id and "ocean" in theme_id)
        or "shoreline" in theme_name
    ):
        return generate_gentle_shoreline_ocean(duration_seconds, output, seed, config)

    # 05 Friday Morning Ocean: Slow Deep Ocean Surf
    if (
        audio.get("engine") == "slow_deep_ocean"
        or ("05_friday" in theme_id and "ocean" in theme_id)
        or "slow deep" in theme_name
        or "deep ocean" in theme_name
    ):
        return generate_slow_deep_ocean(duration_seconds, output, seed, config)

    # 06 Saturday Morning Ocean: Tropical Calm Sea
    if (
        audio.get("engine") == "tropical_calm_sea"
        or ("06_saturday" in theme_id and "ocean" in theme_id)
        or "tropical calm" in theme_name
    ):
        return generate_tropical_calm_sea(duration_seconds, output, seed, config)

    # 07 Sunday Morning Ocean: Peaceful Sunday Beach
    if (
        audio.get("engine") == "peaceful_sunday_beach"
        or ("07_sunday" in theme_id and "ocean" in theme_id)
        or "peaceful sunday" in theme_name
    ):
        return generate_peaceful_sunday_beach(duration_seconds, output, seed, config)

    # Fallback Ocean
    if config.get("type") == "ocean" or audio.get("engine") == "procedural_ocean":
        ocean = generate_ocean(duration_seconds, sr, seed, audio)
        return mix_and_write({"ocean": ocean}, output, {"ocean": 1.0})

    # Monday: Midnight Cabin Heavy Rain
    if (
        audio.get("engine") == "cabin_rain"
        or "01_monday" in theme_id
        or "cabin" in theme_id
        or "cabin" in theme_name
    ):
        return generate_cabin_rain(duration_seconds, output, seed, config)

    # Tuesday: Rainy Window Night
    if (
        audio.get("engine") == "window_rain"
        or "02_tuesday" in theme_id
        or "window" in theme_id
        or "window" in theme_name
    ):
        return generate_window_rain(duration_seconds, output, seed, config)

    # Wednesday: Forest Rain at Midnight
    if (
        audio.get("engine") == "forest_rain"
        or "03_wednesday" in theme_id
        or "forest" in theme_id
        or "forest" in theme_name
    ):
        return generate_forest_rain(duration_seconds, output, seed, config)

    # Thursday: Heavy Rain on Tin Roof
    if (
        audio.get("engine") == "tin_roof_rain"
        or "04_thursday" in theme_id
        or "tin" in theme_id
        or "tin" in theme_name
    ):
        return generate_tin_roof_rain(duration_seconds, output, seed, config)

    # Friday: Distant Thunder Storm
    if (
        audio.get("engine") == "distant_thunder_storm"
        or "05_friday" in theme_id
        or "distant" in theme_id
        or "distant" in theme_name
        or "storm" in theme_name
    ):
        return generate_distant_thunder_storm(duration_seconds, output, seed, config)

    # Saturday: Cozy Car Rain
    if (
        audio.get("engine") == "car_rain"
        or "06_saturday" in theme_id
        or "car" in theme_id
        or "car" in theme_name
    ):
        return generate_car_rain(duration_seconds, output, seed, config)

    # Sunday: Peaceful Rain for Deep Sleep
    if (
        audio.get("engine") == "peaceful_sleep_rain"
        or "07_sunday" in theme_id
        or "sleep" in theme_id
        or "peaceful" in theme_id
        or "sleep" in theme_name
        or "peaceful" in theme_name
    ):
        return generate_peaceful_sleep_rain(duration_seconds, output, seed, config)

    # Other Rain themes (will be customized day-by-day)
    raw_intensity = audio.get("rain_intensity", 0.85)
    if isinstance(raw_intensity, dict):
        intensity = float(raw_intensity.get("max", 0.85)) * 0.55
    else:
        intensity = float(raw_intensity) * 0.55

    rain = generate_rain(duration_seconds, sr, seed, intensity)
    roof = generate_roof_rain(duration_seconds, sr, seed + 1, float(audio.get("roof_resonance", 0.7)) * 0.6)

    thunder_cfg = audio.get("thunder", {})
    thunder = generate_thunder(duration_seconds, sr, seed + 2, thunder_cfg)

    weights = audio.get("mix", {})
    rain_weight = float(weights.get("rain", 0.55))
    roof_weight = float(weights.get("roof", 0.18))
    thunder_weight = 0.42

    layers = {"rain": rain, "roof": roof, "thunder": thunder}
    mix_weights = {"rain": rain_weight, "roof": roof_weight, "thunder": thunder_weight}

    return mix_and_write(layers, output, mix_weights)
