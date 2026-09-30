"""
YT-1M Automation: Rain Sound + Real Video Generator
===================================================

Usage:
  python generate_rain_video.py --theme 01_monday_evening_rain --duration 60

Flow:
  1. Generate original procedural binaural rain audio
  2. Build detailed cinematic video prompt
  3. Get 100% REAL moving 1080p video clip (AI / Real 4K nature footage, NO STATIC IMAGES)
  4. Loop video seamlessly to match audio duration
  5. Export broadcast-ready 1080p MP4 to output/ folder
  6. Automatically clean up temp/ folder
  7. Automatically delete older output videos (keeping only the newest final video)
"""
from __future__ import annotations

import os
import sys
import shutil
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Load .env from backend/
load_dotenv(BACKEND / ".env")

from core.config import load_theme
from core.audio_engine.master import generate_master_audio
from core.video_engine.ai_video_engine import (
    build_master_video_prompt,
    generate_real_video_clip,
    render_looped_video_with_audio,
    build_youtube_seo_metadata,
)

TEMP_DIR = ROOT / "temp"
OUTPUT_DIR = ROOT / "output"
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def cleanup_temp_dir(temp_dir: Path):
    """
    Automatically cleans up temporary WAV, MP4, and frame files from temp/
    after the final video is successfully exported, preventing storage buildup.
    """
    print("\n[Auto-Cleanup] Deleting temporary files from temp/...")
    deleted_count = 0
    bytes_freed = 0
    if temp_dir.exists():
        for item in temp_dir.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    sz = item.stat().st_size
                    item.unlink()
                    deleted_count += 1
                    bytes_freed += sz
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    deleted_count += 1
            except Exception:
                pass
    mb_freed = bytes_freed / (1024 * 1024)
    print(f"      Cleared {deleted_count} temporary items ({mb_freed:.2f} MB freed).")


def cleanup_old_output_videos(output_dir: Path, current_final_video: Path):
    """
    Deletes all older/previous video files from output/,
    keeping strictly ONLY the newest generated final video.
    """
    print("\n[Auto-Cleanup] Cleaning up older videos from output/ (keeping only latest)...")
    deleted_count = 0
    bytes_freed = 0
    current_resolved = current_final_video.resolve()
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_file() and item.resolve() != current_resolved:
                try:
                    sz = item.stat().st_size
                    item.unlink()
                    deleted_count += 1
                    bytes_freed += sz
                except Exception:
                    pass
    mb_freed = bytes_freed / (1024 * 1024)
    if deleted_count > 0:
        print(f"      Removed {deleted_count} older video(s) ({mb_freed:.2f} MB freed).")
    print(f"      Kept ONLY the latest video: {current_final_video.name}")


def main():
    parser = argparse.ArgumentParser(description="YT-1M Rain Sound + Real Video Generator")
    parser.add_argument("--theme", default="01_monday_evening_rain", help="Theme ID")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print("=" * 70)
    print("YT-1M AUTOMATION: RAIN AUDIO + 100% REAL VIDEO GENERATOR")
    print("=" * 70)

    # 1. Load Theme
    config = load_theme(args.theme)
    theme_name = config.get("name", args.theme)
    theme_type = config.get("type", "rain")
    print(f"\n[1/4] Ambience: {theme_name}")
    print(f"      Duration: {args.duration}s ({args.duration // 60}m {args.duration % 60}s)")

    # 2. Generate Rain Audio
    audio_path = TEMP_DIR / f"{args.theme}_{args.seed}.wav"
    print(f"\n[2/4] Generating original binaural rain audio ({args.duration}s)...")
    generate_master_audio(args.duration, audio_path, args.seed, config)
    print(f"      Audio Ready: {audio_path.name} ({audio_path.stat().st_size:,} bytes)")

    # 3. Generate REAL Moving Video Clip (NO STATIC IMAGES)
    clip_path = TEMP_DIR / f"real_video_clip_{args.seed}.mp4"
    print(f"\n[3/4] Fetching REAL 1080p Moving Video Clip for {theme_name}...")
    master_prompt = build_master_video_prompt(config)

    success = generate_real_video_clip(master_prompt, clip_path, theme_config=config, seed=args.seed)
    if not success or not clip_path.exists():
        print("      [ERROR] Could not fetch real video clip.")
        sys.exit(1)

    print(f"      REAL MOVING VIDEO READY: {clip_path.name} ({clip_path.stat().st_size:,} bytes)")

    # 4. Loop Video Seamlessly & Sync with Audio
    final_output = OUTPUT_DIR / f"{args.theme}_{args.duration}s_{args.seed}.mp4"
    print(f"\n[4/4] Looping 1080p video with SEAMLESS DISSOLVE to {args.duration}s and syncing with audio...")
    render_looped_video_with_audio(clip_path, audio_path, final_output, args.duration, seed=args.seed)
    print(f"\n      SUCCESS! 100% REAL VIDEO EXPORTED!")
    print(f"      Path: {final_output.resolve()}")
    print(f"      Size: {final_output.stat().st_size / (1024 * 1024):.2f} MB")

    # 5. Auto Cleanup Temp Folder
    cleanup_temp_dir(TEMP_DIR)

    # 6. Auto Cleanup Old Output Videos (Keep only latest)
    cleanup_old_output_videos(OUTPUT_DIR, final_output)

    # YouTube SEO Metadata
    meta = build_youtube_seo_metadata(config, args.duration)
    print("\n" + "=" * 70)
    print("YOUTUBE METADATA (Auto-Generated)")
    print("=" * 70)
    print(f"TITLE: {meta['title']}")
    print(f"TAGS:  {', '.join(meta['tags'][:6])}")
    print("=" * 70)


if __name__ == "__main__":
    main()
