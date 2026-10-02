"""
Push / Trigger YT-1M Autonomous Runner on Kaggle via Kaggle CLI
Works seamlessly locally AND in GitHub Actions (without leaking secrets to GitHub)!
"""
import os
import sys
import re
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY_DIR = ROOT / "kaggle_deploy"

parser = argparse.ArgumentParser(description="Push / Trigger YT-1M Runner on Kaggle")
parser.add_argument("--slot", type=str, default="auto", choices=["auto", "morning", "evening", "dual"], help="Target production slot: morning (ocean), evening (rain), dual, or auto")
args = parser.parse_args()

print("=" * 65)
print(f"🚀 [YT-1M AUTONOMOUS CLOUD TRIGGER] INITIATING RUNNER (SLOT: {args.slot.upper()})")
print("=" * 65)

# If kaggle_deploy exists locally, push directly
if DEPLOY_DIR.exists() and (DEPLOY_DIR / "kaggle_runner.py").exists():
    print(f"Deploying from local package: {DEPLOY_DIR}")
    target_dir = DEPLOY_DIR
else:
    # Running in GitHub Actions: pull current private kernel from Kaggle and re-push
    print("Running in GitHub Actions cloud runner...")
    target_dir = ROOT / "temp_deploy"
    shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    print("Pulling current private kernel & metadata from Kaggle...")
    r_pull = subprocess.run(
        ["kaggle", "kernels", "pull", "sonuji93/yt-1m-daily-production", "-p", str(target_dir), "-m"],
        capture_output=True, text=True
    )
    if r_pull.returncode != 0:
        print(f"Error pulling kernel: {r_pull.stderr}")
        sys.exit(r_pull.returncode)
    print("✓ Successfully pulled private kernel configuration!")

# Configure slot in kaggle_runner.py if specified
if args.slot != "auto":
    runner_script = target_dir / "kaggle_runner.py"
    if runner_script.exists():
        content = runner_script.read_text(encoding="utf-8")
        new_content = re.sub(r'("--slot",\s*)"[^"]*"', rf'\1"{args.slot}"', content)
        runner_script.write_text(new_content, encoding="utf-8")
        print(f"✓ Configured Kaggle runner for slot: {args.slot.upper()}")

print("Triggering Kaggle kernel execution...")
res = subprocess.run(["kaggle", "kernels", "push", "-p", str(target_dir)], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)

# Cleanup temp_deploy if created
if (ROOT / "temp_deploy").exists():
    shutil.rmtree(ROOT / "temp_deploy", ignore_errors=True)

if res.returncode == 0:
    print("\n🎉 SUCCESS! KERNEL TRIGGERED ON KAGGLE!")
    print("👉 Direct URL: https://www.kaggle.com/code/sonuji93/yt-1m-daily-production")
    print("Kaggle is now running the daily 12-hour dual production in the background!")
else:
    sys.exit(res.returncode)
