from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.config import load_theme
from .core.audio_engine.master import generate_master_audio
from .core.image_engine.generator import create_generator
from .core.video_engine.ffmpeg_render import render_static_image_video

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

state = {"running": False, "jobs": {}}


def read_settings() -> dict:
    if SETTINGS.exists():
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    return {"machine_online": False, "enabled": False, "duration_minutes": 5, "testing_mode": True}


def write_settings(data: dict) -> None:
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class SettingsPayload(BaseModel):
    settings: dict


class GeneratePayload(BaseModel):
    theme_id: str
    duration_minutes: int = 5
    seed: int = 42


def do_generate(job_id: str, theme_id: str, duration_minutes: int, seed: int) -> None:
    try:
        config = load_theme(theme_id)
        limit = 5 if read_settings().get("testing_mode", True) else 240
        duration_minutes = min(max(int(duration_minutes), 1), limit)
        seconds = duration_minutes * 60
        base = f"{theme_id}_{seed}_{uuid.uuid4().hex[:6]}"
        audio_path = TEMP / f"{base}.wav"
        image_path = TEMP / f"{base}.png"
        video_path = OUTPUT / f"{base}.mp4"

        state["jobs"][job_id] = {"status": "generating_audio", "theme": config.get("name", theme_id)}
        generate_master_audio(seconds, audio_path, seed, config)

        state["jobs"][job_id] = {"status": "generating_image", "theme": config.get("name", theme_id)}
        scene = config.get("visual", {}).get("scene", config.get("name", theme_id))
        create_generator("placeholder").generate(scene, 1920, 1080, image_path)

        state["jobs"][job_id] = {"status": "rendering_video", "theme": config.get("name", theme_id)}
        render_static_image_video(image_path, audio_path, video_path, seconds)
        state["jobs"][job_id] = {
            "status": "completed",
            "theme": config.get("name", theme_id),
            "file": video_path.name,
            "url": f"/output/{video_path.name}",
        }
    except Exception as exc:
        state["jobs"][job_id] = {"status": "failed", "error": str(exc)}


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
            result.append({"id": cfg["id"], "name": cfg["name"], "type": cfg.get("type", "unknown")})
        except Exception:
            continue
    return result


@app.post("/api/test-generate")
def test_generate(payload: GeneratePayload, background_tasks: BackgroundTasks) -> dict:
    try:
        load_theme(payload.theme_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    job_id = uuid.uuid4().hex
    state["jobs"][job_id] = {"status": "queued", "theme": payload.theme_id}
    background_tasks.add_task(do_generate, job_id, payload.theme_id, payload.duration_minutes, payload.seed)
    return {"ok": True, "job_id": job_id}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")
