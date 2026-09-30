#!/usr/bin/env python3
"""
CLI Test Script for YT-1M-Automation Image Engine
------------------------------------------------
Usage:
    python test_image_engine.py
    python test_image_engine.py --prompt "A cozy wooden cabin in the woods during rain..."
    python test_image_engine.py --batch 3 --output-dir output/images/batch_test
"""

import sys
import argparse
import time
from pathlib import Path
from PIL import Image

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if (PROJECT_ROOT / "backend").exists():
    sys.path.insert(0, str(PROJECT_ROOT))
    from backend.core.image_engine.generator import HuggingFaceImageGenerator
    from backend.core.image_engine.config import TARGET_WIDTH, TARGET_HEIGHT, PRIMARY_MODEL, IMAGE_MODELS
else:
    # Running from local scratch workspace
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from image_engine_generator import HuggingFaceImageGenerator
        from image_engine_config import TARGET_WIDTH, TARGET_HEIGHT, PRIMARY_MODEL, IMAGE_MODELS
    except ImportError:
        alt_root = Path(r"C:\Users\HDD WORK\Downloads\YT-1M-Automation-main")
        sys.path.insert(0, str(alt_root))
        from backend.core.image_engine.generator import HuggingFaceImageGenerator
        from backend.core.image_engine.config import TARGET_WIDTH, TARGET_HEIGHT, PRIMARY_MODEL, IMAGE_MODELS

# Default user test prompt (from Section 20 of specification)
DEFAULT_TEST_PROMPT = (
    "A peaceful tropical beach at sunrise, gentle ocean waves rolling onto a clean sandy shoreline, "
    "soft golden sunlight reflecting across the water, subtle sea mist in the distance, "
    "natural realistic textures, calm relaxing atmosphere, cinematic photorealistic photography, "
    "highly detailed, soft natural lighting, wide open composition, no people, no buildings, "
    "no boats, no birds, no text, no watermark"
)


def main():
    parser = argparse.ArgumentParser(description="Test Image Engine (2048x1152 16:9 PNG)")
    parser.add_argument("--prompt", type=str, default=DEFAULT_TEST_PROMPT, help="Text prompt for image generation")
    parser.add_argument("--output", type=str, default="output/images/test_output.png", help="Output PNG path")
    parser.add_argument("--seed", type=int, default=None, help="Optional generation seed")
    parser.add_argument("--style", type=str, default=None, choices=["rain", "ocean", "general"], help="Optional style preset")
    parser.add_argument("--batch", type=int, default=1, help="Number of images to generate (default: 1)")
    parser.add_argument("--output-dir", type=str, default="output/images/batch_job", help="Batch output directory")
    parser.add_argument("--provider", type=str, default="huggingface", choices=["huggingface", "placeholder"], help="Provider to test (huggingface or offline placeholder)")
    args = parser.parse_args()

    print("=" * 60)
    print("YT-1M-AUTOMATION IMAGE ENGINE TEST")
    print("=" * 60)
    print(f"Target Resolution: {TARGET_WIDTH} x {TARGET_HEIGHT} (16:9 PNG)")
    print(f"Provider:          {args.provider.upper()}")
    if args.provider == "huggingface":
        print(f"Primary Model:     {PRIMARY_MODEL}")
        print(f"Fallback Chain:    {' -> '.join(IMAGE_MODELS)} -> AUTO")
    print(f"Prompt:            {args.prompt[:90]}...")
    print("=" * 60)

    if args.provider == "placeholder":
        from backend.core.image_engine.generator import PlaceholderImageGenerator
        engine = PlaceholderImageGenerator()
    else:
        engine = HuggingFaceImageGenerator()
    start_time = time.time()

    if args.batch > 1:
        print(f"\nGenerating batch of {args.batch} sequential images (1.png, 2.png, ...)...")
        saved_files = engine.generate_batch(
            prompt=args.prompt,
            count=args.batch,
            output_dir=args.output_dir,
            base_seed=args.seed,
            style_preset=args.style,
        )
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("BATCH GENERATION COMPLETED SUCCESSFULLY!")
        print(f"Generated: {len(saved_files)} images in {args.output_dir}")
        for p in saved_files:
            img = Image.open(p)
            print(f"  - {p.name}: {img.size} ({img.format})")
        print(f"Total Time: {total_time:.1f} seconds")
        print("=" * 60)

    else:
        out_path = Path(args.output)
        print(f"\nGenerating single image to '{out_path}'...")
        saved_file = engine.generate(
            prompt=args.prompt,
            width=TARGET_WIDTH,
            height=TARGET_HEIGHT,
            output=out_path,
            seed=args.seed,
            style_preset=args.style,
        )
        total_time = time.time() - start_time

        # Verify output image on disk
        img = Image.open(saved_file)
        print("\n" + "=" * 60)
        print("IMAGE GENERATION SUCCESSFUL!")
        print(f"File Saved:  {saved_file.resolve()}")
        print(f"Resolution:  {img.size[0]} x {img.size[1]} (Target: {TARGET_WIDTH} x {TARGET_HEIGHT})")
        print(f"Format:      {img.format}")
        print(f"Total Time:  {total_time:.1f} seconds")
        assert img.size == (TARGET_WIDTH, TARGET_HEIGHT), f"Expected {(TARGET_WIDTH, TARGET_HEIGHT)}, got {img.size}"
        assert img.format == "PNG", f"Expected PNG, got {img.format}"
        print("Verification: PASSED! Exact 2048x1152 16:9 PNG guaranteed.")
        print("=" * 60)


if __name__ == "__main__":
    main()
