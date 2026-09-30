from huggingface_hub import InferenceClient
from pathlib import Path
import time

PROMPT = """
A peaceful tropical beach at sunrise, gentle ocean waves rolling onto a clean sandy shoreline,
soft golden sunlight reflecting across the water, subtle sea mist in the distance,
natural realistic textures, calm relaxing atmosphere, cinematic photorealistic photography,
highly detailed, soft natural lighting, wide open composition, no people, no buildings,
no boats, no birds, no text, no watermark
"""

MODEL = "Tongyi-MAI/Z-Image-Turbo"

WIDTH = 2048
HEIGHT = 1152

output_dir = Path("output/hf_test")
output_dir.mkdir(parents=True, exist_ok=True)

print("Starting 16:9 image generation...")
print("Model:", MODEL)
print(f"Resolution: {WIDTH}x{HEIGHT}")
print("Please wait...")

start = time.time()

try:
    client = InferenceClient()

    image = client.text_to_image(
        prompt=PROMPT,
        model=MODEL,
        width=WIDTH,
        height=HEIGHT
    )

    output_file = output_dir / "test_16x9_1280x720.png"
    image.save(output_file)

    elapsed = time.time() - start

    print()
    print("=" * 50)
    print("SUCCESS!")
    print("Resolution:", image.size)
    print("Image saved:", output_file.resolve())
    print(f"Time: {elapsed:.1f} seconds")
    print("=" * 50)

except Exception as e:
    print()
    print("=" * 50)
    print("IMAGE GENERATION FAILED")
    print(type(e).__name__)
    print(str(e))
    print("=" * 50)