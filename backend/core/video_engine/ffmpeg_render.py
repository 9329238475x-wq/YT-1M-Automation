from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render_static_image_video(image: str | Path, audio: str | Path, output: str | Path, duration_seconds: int) -> Path:
    """Render a test/fallback video. The production visual engine will provide the animated source."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg was not found in PATH")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-t", str(duration_seconds), "-r", "30", "-vf", """scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2""",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)
    ]
    subprocess.run(cmd, check=True)
    return out
