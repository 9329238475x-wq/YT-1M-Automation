from __future__ import annotations

from pathlib import Path


def upload_video(video_path: str | Path, metadata: dict, publish_at: str | None = None) -> None:
    """Placeholder for OAuth + resumable YouTube upload.

    Credentials are deliberately not stored in source control. Production upload
    will use environment/secret storage and googleapiclient's resumable upload.
    """
    raise NotImplementedError("YouTube upload engine will be enabled after OAuth setup")
