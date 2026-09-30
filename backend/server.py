from __future__ import annotations

import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
import json
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .youtube_manager import (
    load_channels,
    save_channels,
    get_channel,
    get_auth_url,
    process_oauth_code,
    update_channel_settings,
    delete_channel,
    get_channel_credentials,
    upload_video_to_channel,
)
from .auth import (
    get_google_auth_url,
    process_user_oauth,
    create_session,
    terminate_session,
    get_current_user_from_request,
    load_users,
    attach_channel_to_user,
    SESSION_COOKIE_NAME,
)
from .notifier import send_upload_success_email
from .core.config import load_theme
from .core.audio_engine.master import generate_master_audio
from .core.image_engine.generator import create_generator
from .core.video_engine.ffmpeg_render import render_static_image_video
from .core.video_engine.ai_video_engine import (
    build_master_video_prompt,
    generate_real_video_clip,
    render_looped_video_with_audio,
    build_youtube_seo_metadata,
)

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
FRONTEND = PROJECT / "frontend"
OUTPUT = PROJECT / "output"
TEMP = PROJECT / "temp"
THEMES = ROOT / "themes"
SETTINGS = FRONTEND / "settings.json"
OUTPUT.mkdir(exist_ok=True)
TEMP.mkdir(exist_ok=True)

app = FastAPI(title="YT-1M Automation Local Control")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/output", StaticFiles(directory=OUTPUT), name="output")
app.mount("/temp", StaticFiles(directory=TEMP), name="temp")

JOBS_FILE = ROOT / "jobs_status.json"

