from __future__ import annotations

import json
import logging
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("youtube_manager")

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
CHANNELS_FILE = ROOT / "channels.json"
STATE_CACHE_FILE = ROOT / "oauth_pending_states.json"
TOKENS_DIR = ROOT / "tokens"
TOKENS_DIR.mkdir(parents=True, exist_ok=True)
CLIENT_SECRETS_FILE = PROJECT / "client_secrets.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _save_oauth_state(state: str, code_verifier: Optional[str]) -> None:
    if not code_verifier:
        return
    try:
        data = {}
        if STATE_CACHE_FILE.exists():
            try:
                data = json.loads(STATE_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[state] = {
            "code_verifier": code_verifier,
            "created_at": datetime.now().isoformat()
        }
        data["__latest__"] = code_verifier
        STATE_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Failed to persist oauth state: {exc}")


def _get_oauth_verifier(state: Optional[str] = None) -> Optional[str]:
    if not STATE_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_CACHE_FILE.read_text(encoding="utf-8"))
        if state and state in data and isinstance(data[state], dict):
            entry = data.pop(state)
            try:
                STATE_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass
            return entry.get("code_verifier")
        if "__latest__" in data:
            return data.get("__latest__")
    except Exception as exc:
        logger.warning(f"Failed to read oauth state: {exc}")
    return None


def load_channels() -> List[Dict[str, Any]]:
    """Loads all saved YouTube channels from channels.json"""
    if not CHANNELS_FILE.exists():
        return []
    try:
        content = CHANNELS_FILE.read_text(encoding="utf-8").strip()
        if not content:
            return []
        data = json.loads(content)
        if isinstance(data, list):
            return data
        return []
    except Exception as exc:
        logger.error(f"Failed to read channels.json: {exc}")
        return []


