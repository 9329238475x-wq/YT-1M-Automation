from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw


class BaseImageGenerator:
    def generate(self, prompt: str, width: int, height: int, output: str | Path) -> Path:
        raise NotImplementedError


class PlaceholderImageGenerator(BaseImageGenerator):
    """Offline image used for pipeline tests until a real provider is configured."""
    def generate(self, prompt: str, width: int, height: int, output: str | Path) -> Path:
        img = Image.new("RGB", (width, height), (12, 18, 24))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            shade = int(12 + 22 * (y / max(height - 1, 1)))
            draw.line((0, y, width, y), fill=(shade // 2, shade, shade + 8))
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        return path


def create_generator(provider: str = "placeholder") -> BaseImageGenerator:
    if provider in {"placeholder", "env"}:
        return PlaceholderImageGenerator()
    raise ValueError(f"Unsupported image provider: {provider}")
