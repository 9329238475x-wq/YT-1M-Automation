"""
YT-1M Autonomous Production Pipeline
====================================
Runs headlessly on Kaggle / Cloud:
  1. Picks daily theme (or rotates weekly)
  2. Generates original procedural binaural ambient audio
  3. Fetches 1080p real nature video clip
  4. Renders seamless dissolve crossfade loop to target duration (e.g. 8 hours)
  5. Uploads directly to YouTube channel via Google OAuth
  6. Sends confirmation email with YouTube link & Video ID
  7. Cleans up all temporary and output video files
"""
from __future__ import annotations

import os
import sys
import time
import json
import shutil
import random
import argparse
from pathlib import Path
from datetime import datetime

# Windows encoding safety
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

TEMP_DIR = ROOT / "temp"
OUTPUT_DIR = ROOT / "output"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Import backend engines
from core.config import load_theme
from core.audio_engine.master import generate_master_audio
from core.video_engine.ai_video_engine import (
    build_master_video_prompt,
    generate_real_video_clip,
    render_looped_video_with_audio,
    build_youtube_seo_metadata,
)
from youtube_manager import upload_video_to_channel, load_channels
from notifier import send_upload_success_email


def auto_select_daily_theme() -> str:
    """Selects theme based on day of week or picks randomly from weekly themes."""
    day_map = {
        0: "01_monday_evening_rain",
        1: "02_tuesday_deep_thunder",
        2: "03_wednesday_cozy_cabin_rain",
        3: "04_thursday_rain_on_window",
        4: "05_friday_tin_roof_rain",
        5: "06_saturday_forest_gentle_rain",
        6: "07_sunday_night_sleep_rain",
    }
    today_idx = datetime.now().weekday()
    theme_id = day_map.get(today_idx, "01_monday_evening_rain")
    print(f"[Theme Selection] Today is day {today_idx} -> Theme: {theme_id}")
    return theme_id


def cleanup_all():
    """Frees all disk space from temp/ and output/."""
    print("\n[Auto-Purge] Cleaning up temp/ and output/ to free 100% disk space...")
    for folder in [TEMP_DIR, OUTPUT_DIR]:
        if folder.exists():
            for item in folder.iterdir():
                try:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
    print("      Disk cleanup complete.")


