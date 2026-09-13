# YT-1M-Automation

Automated ambience-video production system for YouTube.

## Architecture

- `backend/core/` — reusable engines (audio, image, visual, video, YouTube, scheduler, utilities)
- `backend/themes/` — day/theme-specific recipes; Monday is the first production module
- `frontend/` — web dashboard (added after backend foundation is stable)
- `output/` — final videos (ignored by Git)
- `temp/` — intermediate files (ignored by Git)
- `logs/` — runtime logs (ignored by Git)
- `metadata/` — generation/job metadata

The design intentionally keeps Monday-specific settings separate from reusable engines so future themes do not duplicate code.
