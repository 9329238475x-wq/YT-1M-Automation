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


from datetime import datetime, timezone


def auto_select_daily_theme(slot: str = "auto") -> tuple[str, str]:
    """
    Selects theme based on USA target time & day of the week:
      - Morning Slot (USA 6:00 AM - 12:00 PM) -> Morning Ocean Waves & Sunrise Meditation
      - Evening Slot (USA 7:00 PM - 11:00 PM) -> Evening Deep Rain & Night Sleep Thunder
    """
    now_utc = datetime.now(timezone.utc)
    # Target USA Eastern Time (New York / EDT = UTC - 4)
    us_hour = (now_utc.hour - 4) % 24

    if slot not in ["morning", "evening"]:
        # Auto-detect based on US Eastern daytime vs evening/night
        slot = "morning" if (5 <= us_hour < 14) else "evening"

    today_idx = now_utc.weekday()

    ocean_map = {
        0: "01_monday_morning_ocean",
        1: "02_tuesday_morning_ocean",
        2: "03_wednesday_morning_ocean",
        3: "04_thursday_morning_ocean",
        4: "05_friday_morning_ocean",
        5: "06_saturday_morning_ocean",
        6: "07_sunday_morning_ocean",
    }

    rain_map = {
        0: "01_monday_evening_rain",
        1: "02_tuesday_evening_rain",
        2: "03_wednesday_evening_rain",
        3: "04_thursday_evening_rain",
        4: "05_friday_evening_rain",
        5: "06_saturday_evening_rain",
        6: "07_sunday_evening_rain",
    }

    theme_id = ocean_map.get(today_idx, "01_monday_morning_ocean") if slot == "morning" else rain_map.get(today_idx, "01_monday_evening_rain")
    slot_label = "MORNING SUNRISE OCEAN" if slot == "morning" else "EVENING DEEP SLEEP RAIN"
    print(f"\n[USA Smart Target] US Eastern Time: {us_hour:02d}:{now_utc.minute:02d}")
    print(f"                   Scheduled Slot : {slot_label}")
    print(f"                   Selected Theme : {theme_id} (Day {today_idx})")
    return theme_id, slot


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
    duration_hours: float = 12.0,
    theme_id: str | None = None,
    slot: str = "auto",
    channel_id: str = "all",
    privacy: str = "public",
    recipient_email: str = "9329238475x@gmail.com",
):
    start_time = time.time()
    base_seconds = int(duration_hours * 3600)

    # Hardware acceleration detection (GPU NVIDIA T4 / CPU Fallback)
    hw_mode = "CPU"
    try:
        import torch
        if torch.cuda.is_available():
            hw_mode = f"NVIDIA GPU ({torch.cuda.get_device_name(0)})"
    except Exception:
        pass

    # 1. Resolve Target Channel(s)
    if channel_id == "all":
        all_ch = load_channels()
        channels_to_process = [c for c in all_ch if c.get("status") == "connected"]
        if not channels_to_process:
            channels_to_process = [{"id": "UC3bOKg56B9cc2shqNrAKlxw", "title": "MAN 709"}]
    else:
        channels_to_process = [{"id": channel_id, "title": "Target Channel"}]

    print(f"\n[Multi-Channel Hub] Active Channels for 2X Daily Production: {len(channels_to_process)}")
    for c in channels_to_process:
        print(f"                    -> {c.get('title', 'Channel')} ({c.get('id')})")

    results = []

    # 2. Process each channel independently with unique seed & variations
    for ch_idx, target_ch in enumerate(channels_to_process, 1):
        curr_chan_id = target_ch.get("id")
        curr_chan_title = target_ch.get("title", f"Channel {ch_idx}")

        print("\n" + "=" * 75)
        print(f">>> [Channel {ch_idx}/{len(channels_to_process)}] {curr_chan_title} ({curr_chan_id})")
        print("=" * 75)

        # 1. Theme Configuration & USA Slot Resolution
        if not theme_id or theme_id == "auto":
            curr_theme_id, resolved_slot = auto_select_daily_theme(slot=slot)
        else:
            curr_theme_id = theme_id
            resolved_slot = "custom"

        config = load_theme(curr_theme_id)
        theme_name = config.get("name", curr_theme_id)

        # Unique seed per channel + render prevents any cross-channel duplicate content!
        seed = (random.randint(1000, 999999) + abs(hash(curr_chan_id))) % 1000000

        # Unique natural duration variation (+1m 15s to +11m 45s) per channel
        # Ensures even across multiple channels, no two videos ever share identical timestamps
        random_offset_seconds = random.randint(75, 705)
        total_seconds = base_seconds + random_offset_seconds
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        dur_exact_timestamp = f"{h:02d}:{m:02d}:{s:02d}"
        dur_display = f"{int(duration_hours)} Hours" if duration_hours >= 1 else f"{int(total_seconds // 60)} Minutes"

        print(f"Production Slot  : {resolved_slot.upper()}")
        print(f"Ambience Theme   : {theme_name} (Seed: {seed})")
        print(f"Target Duration  : {dur_display} (Exact: {dur_exact_timestamp})")
        print(f"Hardware Engine  : {hw_mode} (Automatic Fallback Active)")
        print(f"Privacy Mode     : {privacy.upper()}")
        print(f"Alert Email      : {recipient_email}")

        # 2. Audio Generation (5-minute rich procedural binaural master, looped seamlessly by FFmpeg)
        audio_dur = min(total_seconds, 300)
        audio_path = TEMP_DIR / f"{curr_theme_id}_{seed}.wav"
        print(f"\n[Step 2/5] Generating procedural binaural soundscape master ({audio_dur}s block)...")
        generate_master_audio(audio_dur, audio_path, seed, config)
        print(f"           Audio Master Ready: {audio_path.name} ({audio_path.stat().st_size:,} bytes)")

        # 3. 1080p Real Nature Moving Video Clip
        clip_path = TEMP_DIR / f"clip_{seed}.mp4"
        print(f"\n[Step 3/5] Fetching real 1080p moving nature clip...")
        prompt = build_master_video_prompt(config)
        success = generate_real_video_clip(prompt, clip_path, theme_config=config, seed=seed)
        if not success or not clip_path.exists():
            raise RuntimeError("Failed to obtain real 1080p moving video clip")
        print(f"           Real Clip Ready: {clip_path.name} ({clip_path.stat().st_size:,} bytes)")

        # 4. Render Seamless Looped Final Video
        final_video = OUTPUT_DIR / f"{curr_theme_id}_{int(duration_hours)}h_{seed}.mp4"
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

        print(f"\n[Step 5/5] Uploading to YouTube Channel {curr_chan_title} ({curr_chan_id}) at Cloud Speed (1 Gbps)...")

        def on_progress(pct: int):
            if pct % 20 == 0 or pct == 100:
                print(f"           Upload Progress: {pct}%")

        upload_res = upload_video_to_channel(
            channel_id=curr_chan_id,
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
        print(f"   Channel  : {curr_chan_title}")
        print(f"   Video ID : {video_id}")
        print(f"   Watch URL: {video_url}")

        # 6. Send Email Alert with Confirmed Video ID
        print(f"\n[Email Alert] Sending upload notification to {recipient_email}...")
        try:
            email_sent = send_upload_success_email(
                channel_name=curr_chan_title,
                channel_id=curr_chan_id,
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

        # 7. Complete Disk Cleanup for this channel
        cleanup_all()

        results.append({
            "channel_id": curr_chan_id,
            "channel_title": curr_chan_title,
            "video_id": video_id,
            "video_url": video_url,
            "title": title,
        })

    elapsed = time.time() - start_time
    print(f"\n✨ COMPLETE PRODUCTION CYCLE FINISHED IN {elapsed:.1f}s ({elapsed / 60:.1f} minutes)!")
    return {
        "results": results,
        "total_channels": len(results),
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YT-1M Autonomous Production Pipeline")
    parser.add_argument("--duration_hours", type=float, default=12.0, help="Duration in hours (e.g. 12.0)")
    parser.add_argument("--theme", type=str, default="auto", help="Theme ID or 'auto'")
    parser.add_argument("--slot", type=str, default="auto", choices=["auto", "morning", "evening"], help="Target slot: morning (ocean) or evening (rain)")
    parser.add_argument("--channel_id", type=str, default="all", help="YouTube Channel ID or 'all' for all connected channels")
    parser.add_argument("--privacy", type=str, default="public", help="public or private")
    parser.add_argument("--recipient_email", type=str, default="9329238475x@gmail.com", help="Notification Email")
    args = parser.parse_args()

    run_pipeline(
        duration_hours=args.duration_hours,
        theme_id=args.theme,
        slot=args.slot,
        channel_id=args.channel_id,
        privacy=args.privacy,
        recipient_email=args.recipient_email,
    )
