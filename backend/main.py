from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.config import load_theme
from core.audio_engine.master import generate_master_audio
from core.image_engine.generator import create_generator
from core.image_engine.prompts import monday_prompt
from core.video_engine.ffmpeg_render import render_static_image_video
from core.video_engine.ai_video_engine import (
    build_master_video_prompt,
    generate_hf_video_clip,
    create_dynamic_kenburns_clip,
    render_looped_video_with_audio,
    build_youtube_seo_metadata,
)

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
    clip_path = TEMP / f"clip_{theme_id}_{seed}.mp4"

    print(f"[1/3] Generating audio: {duration_seconds}s")
    generate_master_audio(duration_seconds, audio_path, seed, config)

    print("[2/3] Generating visuals & master video prompt")
    master_prompt = build_master_video_prompt(config)
    provider = config.get("image", {}).get("provider", "placeholder")
    create_generator("placeholder" if provider == "env" else provider).generate(
        master_prompt, config.get("image", {}).get("width", 1920), config.get("image", {}).get("height", 1080), image_path
    )

    if render_video:
        print("[3/3] Generating video clip & looping seamlessly to audio duration")
        hf_ok = generate_hf_video_clip(master_prompt, clip_path, timeout=30)
        if not hf_ok:
            print("  (HF video API unavailable or depleted; using high-res visual motion engine)")
            create_dynamic_kenburns_clip(image_path, clip_path, duration_seconds=10)
        render_looped_video_with_audio(clip_path, audio_path, video_path, duration_seconds)
        meta = build_youtube_seo_metadata(config, duration_seconds)
        print(f"Done: {video_path}")
        print(f"YouTube Title: {meta['title']}")
    else:
        print("[3/3] Video rendering skipped")


def main() -> None:
    parser = argparse.ArgumentParser(description="YT-1M ambience automation")
    parser.add_argument("--theme", default="01_monday_evening_rain")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    run(args.theme, args.duration, args.seed, args.render)


if __name__ == "__main__":
    main()