def _load_persisted_jobs() -> dict:
    if JOBS_FILE.exists():
        try:
            return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _persist_jobs() -> None:
    try:
        JOBS_FILE.write_text(json.dumps(state["jobs"], indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

state = {"running": False, "jobs": _load_persisted_jobs()}


def read_settings() -> dict:
    defaults = {
        "machine_online": False,
        "enabled": False,
        "duration_minutes": 5,
        "testing_mode": True,
        "random_duration_offset": True,
        "random_offset_min_seconds": 5,
        "random_offset_max_seconds": 45,
    }
    if SETTINGS.exists():
        try:
            data = json.loads(SETTINGS.read_text(encoding="utf-8"))
            for k, v in defaults.items():
                if k not in data:
                    data[k] = v
            return data
        except Exception:
            pass
    return defaults


def write_settings(data: dict) -> None:
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class SettingsPayload(BaseModel):
    settings: dict


class GeneratePayload(BaseModel):
    theme_id: str
    duration_minutes: int = 5
    seed: int = 42


class ChannelSettingsPayload(BaseModel):
    automation: dict


class ManualChannelPayload(BaseModel):
    title: str
    custom_url: str = ""
    description: str = ""
    thumbnail: str = ""
    automation: Optional[dict] = None


class OAuthCodePayload(BaseModel):
    code: str
    redirect_uri: Optional[str] = None


class ChannelTestPipelinePayload(BaseModel):
    duration_seconds: Optional[int] = 30
    use_channel_duration: Optional[bool] = False


def _limit_duration(duration_minutes: int) -> int:
    limit = 5 if read_settings().get("testing_mode", True) else 240
    return min(max(int(duration_minutes), 1), limit)


def _compute_duration_seconds(duration_minutes: int) -> tuple[int, int]:
    """
    Computes duration in seconds based on requested duration_minutes and settings.
    If random_duration_offset is enabled (default True):
      Adds random positive seconds (min_offset to max_offset, e.g. 5 to 45 seconds).
      Guarantees: Result is STRICTLY greater than or equal to duration_minutes * 60.
      It will NEVER be less than the set duration.
    Returns: (total_seconds, extra_seconds)
    """
    settings = read_settings()
    duration_minutes = _limit_duration(duration_minutes)
    base_seconds = duration_minutes * 60

    use_random = bool(settings.get("random_duration_offset", True))
    if use_random:
        min_extra = max(int(settings.get("random_offset_min_seconds", 5)), 3)
        max_extra = max(int(settings.get("random_offset_max_seconds", 45)), min_extra + 3)
        extra_seconds = random.randint(min_extra, max_extra)
    else:
        extra_seconds = 0

    total_seconds = base_seconds + extra_seconds
    return total_seconds, extra_seconds


def do_generate(job_id: str, theme_id: str, duration_minutes: int, seed: int) -> None:
    try:
        config = load_theme(theme_id)
        total_seconds, extra_seconds = _compute_duration_seconds(duration_minutes)
        seconds = total_seconds
        base = f"{theme_id}_{seed}_{uuid.uuid4().hex[:6]}"
        audio_path = TEMP / f"{base}.wav"
        image_path = TEMP / f"{base}.png"
        video_path = OUTPUT / f"{base}.mp4"

        mins_disp = seconds // 60
        secs_disp = seconds % 60
        dur_str = f"{mins_disp}m {secs_disp:02d}s"

        state["jobs"][job_id] = {
            "status": "generating_audio",
            "theme": config.get("name", theme_id),
            "target_minutes": duration_minutes,
            "total_seconds": seconds,
            "extra_seconds": extra_seconds,
            "duration_display": dur_str,
        }
        generate_master_audio(seconds, audio_path, seed, config)

        state["jobs"][job_id]["status"] = "generating_video"
        clip_path = TEMP / f"clip_{base}.mp4"
        master_prompt = build_master_video_prompt(config)
        generate_real_video_clip(master_prompt, clip_path, theme_config=config, seed=seed)

        state["jobs"][job_id]["status"] = "rendering_video"
        render_looped_video_with_audio(clip_path, audio_path, video_path, seconds, seed=seed)
        
        # Auto-cleanup temp files
        for f in TEMP.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass
        # Keep only latest video in output
        for f in OUTPUT.glob("*.mp4"):
            if f.is_file() and f.name != video_path.name:
                try:
                    f.unlink()
                except Exception:
                    pass

        meta = build_youtube_seo_metadata(config, seconds)

        state["jobs"][job_id] = {
            "status": "completed",
            "theme": config.get("name", theme_id),
            "file": video_path.name,
            "url": f"/output/{video_path.name}",
            "target_minutes": duration_minutes,
            "total_seconds": seconds,
            "extra_seconds": extra_seconds,
            "duration_display": dur_str,
            "youtube_title": meta["title"],
            "youtube_description": meta["description"],
            "youtube_tags": meta["tags"],
        }
    except Exception as exc:
        state["jobs"][job_id] = {"status": "failed", "error": str(exc)}


def do_audio_test(job_id: str, theme_id: str, duration_minutes: int, seed: int) -> None:
    try:
        config = load_theme(theme_id)
        total_seconds, extra_seconds = _compute_duration_seconds(duration_minutes)
        seconds = total_seconds
        base = f"sound_{theme_id}_{seed}_{uuid.uuid4().hex[:6]}"
        audio_path = TEMP / f"{base}.wav"

        mins_disp = seconds // 60
        secs_disp = seconds % 60
        dur_str = f"{mins_disp}m {secs_disp:02d}s"

        state["jobs"][job_id] = {
            "status": "generating_audio",
            "theme": config.get("name", theme_id),
            "type": config.get("type", "unknown"),
            "target_minutes": duration_minutes,
            "total_seconds": seconds,
            "extra_seconds": extra_seconds,
            "duration_display": dur_str,
        }
        generate_master_audio(seconds, audio_path, seed, config)
        state["jobs"][job_id] = {
            "status": "completed",
            "theme": config.get("name", theme_id),
            "type": config.get("type", "unknown"),
            "file": audio_path.name,
            "url": f"/temp/{audio_path.name}",
            "duration_minutes": duration_minutes,
            "total_seconds": seconds,
            "extra_seconds": extra_seconds,
            "duration_display": dur_str,
        }
    except Exception as exc:
        state["jobs"][job_id] = {"status": "failed", "error": str(exc)}


def cleanup_all_temp_files():
    """Purges all files in Assets/videos, temp, and output directories."""
    ASSETS_VIDEOS = PROJECT / "Assets" / "videos"
    if ASSETS_VIDEOS.exists():
        for f in ASSETS_VIDEOS.glob("*"):
            if f.is_file():
                try:
                    f.unlink()
                except Exception:
                    pass

    for f in TEMP.glob("*"):
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass

    for f in OUTPUT.glob("*.mp4"):
        if f.is_file():
            try:
                f.unlink()
            except Exception:
                pass


def do_channel_test_pipeline(
    job_id: str,
    channel_id: str,
    custom_duration_seconds: Optional[int] = None,
    use_channel_duration: bool = False,
    user_email: Optional[str] = None,
) -> None:
    seed = random.randint(100, 99999)
    try:
        ch = get_channel(channel_id)
        if not ch:
            raise ValueError(f"Channel {channel_id} not found in database.")

        chan_title = ch.get("title", f"Channel {channel_id}")
        target_email = (user_email or ch.get("owner_email") or "9329238475x@gmail.com").strip()
        auto = ch.get("automation", {})
        theme_id = auto.get("theme_id", "01_monday_evening_rain")
        privacy = auto.get("privacy", "public")
        target_mins = auto.get("duration_minutes", 60)

        # Decide duration without any arbitrary 5m clamp!
        if use_channel_duration or not custom_duration_seconds:
            total_mins = max(1, int(target_mins))
            seconds = total_mins * 60
        else:
            seconds = max(10, int(custom_duration_seconds))

        mins_disp = seconds // 60
        secs_disp = seconds % 60
        if seconds >= 3600 and seconds % 3600 == 0:
            dur_str = f"{seconds // 3600} Hr"
        elif seconds >= 60:
            dur_str = f"{mins_disp} Minutes"
        else:
            dur_str = f"{secs_disp}s (Quick Test)"

        config = load_theme(theme_id)
        theme_name = config.get("name", theme_id)

        base = f"test_{channel_id[:8]}_{seed}_{uuid.uuid4().hex[:4]}"
        audio_path = TEMP / f"{base}.wav"
        clip_path = TEMP / f"clip_{base}.mp4"
        video_path = OUTPUT / f"final_{base}.mp4"

        # 1. Synthesize procedural audio
        # If duration > 90s, synthesize a seamless 90s audio master that FFmpeg will stream-loop
        audio_dur = min(seconds, 90) if seconds > 120 else seconds
        state["jobs"][job_id] = {
            "status": "generating_audio",
            "progress": 15,
            "step": "1/5",
            "message": f"1/5: Synthesizing {dur_str} procedural binaural audio for {chan_title}...",
            "channel_title": chan_title,
            "theme": theme_name,
            "duration_display": dur_str,
            "privacy": privacy,
        }
        _persist_jobs()
        generate_master_audio(audio_dur, audio_path, seed, config)

        # 2. Real Nature Footage Clip
        state["jobs"][job_id]["status"] = "generating_video"
        state["jobs"][job_id]["progress"] = 35
        state["jobs"][job_id]["step"] = "2/5"
        state["jobs"][job_id]["message"] = "2/5: Generating 1080p real nature footage clip..."
        _persist_jobs()
        master_prompt = build_master_video_prompt(config)
        generate_real_video_clip(master_prompt, clip_path, theme_config=config, seed=seed)

        # 3. Looped video render & audio sync
        state["jobs"][job_id]["status"] = "rendering_video"
        state["jobs"][job_id]["progress"] = 60
        state["jobs"][job_id]["step"] = "3/5"
        state["jobs"][job_id]["message"] = f"3/5: Rendering seamless looped {dur_str} video & syncing audio (FFmpeg)..."
        _persist_jobs()
        render_looped_video_with_audio(clip_path, audio_path, video_path, seconds, seed=seed)

        # 4. YouTube Upload
        state["jobs"][job_id]["status"] = "uploading_youtube"
        state["jobs"][job_id]["progress"] = 75
        state["jobs"][job_id]["step"] = "4/5"
        state["jobs"][job_id]["message"] = f"4/5: Uploading to YouTube ({chan_title}) with {privacy.upper()} visibility..."
        _persist_jobs()
        meta = build_youtube_seo_metadata(config, seconds)

        def on_upload_chunk(pct: int):
            prog = min(92, 75 + int(pct * 0.17))
            state["jobs"][job_id]["progress"] = prog
            state["jobs"][job_id]["upload_percent"] = pct
            state["jobs"][job_id]["message"] = f"4/5: Uploading to YouTube: {pct}% complete..."
            _persist_jobs()

        upload_res = upload_video_to_channel(
            channel_id=channel_id,
            video_path=video_path,
            title=meta["title"],
            description=meta["description"],
            tags=meta["tags"],
            privacy=privacy,
            progress_callback=on_upload_chunk,
        )
        video_id = upload_res.get("video_id")
        video_url = upload_res.get("url", f"https://youtu.be/{video_id}")

        # 5. Email Notification
        state["jobs"][job_id]["status"] = "sending_email"
        state["jobs"][job_id]["progress"] = 93
        state["jobs"][job_id]["step"] = "5/5"
        state["jobs"][job_id]["message"] = f"5/5: Sending confirmation alert to {target_email}..."
        _persist_jobs()
        email_sent = send_upload_success_email(
            channel_name=chan_title,
            channel_id=channel_id,
            video_title=meta["title"],
            video_id=video_id,
            privacy=privacy,
            duration_display=dur_str,
            theme_name=theme_name,
            recipient_email=target_email,
        )

        # 6. Complete Auto-Disk Cleanup (Assets/videos, temp, output)
        state["jobs"][job_id]["progress"] = 98
        state["jobs"][job_id]["message"] = "Cleaning local video and temporary files..."
        _persist_jobs()
        cleanup_all_temp_files()

        state["jobs"][job_id] = {
            "status": "completed",
            "progress": 100,
            "channel_id": channel_id,
            "channel_title": chan_title,
            "video_id": video_id,
            "video_url": video_url,
            "youtube_title": meta["title"],
            "privacy": privacy,
            "theme": theme_name,
            "duration_display": dur_str,
            "email_sent": email_sent,
            "recipient_email": target_email,
            "auto_cleaned": True,
            "message": f"🎉 Successfully uploaded to YouTube & confirmation email sent to {target_email}! Assets/videos, temp, and output files cleared.",
        }
        _persist_jobs()

    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}", exc_info=True)
        # Attempt cleanup on error as well
        try:
            cleanup_all_temp_files()
        except Exception:
            pass
        state["jobs"][job_id] = {
            "status": "failed",
            "progress": 0,
            "error": str(exc),
            "channel_id": channel_id,
        }
        _persist_jobs()


@app.get("/api/status")
def status() -> dict:
    return {"running": state["running"], "jobs": state["jobs"]}


@app.get("/api/settings")
def get_settings() -> dict:
    return read_settings()


@app.post("/api/settings")
def save_settings(payload: SettingsPayload) -> dict:
    settings = payload.settings
    settings["machine_online"] = bool(settings.get("machine_online", False))
    settings["random_duration_offset"] = bool(settings.get("random_duration_offset", True))
    settings["random_offset_min_seconds"] = max(3, int(settings.get("random_offset_min_seconds", 5)))
    settings["random_offset_max_seconds"] = max(
        settings["random_offset_min_seconds"] + 3,
        int(settings.get("random_offset_max_seconds", 45)),
    )
    write_settings(settings)
    state["running"] = settings["machine_online"] and bool(settings.get("enabled", False))
    return {"ok": True, "settings": settings}


@app.post("/api/control/start")
def start() -> dict:
    settings = read_settings()
    settings["machine_online"] = True
    settings["enabled"] = True
    write_settings(settings)
    state["running"] = True
    return {"ok": True, "running": True}


@app.post("/api/control/stop")
def stop() -> dict:
    settings = read_settings()
    settings["machine_online"] = False
    settings["enabled"] = False
    write_settings(settings)
    state["running"] = False
    return {"ok": True, "running": False}


@app.get("/api/themes")
def themes() -> list[dict]:
    result = []
    for path in sorted(THEMES.glob("*/config.json")):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
            if cfg.get("id") == "01_monday":
                continue
            result.append({"id": cfg["id"], "name": cfg["name"], "type": cfg.get("type", "unknown")})
        except Exception:
            continue
    return result


@app.post("/api/test-audio")
def test_audio(payload: GeneratePayload, background_tasks: BackgroundTasks) -> dict:
    theme_id = (payload.theme_id or "").strip() or "01_monday_evening_rain"
    try:
        cfg = load_theme(theme_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    resolved_theme = cfg.get("id", theme_id)
    job_id = uuid.uuid4().hex
    state["jobs"][job_id] = {"status": "queued", "theme": cfg.get("name", theme_id), "type": "audio"}
    background_tasks.add_task(do_audio_test, job_id, resolved_theme, payload.duration_minutes, payload.seed)
    return {"ok": True, "job_id": job_id}


@app.post("/api/test-generate")
def test_generate(payload: GeneratePayload, background_tasks: BackgroundTasks) -> dict:
    theme_id = (payload.theme_id or "").strip() or "01_monday_evening_rain"
    try:
        cfg = load_theme(theme_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    resolved_theme = cfg.get("id", theme_id)
    job_id = uuid.uuid4().hex
    state["jobs"][job_id] = {"status": "queued", "theme": cfg.get("name", theme_id)}
    background_tasks.add_task(do_generate, job_id, resolved_theme, payload.duration_minutes, payload.seed)
    return {"ok": True, "job_id": job_id}


@app.get("/testing")
def testing() -> FileResponse:
    return FileResponse(FRONTEND / "testing.html")


@app.get("/favicon.ico")
def favicon():
    fav = FRONTEND / "favicon.svg"
    if fav.exists():
        return FileResponse(fav, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(FRONTEND / "home.html")


@app.get("/home")
def home_page() -> FileResponse:
    return FileResponse(FRONTEND / "home.html")


@app.get("/dashboard")
def dashboard(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/?login_required=1", status_code=302)
    return FileResponse(FRONTEND / "index.html")


@app.get("/account")
def account(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/?login_required=1", status_code=302)
    return FileResponse(FRONTEND / "account.html")


@app.get("/privacy")
def privacy_page() -> FileResponse:
    return FileResponse(FRONTEND / "privacy.html")


@app.get("/terms")
def terms_page() -> FileResponse:
    return FileResponse(FRONTEND / "terms.html")


@app.get("/statement")
def statement(request: Request):
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/?login_required=1", status_code=302)
    return FileResponse(FRONTEND / "statement.html")


# ================= USER GOOGLE AUTH ENDPOINTS =================

@app.get("/api/auth/google/url")
def auth_google_url(request: Request) -> dict:
    """Generates Google OAuth URL for user login."""
    try:
        redirect_uri = "http://localhost:8000/api/auth/google/callback"
        auth_url, state_param = get_google_auth_url(redirect_uri=redirect_uri)
        return {"ok": True, "auth_url": auth_url, "state": state_param}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/auth/google/login")
def auth_google_login(request: Request) -> RedirectResponse:
    """Redirects directly to Google Login consent screen."""
    try:
        redirect_uri = "http://localhost:8000/api/auth/google/callback"
        auth_url, _ = get_google_auth_url(redirect_uri=redirect_uri)
        return RedirectResponse(url=auth_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/auth/google/callback")
def auth_google_callback(
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
) -> RedirectResponse:
    """Handles user Google OAuth callback, sets session cookie, redirects to dashboard."""
    if error:
        return RedirectResponse(url=f"/?auth_error={error}")
    if not code:
        return RedirectResponse(url="/?auth_error=no_authorization_code")

    try:
        redirect_uri = "http://localhost:8000/api/auth/google/callback"
        user = process_user_oauth(code=code, redirect_uri=redirect_uri, state=state)
        session_token = create_session(user["email"])
        resp = RedirectResponse(url="/dashboard?login=success", status_code=302)
        resp.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_token,
            max_age=30 * 86400,
            path="/",
            httponly=False,
            samesite="lax",
        )
        return resp
    except Exception as exc:
        err_msg = str(exc).replace(" ", "%20")
        return RedirectResponse(url=f"/?auth_error={err_msg}")


@app.get("/api/auth/me")
def get_current_user_profile(request: Request) -> dict:
    """Returns current authenticated user details."""
    user = get_current_user_from_request(request)
    if not user:
        return {"ok": True, "authenticated": False, "user": None}
    return {"ok": True, "authenticated": True, "user": user}


@app.post("/api/auth/logout")
@app.get("/api/auth/logout")
def logout_user(request: Request) -> RedirectResponse:
    """Clears session cookie and invalidates session token."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        terminate_session(token)
    resp = RedirectResponse(url="/?logged_out=1", status_code=302)
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp


@app.post("/api/control/clear-jobs")
def clear_jobs() -> dict:
    state["jobs"].clear()
    return {"ok": True}


# ================= MULTI-CHANNEL YOUTUBE API ENDPOINTS =================

@app.get("/api/channels")
def get_all_channels(request: Request) -> dict:
    """Returns saved channels from channels.json, filtered for current user if applicable."""
    channels = load_channels()
    user = get_current_user_from_request(request)
    if user and user.get("email"):
        user_email = user["email"]
        user_channels = [c for c in channels if c.get("owner_email") == user_email]
        # Include legacy channels that have no owner_email assigned yet
        if not user_channels:
            legacy_assigned = False
            for c in channels:
                if not c.get("owner_email"):
                    c["owner_email"] = user_email
                    user_channels.append(c)
                    legacy_assigned = True
            if legacy_assigned:
                save_channels(channels)
        return {"ok": True, "channels": user_channels, "user_email": user_email}
    return {"ok": True, "channels": channels, "user_email": None}


@app.get("/api/channels/auth/start")
def start_oauth_flow(request: Request) -> RedirectResponse:
    """Redirects user directly to Google OAuth consent screen for YouTube."""
    try:
        # Determine redirect URI dynamically or fallback to standard localhost
        redirect_uri = "http://localhost:8000/api/channels/oauth2callback"
        auth_url, state_param = get_auth_url(redirect_uri=redirect_uri)
        return RedirectResponse(url=auth_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/channels/auth/url")
def generate_oauth_url(request: Request) -> dict:
    """Generates the Google OAuth authorization URL for the frontend."""
    try:
        redirect_uri = "http://localhost:8000/api/channels/oauth2callback"
        auth_url, state_param = get_auth_url(redirect_uri=redirect_uri)
        return {"ok": True, "auth_url": auth_url, "state": state_param}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/channels/oauth2callback")
def oauth2_callback(
    request: Request,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
) -> RedirectResponse:
    """Handles OAuth 2.0 loopback redirect from Google."""
    if error:
        return RedirectResponse(url=f"/account?oauth_error={error}")
    if not code:
        return RedirectResponse(url="/account?oauth_error=no_authorization_code_received")

    try:
        redirect_uri = "http://localhost:8000/api/channels/oauth2callback"
        user = get_current_user_from_request(request)
        owner_email = user.get("email") if user else None
        channel_data = process_oauth_code(code, redirect_uri=redirect_uri, state=state, owner_email=owner_email)
        chan_id = channel_data.get("id", "")
        chan_title = channel_data.get("title", "")
        if owner_email and chan_id:
            attach_channel_to_user(owner_email, chan_id)
        return RedirectResponse(url=f"/account?connected=1&channel_id={chan_id}&title={chan_title}")
    except Exception as exc:
        err_msg = str(exc).replace(" ", "%20")
        return RedirectResponse(url=f"/account?oauth_error={err_msg}")


@app.post("/api/channels/auth/code")
def exchange_code_manually(payload: OAuthCodePayload) -> dict:
    """Exchanges an authorization code manually if pasted by user."""
    try:
        redirect_uri = payload.redirect_uri or "http://localhost:8000/api/channels/oauth2callback"
        channel_data = process_oauth_code(payload.code, redirect_uri=redirect_uri)
        return {"ok": True, "channel": channel_data}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/channels/manual")
def add_manual_channel(payload: ManualChannelPayload, request: Request) -> dict:
    """Allows adding a custom/brand channel profile with custom automation parameters."""
    channels = load_channels()
    chan_id = "UC_" + uuid.uuid4().hex[:12]
    now_str = datetime.now().isoformat()
    user = get_current_user_from_request(request)
    owner_email = user.get("email") if user else ""

    default_auto = {
        "enabled": True,
        "theme_mode": "all_weekly",
        "theme_id": "01_monday_evening_rain",
        "duration_hours": 2,
        "duration_minutes": 0,
        "schedule_type": "daily",
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "upload_time": "18:00",
        "privacy": "private"
    }
    if payload.automation:
        default_auto.update(payload.automation)

    channel_data = {
        "id": chan_id,
        "title": payload.title.strip() or f"Brand Channel {len(channels)+1}",
        "custom_url": payload.custom_url.strip() or f"@{payload.title.lower().replace(' ', '')}",
        "description": payload.description.strip(),
        "thumbnail": payload.thumbnail.strip(),
        "subscriber_count": "0",
        "video_count": "0",
        "tool_uploads_count": 0,
        "connected_at": now_str,
        "last_connected": now_str,
        "token_file": "",
        "status": "configured",
        "owner_email": owner_email,
        "automation": default_auto
    }
    channels.append(channel_data)
    save_channels(channels)
    if owner_email:
        attach_channel_to_user(owner_email, chan_id)
    return {"ok": True, "channel": channel_data}


@app.post("/api/channels/{channel_id}/settings")
@app.put("/api/channels/{channel_id}/settings")
def save_channel_settings(channel_id: str, payload: ChannelSettingsPayload) -> dict:
    """Updates and saves automation configuration for a specific channel."""
    try:
        updated = update_channel_settings(channel_id, payload.automation)
        return {"ok": True, "channel": updated}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/channels/{channel_id}")
def remove_channel(channel_id: str) -> dict:
    """Deletes a channel and clears its stored credentials."""
    success = delete_channel(channel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"ok": True, "channel_id": channel_id}


@app.post("/api/channels/{channel_id}/test-status")
def test_channel_token_status(channel_id: str) -> dict:
    """Validates the OAuth token for the channel."""
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")

    creds = get_channel_credentials(channel_id)
    if not creds:
        return {
            "ok": False,
            "channel_id": channel_id,
            "status": "no_credentials",
            "message": "Token file not found or invalid."
        }

    try:
        from google.auth.transport.requests import Request as GoogleRequest
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        return {
            "ok": True,
            "channel_id": channel_id,
            "status": "valid",
            "message": "OAuth credentials are active and ready for automatic uploads."
        }
    except Exception as exc:
        return {
            "ok": False,
            "channel_id": channel_id,
            "status": "refresh_failed",
            "message": str(exc)
        }


@app.post("/api/channels/{channel_id}/test-pipeline")
def test_channel_pipeline(
    channel_id: str,
    request: Request,
    payload: Optional[ChannelTestPipelinePayload] = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Executes a complete end-to-end video pipeline test for the specified channel:
    generates procedural audio -> renders looped video -> uploads to YouTube via OAuth
    -> sends confirmation Gmail -> purges all local temp & video files automatically.
    """
    ch = get_channel(channel_id)
    if not ch:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found.")

    creds = get_channel_credentials(channel_id)
    if not creds:
        raise HTTPException(
            status_code=400,
            detail=f"No active YouTube OAuth credentials found for {ch.get('title')}. Please link the channel first.",
        )

    user = get_current_user_from_request(request)
    user_email = user.get("email") if user else None

    job_id = "pipe_" + uuid.uuid4().hex[:8]
    duration_sec = payload.duration_seconds if payload and payload.duration_seconds else 30
    use_chan_dur = bool(payload.use_channel_duration) if payload else False

    state["jobs"][job_id] = {
        "status": "queued",
        "channel_id": channel_id,
        "channel_title": ch.get("title"),
        "job_type": "full_pipeline_test",
        "created_at": datetime.now().isoformat(),
        "step": "0/4",
        "message": f"Job queued for {ch.get('title')}...",
    }

    if background_tasks:
        background_tasks.add_task(
            do_channel_test_pipeline,
            job_id,
            channel_id,
            duration_sec,
            use_chan_dur,
            user_email,
        )
    else:
        # Fallback thread if background_tasks not injected
        import threading
        t = threading.Thread(
            target=do_channel_test_pipeline,
            args=(job_id, channel_id, duration_sec, use_chan_dur, user_email),
            daemon=True,
        )
        t.start()

    return {
        "ok": True,
        "job_id": job_id,
        "channel_id": channel_id,
        "channel_title": ch.get("title"),
        "message": "Full video pipeline test triggered. Rendering video & uploading to YouTube...",
    }


