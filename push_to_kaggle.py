"""
Push YT-1M Autonomous Runner to Kaggle via Kaggle CLI
=====================================================
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY_DIR = ROOT / "kaggle_deploy"

print("Deploying kernel to Kaggle via official Kaggle CLI...")
res = subprocess.run(["kaggle", "kernels", "push", "-p", str(DEPLOY_DIR)], capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print(res.stderr)

if res.returncode == 0:
    print("\n🎉 SUCCESS! KERNEL PUSHED TO KAGGLE!")
    print("👉 Direct URL: https://www.kaggle.com/code/sonuji93/yt-1m-daily-production")
    print("Kaggle is now running the kernel in the background!")
else:
    sys.exit(res.returncode)

