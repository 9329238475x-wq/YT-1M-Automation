from __future__ import annotations

from PIL import Image


def enforce_target_resolution(
    img: Image.Image,
    target_width: int = 2048,
    target_height: int = 1152,
) -> Image.Image:
    """Enforces exact 2048x1152 16:9 resolution using aspect-ratio-preserving scaling.
    
    Guarantees:
    - NEVER stretches or distorts the image.
    - If native resolution is already 2048x1152, passes through directly.
    - If aspect ratio is 16:9 (e.g. 1024x576, 1280x720, 1920x1080), performs high-quality Lanczos upscale.
    - If aspect ratio differs (e.g. 1:1, 4:3, 3:2), scales so the target frame is completely covered,
      then cleanly center-crops the minimal excess.
    - Converts to standard RGB.
    """
    if img.mode != "RGB":
        img = img.convert("RGB")

    cur_w, cur_h = img.size
    if cur_w == target_width and cur_h == target_height:
        return img

    target_ar = float(target_width) / float(target_height)
    cur_ar = float(cur_w) / float(cur_h)

    # If within 0.5% of 16:9, direct high-quality Lanczos resize without cropping
    if abs(cur_ar - target_ar) < 0.005:
        return img.resize((target_width, target_height), resample=Image.Resampling.LANCZOS)

    # Aspect-preserving scale + minimal center crop
    if cur_ar > target_ar:
        # Input is wider than 16:9 -> match height, crop excess horizontal sides
        scale = target_height / float(cur_h)
        scaled_w = int(round(cur_w * scale))
        scaled_h = target_height
        resized = img.resize((scaled_w, scaled_h), resample=Image.Resampling.LANCZOS)
        left = max(0, (scaled_w - target_width) // 2)
        right = left + target_width
        return resized.crop((left, 0, right, target_height))
    else:
        # Input is taller than 16:9 (e.g. 1:1, 4:3) -> match width, crop excess vertical top/bottom
        scale = target_width / float(cur_w)
        scaled_w = target_width
        scaled_h = int(round(cur_h * scale))
        resized = img.resize((scaled_w, scaled_h), resample=Image.Resampling.LANCZOS)
        top = max(0, (scaled_h - target_height) // 2)
        bottom = top + target_height
        return resized.crop((0, top, target_width, bottom))
