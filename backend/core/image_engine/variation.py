from __future__ import annotations

import random
from typing import Sequence

# Curated Controlled Visual Variations (preserving original prompt subject)
VARIATION_PROFILES: list[dict[str, str]] = [
    {
        "name": "Wide Atmospheric View",
        "camera": "wide cinematic establishing shot, expansive landscape framing",
        "lighting": "soft natural diffused lighting, gentle atmospheric depth",
        "detail": "clean balanced composition, subtle layered horizon",
    },
    {
        "name": "Low-Angle Foreground Depth",
        "camera": "low camera angle, immersive ground-level perspective",
        "lighting": "subtle ambient reflections, soft directional glow",
        "detail": "detailed tactile foreground textures, leading perspective lines",
    },
    {
        "name": "Panoramic Ethereal Mist",
        "camera": "panoramic wide composition, vast open horizon framing",
        "lighting": "ethereal soft mist-filtered light, delicate atmospheric haze",
        "detail": "peaceful spatial depth, gentle volumetric light diffusion",
    },
    {
        "name": "Intimate Eye-Level Cinematic",
        "camera": "eye-level medium-wide cinematic framing",
        "lighting": "rich balanced illumination, soft natural contrast",
        "detail": "refined environmental details, serene organic textures",
    },
    {
        "name": "Elevated Diagonal Perspective",
        "camera": "slightly elevated diagonal perspective, graceful depth",
        "lighting": "subtle golden ambient highlights, warm diffused rays",
        "detail": "harmonious rule-of-thirds composition, gentle focal roll-off",
    },
    {
        "name": "Deep Atmospheric Immersion",
        "camera": "deep perspective view, centered tranquil horizon",
        "lighting": "deep moody atmospheric tones, cinematic ambient glow",
        "detail": "delicate moisture and fine environmental nuances, tranquil mood",
    },
]

# Rain Style Ambient Enhancements (cinematic dream-like ambience)
RAIN_STYLE_ENHANCEMENT: str = (
    "cinematic dream-like atmosphere, deep atmospheric fog, wet reflective surfaces, "
    "realistic rainfall texture, subtle moisture reflections, volumetric mist, "
    "soft diffused lighting, peaceful sleep ambience, rich dark blue-gray tones"
)

# Ocean Style Ambient Enhancements (realistic cinematic coastal photography)
OCEAN_STYLE_ENHANCEMENT: str = (
    "realistic cinematic ocean photography, natural rolling water texture, "
    "detailed shoreline, soft natural coastal sunlight, subtle sea mist, "
    "clean wide composition, photorealistic realism"
)


def detect_style_context(prompt: str) -> str:
    """Detects whether prompt is rain-focused, ocean-focused, or general."""
    p_lower = prompt.lower()
    rain_keywords = ["rain", "monsoon", "cabin", "storm", "thunder", "roof", "window", "downpour", "drizzle"]
    ocean_keywords = ["ocean", "beach", "sea", "waves", "shore", "shoreline", "surf", "coastal", "sand"]

    is_rain = any(k in p_lower for k in rain_keywords)
    is_ocean = any(k in p_lower for k in ocean_keywords)

    if is_rain and not is_ocean:
        return "rain"
    if is_ocean and not is_rain:
        return "ocean"
    if is_rain and is_ocean:
        # tie breaker based on count
        rain_hits = sum(p_lower.count(k) for k in rain_keywords)
        ocean_hits = sum(p_lower.count(k) for k in ocean_keywords)
        return "rain" if rain_hits >= ocean_hits else "ocean"
    return "general"


def apply_controlled_variation(
    base_prompt: str,
    variation_index: int | None = None,
    style_preset: str | None = None,
    seed: int | None = None,
) -> str:
    """Applies controlled visual variation to a prompt without altering its core subject.
    
    Args:
        base_prompt: The user's original raw prompt.
        variation_index: Specific variation profile index (0 to len(VARIATION_PROFILES)-1).
        style_preset: Optional forced style ("rain", "ocean", "general", or None to auto-detect).
        seed: Optional seed for reproducible randomized variations.
    
    Returns:
        Enhanced prompt string preserving the original theme.
    """
    clean_prompt = base_prompt.strip().rstrip(",.")
    rng = random.Random(seed) if seed is not None else random.Random()

    # Determine variation profile
    if variation_index is not None:
        profile = VARIATION_PROFILES[variation_index % len(VARIATION_PROFILES)]
    else:
        profile = rng.choice(VARIATION_PROFILES)

    # Determine style context
    detected_style = (style_preset or detect_style_context(clean_prompt)).lower()

    # Assemble enhancement elements
    enhancements: list[str] = [
        profile["camera"],
        profile["lighting"],
        profile["detail"],
    ]

    # Add gentle ambient touch if not already strongly in base prompt
    base_lower = clean_prompt.lower()
    if detected_style == "rain" and "dream-like" not in base_lower:
        enhancements.append("deep volumetric mist, wet atmospheric reflections, peaceful sleep ambience")
    elif detected_style == "ocean" and "photorealistic" not in base_lower:
        enhancements.append("detailed natural water movement, realistic coastal photography")

    # Combine: original prompt ALWAYS comes first and leads the image generation!
    variation_text = ", ".join(enhancements)
    return f"{clean_prompt}, {variation_text}"
