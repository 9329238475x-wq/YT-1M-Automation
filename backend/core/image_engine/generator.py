from __future__ import annotations

import os
import time
import logging
import random
from pathlib import Path
from PIL import Image

try:
    from .config import (
        TARGET_WIDTH,
        TARGET_HEIGHT,
        DEFAULT_NEGATIVE_PROMPT,
        DEFAULT_REQUEST_TIMEOUT,
    )
    from .models import GenerationResult, ModelAttempt
    from .variation import apply_controlled_variation, detect_style_context
    from .resizer import enforce_target_resolution
    from .router import ModelRouter, ImageGenerationError
except ImportError:
    from image_engine_config import (
        TARGET_WIDTH,
        TARGET_HEIGHT,
        DEFAULT_NEGATIVE_PROMPT,
        DEFAULT_REQUEST_TIMEOUT,
    )
    from image_engine_models import GenerationResult, ModelAttempt
    from image_engine_variation import apply_controlled_variation, detect_style_context
    from image_engine_resizer import enforce_target_resolution
    from image_engine_router import ModelRouter, ImageGenerationError

logger = logging.getLogger("ImageEngine")


class BaseImageGenerator:
    """Base interface for all image generation backends."""

    def generate(
        self,
        prompt: str,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        output: str | Path = "output.png",
        seed: int | None = None,
        style_preset: str | None = None,
        variation_index: int | None = None,
        negative_prompt: str | None = None,
        timeout: int | None = None,
    ) -> Path:
        raise NotImplementedError

    def generate_batch(
        self,
        prompt: str,
        count: int,
        output_dir: str | Path,
        base_seed: int | None = None,
        style_preset: str | None = None,
        negative_prompt: str | None = None,
    ) -> list[Path]:
        """Generates a sequence of uniquely numbered images (1.png, 2.png...)."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []
        for i in range(1, count + 1):
            target_file = out_dir / f"{i}.png"
            img_seed = (base_seed + i) if base_seed is not None else random.randint(1, 2_147_483_647)
            saved_path = self.generate(
                prompt=prompt,
                width=TARGET_WIDTH,
                height=TARGET_HEIGHT,
                output=target_file,
                seed=img_seed,
                style_preset=style_preset,
                variation_index=i - 1,
                negative_prompt=negative_prompt,
            )
            results.append(saved_path)
        return results


class PlaceholderImageGenerator(BaseImageGenerator):
    """Offline placeholder generator for lightweight unit tests."""

    def generate(
        self,
        prompt: str,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        output: str | Path = "output.png",
        seed: int | None = None,
        style_preset: str | None = None,
        variation_index: int | None = None,
        negative_prompt: str | None = None,
        timeout: int | None = None,
    ) -> Path:
        import urllib.parse
        from PIL import ImageDraw

        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Try free photorealistic web AI image generation
        try:
            import httpx
            safe_prompt = urllib.parse.quote(prompt[:120])
            url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={width}&height={height}&nologo=true&seed={seed or 42}"
            resp = httpx.get(url, timeout=12.0)
            if resp.status_code == 200 and len(resp.content) > 5000:
                import io
                downloaded = Image.open(io.BytesIO(resp.content)).convert("RGB")
                if downloaded.size != (width, height):
                    downloaded = downloaded.resize((width, height), Image.Resampling.LANCZOS)
                downloaded.save(out_path, "PNG")
                return out_path
        except Exception:
            pass

        # 2. Offline Fallback: Render visible cozy rain cabin interior with glowing window
        img = Image.new("RGB", (width, height), (18, 14, 24))
        draw = ImageDraw.Draw(img)

        # Ambient background gradient
        for y in range(height):
            r = int(15 + 25 * (y / max(height - 1, 1)))
            g = int(20 + 35 * (y / max(height - 1, 1)))
            b = int(35 + 45 * (y / max(height - 1, 1)))
            draw.line((0, y, width, y), fill=(r, g, b))

        # Glowing Window Pane
        win_x1, win_y1 = int(width * 0.15), int(height * 0.12)
        win_x2, win_y2 = int(width * 0.85), int(height * 0.88)
        draw.rectangle([win_x1, win_y1, win_x2, win_y2], fill=(24, 38, 58), outline=(65, 50, 40), width=12)
        # Window cross bars
        mid_x = (win_x1 + win_x2) // 2
        mid_y = (win_y1 + win_y2) // 2
        draw.line((mid_x, win_y1, mid_x, win_y2), fill=(65, 50, 40), width=8)
        draw.line((win_x1, mid_y, win_x2, mid_y), fill=(65, 50, 40), width=8)

        # Warm amber lamp reflection glow
        draw.ellipse([int(width * 0.65), int(height * 0.4), int(width * 0.82), int(height * 0.7)], fill=(45, 50, 65))

        # Rain streaks on window
        import random as rnd
        r_gen = rnd.Random(seed or 42)
        for _ in range(180):
            rx = r_gen.randint(win_x1 + 10, win_x2 - 10)
            ry = r_gen.randint(win_y1 + 10, win_y2 - 30)
            rlen = r_gen.randint(8, 25)
            draw.line((rx, ry, rx + 1, ry + rlen), fill=(160, 190, 220), width=2)

        img.save(out_path, "PNG")
        return out_path


class HuggingFaceImageGenerator(BaseImageGenerator):
    """Primary Text-to-Image Engine using Hugging Face multi-model router."""

    def __init__(
        self,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.timeout = timeout
        self.router = ModelRouter(timeout=self.timeout)

    def generate(
        self,
        prompt: str,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        output: str | Path = "output.png",
        seed: int | None = None,
        style_preset: str | None = None,
        variation_index: int | None = None,
        negative_prompt: str | None = None,
        timeout: int | None = None,
    ) -> Path:
        """Generates a single 2048x1152 16:9 PNG image from a prompt.
        
        Applies controlled visual variation, model fallback, automatic retries,
        and guarantees exact 2048x1152 output resolution.
        """
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Resolve Seed (User-provided or random uint32)
        resolved_seed = seed if seed is not None else random.randint(1, 2_147_483_647)

        # 2. Apply Controlled Visual Variation (preserves original prompt as primary subject)
        enhanced_prompt = apply_controlled_variation(
            base_prompt=prompt,
            variation_index=variation_index,
            style_preset=style_preset,
            seed=resolved_seed,
        )

        neg_prompt = negative_prompt or DEFAULT_NEGATIVE_PROMPT

        t_start = time.time()
        logger.info(f"Starting image generation (Seed: {resolved_seed})...")

        # 3. Route & Generate through Model Fallback Chain
        raw_img, model_used, provider_used, attempts = self.router.route_and_generate(
            prompt=enhanced_prompt,
            seed=resolved_seed,
            negative_prompt=neg_prompt,
            width=width,
            height=height,
        )

        # 4. Enforce Exact 2048x1152 16:9 Resolution without Stretching
        final_img = enforce_target_resolution(
            img=raw_img,
            target_width=width,
            target_height=height,
        )

        # 5. Save as PNG
        final_img.save(out_path, format="PNG")
        elapsed = time.time() - t_start

        logger.info(
            f"Image saved to: {out_path.resolve()} | "
            f"Model: {model_used} | Size: {final_img.size} | Time: {elapsed:.2f}s"
        )
        return out_path

    def generate_batch(
        self,
        prompt: str,
        count: int,
        output_dir: str | Path,
        base_seed: int | None = None,
        style_preset: str | None = None,
        negative_prompt: str | None = None,
    ) -> list[Path]:
        """Generates a sequence of uniquely varied, sequential images (1.png, 2.png, 3.png...).
        
        Args:
            prompt: Base text prompt.
            count: Number of images to generate.
            output_dir: Directory where 1.png, 2.png... will be saved.
            base_seed: Optional base seed; if provided, each image gets base_seed + i.
            style_preset: Optional forced style preset ("rain", "ocean", or None).
        
        Returns:
            List of generated file paths.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[Path] = []

        logger.info(f"Generating batch of {count} images in '{out_dir}'...")
        for i in range(1, count + 1):
            target_file = out_dir / f"{i}.png"
            img_seed = (base_seed + i) if base_seed is not None else random.randint(1, 2_147_483_647)
            # Cycle through controlled variation profiles
            variation_idx = i - 1

            saved_path = self.generate(
                prompt=prompt,
                width=TARGET_WIDTH,
                height=TARGET_HEIGHT,
                output=target_file,
                seed=img_seed,
                style_preset=style_preset,
                variation_index=variation_idx,
                negative_prompt=negative_prompt,
            )
            results.append(saved_path)

        return results


def create_generator(provider: str = "huggingface") -> BaseImageGenerator:
    """Factory creating the appropriate image generator."""
    p_lower = str(provider).lower()
    if p_lower in {"huggingface", "hf", "default", "env"}:
        return HuggingFaceImageGenerator()
    if p_lower in {"placeholder", "offline"}:
        return PlaceholderImageGenerator()
    # Default to HuggingFace
    return HuggingFaceImageGenerator()
