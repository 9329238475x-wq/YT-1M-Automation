from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"


def load_theme(theme_id: str = "01_monday_evening_rain") -> dict[str, Any]:
    if not theme_id or not str(theme_id).strip():
        theme_id = "01_monday_evening_rain"

    theme_id = str(theme_id).strip()
    if theme_id == "01_monday":
        theme_id = "01_monday_evening_rain"

    path = THEMES / theme_id / "config.json"

    if not path.exists():
        evening_path = THEMES / f"{theme_id}_evening_rain" / "config.json"
        if evening_path.exists():
            path = evening_path
        else:
            ocean_path = THEMES / f"{theme_id}_morning_ocean" / "config.json"
            if ocean_path.exists():
                path = ocean_path
            else:
                fallback_path = THEMES / "01_monday_evening_rain" / "config.json"
                if fallback_path.exists():
                    path = fallback_path
                else:
                    raise FileNotFoundError(f"Theme config not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))
