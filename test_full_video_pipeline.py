from __future__ import annotations

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from huggingface_hub import InferenceClient, get_token

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
TEMP_DIR = ROOT / "temp"
OUTPUT_DIR = ROOT / "output"
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import backend modules
sys.path.insert(0, str(BACKEND))
from core.audio_engine.master import generate_master_audio
from core.config import load_theme


# ==============================================================================
# 1. Master Prompt Generator for Rain Ambience
# ==============================================================================
def create_master_rain_prompt(theme_config: dict) -> dict:
    """
    Generates tailored, high-converting video prompts and YouTube metadata
    based on the specific rain sound recipe.
    """
    theme_name = theme_config.get("name", "Heavy Rain Ambience")
    theme_type = theme_config.get("type", "rain")
    audio_cfg = theme_config.get("audio", {})
    engine_name = audio_cfg.get("engine", "rain")

    # Tailored visual descriptions for different rain types
    prompts_map = {
        "cabin_rain": (
            "Cinematic photorealistic slow-motion video. Dark cozy wooden cabin in pine forest at night, "
            "warm ambient golden light glowing inside, huge glass window overlooking the trees. "
            "Heavy rain pouring down, realistic water droplets slowly streaming and rolling on the glass pane, "
            "mystical gentle fog outside, atmospheric moody lighting, 4K quality, seamless ambient loop, peaceful and calm."
        ),
        "window_rain": (
            "Cinematic macro photorealistic view of cozy bedroom window at midnight. "
            "Heavy rain pouring against the window glass, detailed glistening raindrops trickling down, "
            "blurred city street lights and warm bokeh glowing softly in background, relaxing tranquil atmosphere, "
            "hyper-realistic water physics, 4K resolution, soothing ambient loop."
        ),
        "tin_roof_rain": (
            "Cinematic atmospheric video of a rustic porch with corrugated metal tin roof during torrential downpour. "
            "Water sheets cascading off the tin roof eaves into rain barrels, misty moody evening, "
            "soft lantern glowing warmly, realistic splashing droplets, peaceful meditation ambience, 4k ultra realistic."
        ),
        "forest_rain": (
            "Cinematic nature video of deep lush emerald forest during heavy steady rainstorm. "
            "Raindrops splashing on vibrant green fern leaves, gentle mist rising from mossy forest floor, "
            "tall ancient pine trees swaying gently in breeze, deep relaxing nature ambience, photorealistic 4k."
        ),
        "car_rain": (
            "Cozy intimate POV inside a parked car at night during heavy rainstorm. "
            "Raindrops pelting and sliding down the windshield with wiper off, soft warm dashboard glow, "
            "distant city streetlights blurred in rainy bokeh, ultra cozy sleep ambience, 4k seamless loop."
        ),
    }

    selected_prompt = prompts_map.get(engine_name, prompts_map["cabin_rain"])

    return {
        "theme_name": theme_name,
        "engine": engine_name,
        "video_prompt": selected_prompt,
        "title": f"{theme_name} 🌧️ Rain Sounds for Sleep, Study & Deep Relaxation [4K Ambient Video]",
        "description": (
            f"Immerse yourself in this soothing {theme_name} ambience.\n\n"
            "✨ Pure procedural binaural rain sounds synthesized without copyright strikes.\n"
            "🌧️ Ideal for: Deep Sleep, Insomnia Relief, Studying, Focus, Relaxation & Meditation.\n\n"
            "🎧 Recommended: Use headphones at low to medium volume for maximum relaxation.\n"
            "🔔 Subscribe for daily peaceful sleep & rain ambiences!"
        ),
        "tags": [
            "rain sounds",
            "heavy rain",
            "rain for sleep",
            "cabin rain",
            "rain on window",
            "sleep ambience",
            "relaxing rain",
            "study sounds",
            "white noise",
            "4k rain",
        ],
    }


# ==============================================================================
# 2. Hugging Face AI Video Generation Engine
# ==============================================================================
def generate_ai_video_clip(
    prompt: str,
    output_path: Path,
    model: str = "Wan-AI/Wan2.1-T2V-1.3B",
    timeout: int = 60,
) -> bool:
    """
    Attempts to fetch an AI-generated video clip from Hugging Face.
    Returns True if downloaded successfully, False if payment/quota error or timeout.
    """
    token = get_token()
    print("\n--- [Step 2: Hugging Face AI Video Generator] ---")
    print(f"Model: {model}")
    print("Requesting AI video clip...")

    try:
        client = InferenceClient(token=token, timeout=timeout)
        video_bytes = client.text_to_video(
            prompt=prompt,
            model=model,
            num_frames=16,
        )
        output_path.write_bytes(video_bytes)
        print(f"SUCCESS: AI Video generated from Hugging Face! Saved to {output_path.name}")
        return True
    except Exception as exc:
        print(f"NOTICE: Hugging Face Video API returned: {type(exc).__name__}")
        err_msg = str(exc)
        if "402" in err_msg or "Payment Required" in err_msg or "credits" in err_msg:
            print("REASON: Hugging Face Account does not have active Fal.ai/Replicate credits for video router.")
        else:
            print(f"REASON: {err_msg[:120]}...")
        return False


