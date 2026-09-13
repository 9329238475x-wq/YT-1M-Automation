from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"


def load_theme(theme_id: str = "01_monday") -> dict[str, Any]:
    path = THEMES / theme_id / "config.json"
    if not path.exists():
        raise FileNotFoundError(f"Theme config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
