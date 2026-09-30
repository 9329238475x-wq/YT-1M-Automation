from __future__ import annotations

import random


def build_metadata(config: dict, duration_hours: int, seed: int) -> dict:
    rng = random.Random(seed)
    templates = config["youtube"]["title_templates"]
    title = rng.choice(templates).format(hours=duration_hours)
    return {
        "title": title,
        "description": (
            "Relax with an original cinematic rain ambience designed for sleep, relaxation and study.\n\n"
            f"Ambience: {config['name']}\nDuration: {duration_hours} hours"
        ),
        "tags": config["youtube"]["tags"],
        "category_id": config["youtube"]["category_id"]
    }
