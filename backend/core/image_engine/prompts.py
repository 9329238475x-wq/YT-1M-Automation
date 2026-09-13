from __future__ import annotations

import random


def monday_prompt(seed: int) -> str:
    rng = random.Random(seed)
    angles = ["cinematic eye-level view", "wide establishing view", "cozy interior-facing exterior view"]
    fog = ["thick layered natural fog", "dense atmospheric mist", "deep volumetric forest mist"]
    return (
        "Photorealistic cinematic midnight cabin in a dense dark forest during heavy monsoon rain, "
        f"{rng.choice(angles)}, {rng.choice(fog)}, wet reflective ground, visible rainfall, "
        "warm subtle light glowing from cabin windows, realistic moisture and atmospheric depth, "
        "deep peaceful sleep ambience, natural low-light exposure, detailed wood textures, "
        "professional cinematic photography, full HD 16:9, no people, no animals, no text, no watermark, "
        "no cartoon, no oversaturated colors."
    )
