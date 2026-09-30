from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from huggingface_hub import InferenceClient, get_token

# ==============================================================================
# YT-1M Automation: Hugging Face Video Generation Engine Test
# ==============================================================================

ROOT = Path(__file__).resolve().parent
TEMP_DIR = ROOT / "temp"
OUTPUT_DIR = ROOT / "output"
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 1. Rain Master Prompt Generator
def build_rain_video_prompt(theme_name: str = "Midnight Cabin Heavy Rain") -> str:
    """
    Creates a photorealistic cinematic prompt tailored for video AI generation.
    Optimized for slow, relaxing ambience movements without sudden jumps.
    """
    prompt = (
        f"Cinematic photorealistic ambience video of {theme_name}. "
        "Dark cozy wooden cabin interior, warm amber lamp light glowing inside, "
        "large glass window with heavy rain drops dripping and sliding down the pane. "
        "Outside is dark misty pine forest, subtle gentle rain falling continuously, "
        "soft atmospheric fog, perfectly calm relaxing nighttime, high fidelity 4k photography, "
        "seamless looping motion, slow and peaceful ambience."
    )
    return prompt


def request_hf_video(
    prompt: str,
    output_path: Path,
    model: str = "Wan-AI/Wan2.1-T2V-1.3B",
    provider: str | None = None,
) -> bool:
    """
    Sends request to Hugging Face AI model for video generation.
    Returns True if video was successfully downloaded and saved, False otherwise.
    """
    token = get_token()
    print("=" * 60)
    print("🚀 [HUGGING FACE VIDEO GENERATION TEST]")
    print(f"📌 Prompt: {prompt[:90]}...")
    print(f"🤖 Model: {model}")
    print(f"🌐 Provider: {provider or 'Auto / HF Default'}")
    print(f"🔑 Token detected: {'Yes (Length: ' + str(len(token)) + ')' if token else 'No'}")
    print("=" * 60)

    try:
        # Initialize client with user's HF token
        client_kwargs = {"token": token, "timeout": 120}
        if provider:
            client_kwargs["provider"] = provider

        client = InferenceClient(**client_kwargs)

        print("\n⏳ Sending video generation request to Hugging Face...")
        t_start = time.time()

        # Call text_to_video
        video_bytes = client.text_to_video(
            prompt=prompt,
            model=model,
            num_frames=16,
        )

        elapsed = time.time() - t_start
        output_path.write_bytes(video_bytes)

        print(f"✅ Video generated successfully in {elapsed:.1f}s!")
        print(f"📁 Saved to: {output_path.resolve()} ({len(video_bytes):,} bytes)")
        return True

    except Exception as exc:
        print("\n❌ Hugging Face Video Request Error:")
        print(f"Error Type: {type(exc).__name__}")
        print(f"Details: {exc}")
        return False


if __name__ == "__main__":
    test_video_path = TEMP_DIR / "hf_rain_sample.mp4"
    master_prompt = build_rain_video_prompt("Midnight Cabin Heavy Rain")
    
    # Test 1: Try default Wan-AI / HunyuanVideo model
    success = request_hf_video(
        prompt=master_prompt,
        output_path=test_video_path,
        model="Wan-AI/Wan2.1-T2V-1.3B",
    )

    if not success:
        print("\n💡 Tip: Video generation on Hugging Face router uses cloud inference providers (Fal.ai, Replicate).")