def save_channels(channels: List[Dict[str, Any]]) -> None:
    """Saves channels list permanently to channels.json"""
    CHANNELS_FILE.write_text(
        json.dumps(channels, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )


def get_channel(channel_id: str) -> Optional[Dict[str, Any]]:
    channels = load_channels()
    for ch in channels:
        if ch.get("id") == channel_id:
            return ch
    return None


def ensure_client_secrets() -> None:
    """Restores client_secrets.json from GOOGLE_CLIENT_SECRETS_JSON env var if missing."""
    if not CLIENT_SECRETS_FILE.exists():
        env_content = os.getenv("GOOGLE_CLIENT_SECRETS_JSON", "").strip()
        if env_content:
            try:
                CLIENT_SECRETS_FILE.write_text(env_content, encoding="utf-8")
                logger.info("Restored client_secrets.json from GOOGLE_CLIENT_SECRETS_JSON environment variable.")
            except Exception as exc:
                logger.error(f"Failed to write client_secrets.json: {exc}")


def get_auth_url(redirect_uri: str = "http://localhost:8000/api/channels/oauth2callback") -> tuple[str, str]:
    """Generates the Google OAuth authorization URL for YouTube access."""
    ensure_client_secrets()
    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(f"client_secrets.json not found in project root: {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true"
    )
    if getattr(flow, "code_verifier", None):
        _save_oauth_state(state, flow.code_verifier)
    return auth_url, state


def process_oauth_code(
    code: str,
    redirect_uri: str = "http://localhost:8000/api/channels/oauth2callback",
    state: Optional[str] = None,
    owner_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exchanges authorization code for credentials, fetches YouTube channel details,
    saves the refresh token, and updates channels.json.
    """
    ensure_client_secrets()
    if not CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(f"client_secrets.json not found in project root: {CLIENT_SECRETS_FILE}")

    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRETS_FILE),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state
    )
    verifier = _get_oauth_verifier(state)
    if verifier:
        flow.code_verifier = verifier

    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Build YouTube API client
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
    resp = youtube.channels().list(mine=True, part="snippet,statistics,contentDetails").execute()

    items = resp.get("items", [])
    if not items:
        raise ValueError("No YouTube channel found for the authenticated Google Account / Brand Account.")

    channel_item = items[0]
    channel_id = channel_item.get("id")
    snippet = channel_item.get("snippet", {})
    statistics = channel_item.get("statistics", {})

    title = snippet.get("title", f"Channel {channel_id}")
    custom_url = snippet.get("customUrl", "")
    description = snippet.get("description", "")
    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url = (
        thumbnails.get("high", {}).get("url")
        or thumbnails.get("medium", {}).get("url")
        or thumbnails.get("default", {}).get("url")
        or ""
    )
    subscriber_count = statistics.get("subscriberCount", "0")
    video_count = statistics.get("videoCount", "0")

    # Save credentials securely to token file
    token_file = TOKENS_DIR / f"token_{channel_id}.json"
    token_file.write_text(credentials.to_json(), encoding="utf-8")

    # Load existing channels list
    channels = load_channels()
    existing_idx = None
    for idx, ch in enumerate(channels):
        if ch.get("id") == channel_id:
            existing_idx = idx
            break

    default_automation = {
        "enabled": True,
        "theme_mode": "all_weekly",  # "all_weekly", "specific", "rain_only", "ocean_only"
        "theme_id": "01_monday_evening_rain",
        "duration_hours": 2,
        "duration_minutes": 0,
        "schedule_type": "daily",  # "daily", "custom_days", "manual"
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "upload_time": "18:00",
        "privacy": "private"  # "private", "unlisted", "public"
    }

    if existing_idx is not None:
        # Update metadata while preserving existing automation rules
        channel_data = channels[existing_idx]
        channel_data["title"] = title
        channel_data["custom_url"] = custom_url
        channel_data["thumbnail"] = thumbnail_url
        channel_data["subscriber_count"] = subscriber_count
        channel_data["video_count"] = video_count
        channel_data["last_connected"] = datetime.now().isoformat()
        channel_data["token_file"] = str(token_file.relative_to(PROJECT)).replace("\\", "/")
        channel_data["status"] = "connected"
        if owner_email:
            channel_data["owner_email"] = owner_email
        if "automation" not in channel_data:
            channel_data["automation"] = default_automation
        channels[existing_idx] = channel_data
    else:
        channel_data = {
            "id": channel_id,
            "title": title,
            "custom_url": custom_url,
            "description": description[:120],
            "thumbnail": thumbnail_url,
            "subscriber_count": subscriber_count,
            "video_count": video_count,
            "tool_uploads_count": 0,
            "connected_at": datetime.now().isoformat(),
            "last_connected": datetime.now().isoformat(),
            "token_file": str(token_file.relative_to(PROJECT)).replace("\\", "/") if token_file.is_relative_to(PROJECT) else str(token_file),
            "status": "connected",
            "owner_email": owner_email or "",
            "automation": default_automation
        }
        channels.append(channel_data)

    save_channels(channels)
    return channel_data


def update_channel_settings(channel_id: str, new_automation: Dict[str, Any]) -> Dict[str, Any]:
    """Updates automation settings for a specific channel and persists it."""
    channels = load_channels()
    target_idx = None
    for idx, ch in enumerate(channels):
        if ch.get("id") == channel_id:
            target_idx = idx
            break

    if target_idx is None:
        raise KeyError(f"Channel {channel_id} not found")

    cur_automation = channels[target_idx].get("automation", {})
    # Update provided keys
    for k, v in new_automation.items():
        cur_automation[k] = v

    channels[target_idx]["automation"] = cur_automation
    channels[target_idx]["updated_at"] = datetime.now().isoformat()
    save_channels(channels)
    return channels[target_idx]


def delete_channel(channel_id: str) -> bool:
    """Removes a channel and deletes its token file."""
    channels = load_channels()
    target = None
    new_list = []
    for ch in channels:
        if ch.get("id") == channel_id:
            target = ch
        else:
            new_list.append(ch)

    if target is None:
        return False

    save_channels(new_list)

    # Remove token file if present
    token_file = TOKENS_DIR / f"token_{channel_id}.json"
    if token_file.exists():
        try:
            token_file.unlink()
        except Exception as exc:
            logger.warning(f"Could not remove token file {token_file}: {exc}")

    return True


def get_channel_credentials(channel_id: str) -> Optional[Credentials]:
    """Loads Credentials for a channel, automatically refreshing if needed."""
    token_file = TOKENS_DIR / f"token_{channel_id}.json"
    if not token_file.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds
    except Exception as exc:
        logger.error(f"Error loading credentials for {channel_id}: {exc}")
        return None


def upload_video_to_channel(
    channel_id: str,
    video_path: Path | str,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy: str = "private",
    category_id: str = "10",
    progress_callback: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Uploads a video to YouTube using the authenticated credentials for the given channel.
    Automatically increments tool_uploads_count in channels.json on success.
    """
    v_path = Path(video_path)
    if not v_path.exists():
        raise FileNotFoundError(f"Video file not found at {v_path}")

    creds = get_channel_credentials(channel_id)
    if not creds:
        raise ValueError(f"No valid YouTube credentials found for channel: {channel_id}. Please connect OAuth.")

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30] if tags else ["rain sounds", "sleep sounds", "meditation"],
            "categoryId": category_id or "10",
        },
        "status": {
            "privacyStatus": privacy if privacy in ["private", "unlisted", "public"] else "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    logger.info(f"Initiating YouTube video upload to channel {channel_id}: {title} (Privacy: {privacy})")
    media = MediaFileUpload(
        str(v_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.info(f"Uploading {channel_id} video: {pct}%")
            if progress_callback:
                try:
                    progress_callback(pct)
                except Exception:
                    pass

    if progress_callback:
        try:
            progress_callback(100)
        except Exception:
            pass

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError(f"YouTube upload finished but returned no video ID: {response}")

    logger.info(f"SUCCESS: Video uploaded to YouTube with ID: {video_id}")

    # Update tool_uploads_count and last upload in channels.json
    channels = load_channels()
    ch_found = False
    for ch in channels:
        if ch.get("id") == channel_id:
            ch["tool_uploads_count"] = ch.get("tool_uploads_count", 0) + 1
            ch["last_upload_at"] = datetime.now().isoformat()
            ch["last_uploaded_video_id"] = video_id
            ch["last_uploaded_video_title"] = title
            ch_found = True
            break
    if ch_found:
        save_channels(channels)

    return {
        "ok": True,
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "title": title,
        "privacy": privacy,
        "channel_id": channel_id,
    }