# ==============================================================================
# 3. Dynamic Visual Fallback Clip (Zero-Failure Guarantee)
# ==============================================================================
def create_fallback_video_clip(image_path: Path, output_clip_path: Path, duration: int = 10) -> Path:
    """
    If HF API credits are exhausted, creates an ultra-smooth cinematic 1080p
    video clip from high-res image with subtle slow camera zoom (Ken Burns effect)
    so the automation never breaks.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg not found in PATH")

    output_clip_path.parent.mkdir(parents=True, exist_ok=True)
    # 10 second subtle zoom clip
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-t", str(duration),
        "-vf", "zoompan=z='min(zoom+0.0005,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=300:s=1920x1080:fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "19",
        str(output_clip_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_clip_path


# ==============================================================================
# 4. Seamless Video Looper & Audio Sync Engine
# ==============================================================================
def render_looped_final_video(
    video_clip_path: Path,
    audio_path: Path,
    final_output_path: Path,
    target_duration_seconds: int,
) -> Path:
    """
    Loops the video clip seamlessly to match the exact duration of the audio,
    syncing them into a broadcast-ready MP4.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg not found in PATH")

    print(f"\n--- [Step 3: Seamless Video Looper & Audio Sync] ---")
    print(f"Video source: {video_clip_path.name}")
    print(f"Audio source: {audio_path.name}")
    print(f"Target duration: {target_duration_seconds}s")
    print("Looping video to match audio duration...")

    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # -stream_loop -1 loops the video infinitely
    # -shortest cuts the output as soon as the audio ends
    # -t target_duration_seconds ensures exact duration
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(video_clip_path),
        "-i", str(audio_path),
        "-t", str(target_duration_seconds),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(final_output_path),
    ]

    t_start = time.time()
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elapsed = time.time() - t_start

    print(f"SUCCESS: Final synced video rendered in {elapsed:.1f}s!")
    print(f"Saved to: {final_output_path.resolve()}")
    return final_output_path


# ==============================================================================
# 5. Full Pipeline Test Execution
# ==============================================================================
def main():
    print("=" * 70)
    print("🎬 YT-1M AUTOMATION: FULL RAIN SOUND + VIDEO LOOPER PIPELINE TEST")
    print("=" * 70)

    # Test settings
    theme_id = "01_monday_evening_rain"
    test_duration_seconds = 30  # 30 seconds test run
    seed = 42

    # Step 1: Load Theme Config & Generate Master Prompt
    config = load_theme(theme_id)
    metadata = create_master_rain_prompt(config)

    print("\n--- [Step 1: Sound Recipe & Master Video Prompt] ---")
    print(f"Ambience: {metadata['theme_name']}")
    print(f"Master Video Prompt:\n\"{metadata['video_prompt']}\"")

    # Step 2: Generate Original Rain Audio
    audio_path = TEMP_DIR / f"test_rain_audio_{seed}.wav"
    print(f"\nGenerating {test_duration_seconds}s procedural rain audio...")
    generate_master_audio(test_duration_seconds, audio_path, seed, config)
    print(f"Audio ready: {audio_path.name} ({audio_path.stat().st_size:,} bytes)")

    # Step 3: Video Clip Generation (HF AI with fallback)
    video_clip_path = TEMP_DIR / "ai_video_clip.mp4"
    hf_success = generate_ai_video_clip(
        prompt=metadata["video_prompt"],
        output_path=video_clip_path,
        model="Wan-AI/Wan2.1-T2V-1.3B",
        timeout=15,
    )

    if not hf_success:
        print("Using High-Quality Visual Engine to generate base video clip...")
        # Create atmospheric image
        from core.image_engine.generator import create_generator
        image_path = TEMP_DIR / "test_rain_scene.png"
        create_generator("placeholder").generate(metadata["video_prompt"], 1920, 1080, image_path)
        create_fallback_video_clip(image_path, video_clip_path, duration=10)
        print(f"Generated 10-second atmospheric video clip: {video_clip_path.name}")

    # Step 4: Seamless Looping & Audio Sync
    final_video_path = OUTPUT_DIR / f"final_rain_video_synced_{seed}.mp4"
    render_looped_final_video(
        video_clip_path=video_clip_path,
        audio_path=audio_path,
        final_output_path=final_video_path,
        target_duration_seconds=test_duration_seconds,
    )

    # Step 5: Generated YouTube Metadata Preview
    print("\n" + "=" * 70)
    print("📺 READY FOR YOUTUBE UPLOAD: GENERATED METADATA")
    print("=" * 70)
    print(f"📌 TITLE:\n{metadata['title']}\n")
    print(f"📝 DESCRIPTION:\n{metadata['description']}\n")
    print(f"🏷️ TAGS: {', '.join(metadata['tags'])}")
    print(f"📁 FINAL VIDEO FILE: {final_video_path.resolve()}")
    print(f"📊 FILE SIZE: {final_video_path.stat().st_size / (1024 * 1024):.2f} MB")
    print("=" * 70)


if __name__ == "__main__":
    main()
