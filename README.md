---
title: YT 1M Studio
emoji: 🌖
colorFrom: blue
colorTo: yellow
sdk: gradio
app_file: app.py
pinned: false
license: mit
short_description: yt automat tool
---

# YT-1M-Automation

Automated ambience-video production system for YouTube.

## Architecture

- `backend/core/` — reusable engines (audio, image, visual, video, YouTube, scheduler, utilities)
- `backend/themes/` — day/theme-specific recipes
- `frontend/` — web dashboard
- `output/` — final videos (ignored by Git)
- `temp/` — intermediate files (ignored by Git)
- `metadata/` — generation/job metadata
