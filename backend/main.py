from __future__ import annotations

import argparse
from pathlib import Path

from core.config import load_theme
from core.audio_engine.master import generate_master_audio
from core.image_engine.generator import create_generator
from core.image_engine.prompts import monday_prompt
from core.video_engine.ffmpeg_render import render_static_image_video

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / "output"
TEMP = ROOT.parent / "temp"


def run(theme_id: str, duration_seconds: int, seed: int, render_video: bool) -> None:
    config = load_theme(theme_id)
    OUTPUT.mkdir(exist_ok=True)
    TEMP.mkdir(exist_ok=True)

    audio_path = TEMP / f"{theme_id}_{seed}.wav"
    image_path = TEMP / f"{theme_id}_{seed}.png"
    video_path = OUTPUT / f"{theme_id}_{seed}.mp4"

    print(f"[1/3] Generating audio: {duration_seconds}s")
    generate_master_audio(duration_seconds, audio_path, seed, config)

    print("[2/3] Generating image")
    prompt = monday_prompt(seed) if theme_id == "01_monday" else "cinematic ambience scene"
    provider = config["image"].get("provider", "placeholder")
    create_generator("placeholder" if provider == "env" else provider).generate(
        prompt, config["image"]["width"], config["image"]["height"], image_path
    )

    if render_video:
        print("[3/3] Rendering video with FFmpeg")
        render_static_image_video(image_path, audio_path, video_path, duration_seconds)
        print(f"Done: {video_path}")
    else:
        print("[3/3] Video rendering skipped")


def main() -> None:
    parser = argparse.ArgumentParser(description="YT-1M ambience automation")
    parser.add_argument("--theme", default="01_monday")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    run(args.theme, args.duration, args.seed, args.render)


if __name__ == "__main__":
    main()
