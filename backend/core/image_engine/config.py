from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

# Target Output Specifications
TARGET_WIDTH: int = 2048
TARGET_HEIGHT: int = 1152
TARGET_ASPECT_RATIO: float = 16.0 / 9.0
OUTPUT_FORMAT: str = "PNG"

# Network & Execution Parameters
DEFAULT_REQUEST_TIMEOUT: int = int(os.environ.get("IMAGE_REQUEST_TIMEOUT", "60"))
MAX_RETRIES_PER_MODEL: int = 3
BACKOFF_BASE_SECONDS: float = 1.5

# Central Model Configuration (in strict priority order)
PRIMARY_MODEL: str = os.environ.get("IMAGE_PRIMARY_MODEL", "Tongyi-MAI/Z-Image-Turbo")

BACKUP_MODELS: list[str] = [
    "black-forest-labs/FLUX.1-schnell",
    "Qwen/Qwen-Image-2512",
    "Qwen/Qwen-Image",
]

# Combined 4 manually configured models + AUTO fallback mode
IMAGE_MODELS: list[str] = [
    PRIMARY_MODEL,
    *BACKUP_MODELS,
]

AUTO_FALLBACK_KEY: str = "AUTO"

# Default Quality Negative Prompt
DEFAULT_NEGATIVE_PROMPT: str = (
    "text, watermark, logo, blurry, distorted, low quality, "
    "oversaturated, deformed, cartoon, 3d render, frame, border, cropped"
)


def get_hf_token() -> str | None:
    """Securely resolves Hugging Face token from environment or local CLI login.
    
    NEVER hardcodes or logs token.
    Order of precedence:
    1. HF_TOKEN env var
    2. HUGGINGFACE_HUB_TOKEN env var
    3. huggingface_hub.get_token() (from huggingface-cli login on user's machine)
    """
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if token:
        return token.strip()

    try:
        from huggingface_hub import get_token
        stored = get_token()
        if stored:
            return stored.strip()
    except Exception:
        pass

    return None
