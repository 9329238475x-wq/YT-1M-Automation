from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "schedule" / "weekly_plan.json"


def load_plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8"))


def get_uploads_for_date(dt: datetime | None = None) -> list[dict]:
    plan = load_plan()
    tz = ZoneInfo(plan["timezone"])
    now = (dt or datetime.now(tz)).astimezone(tz)
    day = now.strftime("%A").lower()
    day_plan = plan["days"][day]
    result = []
    for slot in plan["slots"]:
        time = slot["time"]
        result.append({
            "date": now.date().isoformat(),
            "time": time,
            "slot_type": slot["type"],
            "theme_id": day_plan[time],
            "duration_minutes": min(
                plan["testing"]["max_duration_minutes"],
                5 if plan["testing"]["enabled"] else 999999,
            ),
        })
    return result


def next_uploads(dt: datetime | None = None) -> list[dict]:
    # The runner can use this deterministic list to enqueue both daily jobs.
    return get_uploads_for_date(dt)


if __name__ == "__main__":
    print(json.dumps(next_uploads(), indent=2))
