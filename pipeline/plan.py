"""How many videos to make today, and whether a run has anything to do.

Standard library only, so the workflow can check it in seconds before installing anything.

VIDEOS_PER_DAY is a comma-separated pattern that repeats day by day, e.g. "1,2" (default):
1 video one day, 2 the next. "1" = one every day, "0" = no limit.
"""

import datetime as dt
import json
import os
from pathlib import Path

STATE_FILE = Path("state/current.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOTEBOOKLM_GAP = dt.timedelta(hours=5)


def today() -> dt.date:
    return dt.datetime.now(IST).date()


def daily_limit(day: dt.date | None = None) -> int:
    pattern = [int(v) for v in (os.getenv("VIDEOS_PER_DAY") or "1,2").split(",") if v.strip()]
    day = day or today()
    return pattern[day.toordinal() % len(pattern)]


def uploads_today(state: dict) -> int:
    return state.get("uploads", {}).get(today().isoformat(), 0)


def limit_reached(state: dict) -> bool:
    limit = daily_limit()
    return bool(limit) and uploads_today(state) >= limit


def nothing_to_do(state: dict) -> bool:
    """True if this run can stop at once: no unfinished video and either today's videos are
    done or NotebookLM's 5-hour gap has not passed yet."""
    if state.get("job"):
        return False
    if limit_reached(state):
        return True
    last = state.get("notebooklm_started_at")
    return bool(last) and dt.datetime.now(IST) - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP


if __name__ == "__main__":  # used by the workflow: prints skip=true/false
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    print(f"today={today()} limit={daily_limit() or 'none'} uploaded={uploads_today(state)}",
          flush=True, file=__import__("sys").stderr)
    print("skip=" + ("true" if nothing_to_do(state) else "false"))
