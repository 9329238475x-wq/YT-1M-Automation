"""
Push YT-1M Autonomous Runner to Kaggle via Kaggle API
=====================================================
"""
import os
import sys
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY_DIR = ROOT / "kaggle_deploy"

USERNAME = os.getenv("KAGGLE_USERNAME", "sonuji93")
KEY = os.getenv("KAGGLE_KEY", "30359df27329878ca4326b93196c3d59")

notebook_path = DEPLOY_DIR / "kaggle_runner.ipynb"
metadata_path = DEPLOY_DIR / "kernel-metadata.json"

if not notebook_path.exists():
    print(f"Error: {notebook_path} not found")
    sys.exit(1)

metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
notebook_text = notebook_path.read_text(encoding="utf-8")

payload = {
    "id": metadata.get("id", f"{USERNAME}/yt-1m-daily-production"),
    "slug": "yt-1m-daily-production",
    "newTitle": metadata.get("title", "YT-1M Daily Production"),
    "text": notebook_text,
    "language": "python",
    "kernelType": "notebook",
    "isPrivate": metadata.get("is_private", "true") in [True, "true", "True"],
    "enableGpu": False,
    "enableTpu": False,
    "enableInternet": True,
    "datasetDataSources": [],
    "competitionSources": [],
    "kernelSources": [],
    "modelSources": [],
}

print(f"Pushing kernel '{payload['id']}' to Kaggle API...")
url = "https://www.kaggle.com/api/v1/kernels/push"

response = requests.post(url, json=payload, auth=(USERNAME, KEY))

print(f"Status Code: {response.status_code}")
try:
    data = response.json()
    print("Response:", json.dumps(data, indent=2))
    if response.status_code == 200:
        url_kernel = data.get("url") or f"https://www.kaggle.com/code/{payload['id']}"
        print(f"\n🎉 SUCCESS! KERNEL PUSHED TO KAGGLE!")
        print(f"👉 Direct URL: {url_kernel}")
        print("Kaggle is now running the kernel in the background!")
except Exception:
    print("Raw Response:", response.text)