def run_pipeline(
    duration_hours: float = 8.0,
    theme_id: str | None = None,
    channel_id: str = "UC3bOKg56B9cc2shqNrAKlxw",
    privacy: str = "public",
    recipient_email: str = "9329238475x@gmail.com",
):
    start_time = time.time()
    total_seconds = int(duration_hours * 3600)
    dur_display = f"{int(duration_hours)} Hours" if duration_hours >= 1 else f"{int(total_seconds // 60)} Minutes"

    print("=" * 75)
    print("YT-1M AUTONOMOUS KAGGLE / CLOUD PRODUCTION RUNNER")
    print(f"Target Duration : {dur_display} ({total_seconds} seconds)")
    print(f"Target Channel  : {channel_id}")
    print(f"Privacy Mode    : {privacy.upper()}")
    print(f"Alert Email     : {recipient_email}")
    print("=" * 75)

    # 1. Theme Configuration
    if not theme_id or theme_id == "auto":
        theme_id = auto_select_daily_theme()

    config = load_theme(theme_id)
    theme_name = config.get("name", theme_id)
    seed = random.randint(1000, 999999)
    print(f"\n[Step 1/5] Selected Ambience: {theme_name} (Seed: {seed})")

    # 2. Audio Generation
    audio_path = TEMP_DIR / f"{theme_id}_{seed}.wav"
    print(f"\n[Step 2/5] Generating procedural binaural soundscape ({total_seconds}s)...")
    generate_master_audio(total_seconds, audio_path, seed, config)
    print(f"           Audio Ready: {audio_path.name} ({audio_path.stat().st_size:,} bytes)")

    # 3. 1080p Real Nature Moving Video Clip
    clip_path = TEMP_DIR / f"clip_{seed}.mp4"
    print(f"\n[Step 3/5] Fetching real 1080p moving nature clip...")
    prompt = build_master_video_prompt(config)
    success = generate_real_video_clip(prompt, clip_path, theme_config=config, seed=seed)
    if not success or not clip_path.exists():
        raise RuntimeError("Failed to obtain real 1080p moving video clip")
    print(f"           Real Clip Ready: {clip_path.name} ({clip_path.stat().st_size:,} bytes)")

    # 4. Render Seamless Looped Final Video
    final_video = OUTPUT_DIR / f"{theme_id}_{int(duration_hours)}h_{seed}.mp4"
    print(f"\n[Step 4/5] Rendering seamless crossfade loop to {dur_display} with stream-copy...")
    render_looped_video_with_audio(clip_path, audio_path, final_video, total_seconds, seed=seed)
    print(f"           Final Video Exported: {final_video.name}")
    print(f"           File Size: {final_video.stat().st_size / (1024 * 1024):.2f} MB")

    # 5. YouTube SEO Metadata & Upload
    meta = build_youtube_seo_metadata(config, total_seconds)
    title = meta["title"]
    desc = meta["description"]
    tags = meta["tags"]

    print("\n" + "-" * 75)
    print(f"YOUTUBE METADATA:")
    print(f"Title: {title}")
    print(f"Tags : {', '.join(tags[:6])}")
    print("-" * 75)

    print(f"\n[Step 5/5] Uploading to YouTube Channel {channel_id} at Cloud Speed (1 Gbps)...")

    def on_progress(pct: int):
        if pct % 20 == 0 or pct == 100:
            print(f"           Upload Progress: {pct}%")

    upload_res = upload_video_to_channel(
        channel_id=channel_id,
        video_path=final_video,
        title=title,
        description=desc,
        tags=tags,
        privacy=privacy,
        progress_callback=on_progress,
    )

    video_id = upload_res.get("video_id")
    video_url = upload_res.get("url", f"https://youtu.be/{video_id}")
    print(f"\n🎉 SUCCESS! VIDEO IS LIVE ON YOUTUBE!")
    print(f"   Video ID : {video_id}")
    print(f"   Watch URL: {video_url}")

    # 6. Send Email Alert with Confirmed Video ID
    print(f"\n[Email Alert] Sending upload notification to {recipient_email}...")
    try:
        email_sent = send_upload_success_email(
            channel_name="MAN 709",
            channel_id=channel_id,
            video_title=title,
            video_id=video_id,
            privacy=privacy,
            duration_display=dur_display,
            theme_name=theme_name,
            recipient_email=recipient_email,
        )
        if email_sent:
            print(f"           Email notification sent successfully!")
        else:
            print(f"           Notice: Email sending returned False, but video is uploaded.")
    except Exception as e:
        print(f"           Notice on email notification: {e}")

    # 7. Complete Disk Cleanup
    cleanup_all()

    elapsed = time.time() - start_time
    print(f"\n✨ COMPLETE PRODUCTION CYCLE FINISHED IN {elapsed:.1f}s ({elapsed / 60:.1f} minutes)!")
    return {
        "video_id": video_id,
        "video_url": video_url,
        "title": title,
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YT-1M Autonomous Production Pipeline")
    parser.add_argument("--duration_hours", type=float, default=8.0, help="Duration in hours (e.g. 8.0)")
    parser.add_argument("--theme", type=str, default="auto", help="Theme ID or 'auto'")
    parser.add_argument("--channel_id", type=str, default="UC3bOKg56B9cc2shqNrAKlxw", help="YouTube Channel ID")
    parser.add_argument("--privacy", type=str, default="public", help="public or private")
    parser.add_argument("--recipient_email", type=str, default="9329238475x@gmail.com", help="Notification Email")
    args = parser.parse_args()

    run_pipeline(
        duration_hours=args.duration_hours,
        theme_id=args.theme,
        channel_id=args.channel_id,
        privacy=args.privacy,
        recipient_email=args.recipient_email,
    )
