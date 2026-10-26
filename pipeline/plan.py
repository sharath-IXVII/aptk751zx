"""Publishing plan: videos are made ahead of time and scheduled into future slots, so the
channel keeps posting even when some runs fail.

- VIDEOS_PER_DAY: videos published per day (default "2"); also a comma-separated pattern
  repeating day by day, e.g. "1,2" = 1 video one day, 2 the next.
- YT_PUBLISH_TIMES: India times of the slots (default "12:00,18:00"). A 1-video day uses the
  last time (18:00), a 2-video day the first two (12:00 and 18:00).
- BUFFER_DAYS: how many days ahead to fill (default 60). Episodes are evergreen, so 4 are made
  every day and the extra 2 a day keep filling future days.

Standard library only, so the workflow can check it in seconds before installing anything.
"""

import datetime as dt
import json
import os
import sys
from pathlib import Path

STATE_FILE = Path("state/current.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
NOTEBOOKLM_GAP = dt.timedelta(hours=6)  # one new video every 6 hours = 4 a day
MIN_LEAD = dt.timedelta(minutes=30)  # a slot must be at least this far away when uploading


def now() -> dt.datetime:
    return dt.datetime.now(IST)


def videos_on(day: dt.date) -> int:
    pattern = [int(v) for v in (os.getenv("VIDEOS_PER_DAY") or "2").split(",") if v.strip()]
    return pattern[day.toordinal() % len(pattern)]


def slots_on(day: dt.date) -> list[dt.datetime]:
    times = [t.strip() for t in (os.getenv("YT_PUBLISH_TIMES") or "12:00,18:00").split(",")]
    n = videos_on(day)
    chosen = times[-1:] if n == 1 else times[:n]
    return [dt.datetime.combine(day, dt.time(*map(int, t.split(":"))), IST) for t in chosen]


def taken(state: dict) -> set[str]:
    return set(state.get("scheduled", []))


def next_slot(state: dict, at: dt.datetime | None = None) -> dt.datetime | None:
    """The first free publishing slot, or None if the buffer is full."""
    at = at or now()
    used = taken(state)
    last_day = at.date() + dt.timedelta(days=int(os.getenv("BUFFER_DAYS") or 60))
    day = at.date()
    while day <= last_day:
        for slot in slots_on(day):
            if slot - at >= MIN_LEAD and slot.isoformat() not in used:
                return slot
        day += dt.timedelta(days=1)
    return None


def book(state: dict, slot: dt.datetime) -> None:
    """Mark a slot as used; forget slots that are already in the past."""
    keep = [s for s in state.get("scheduled", []) if dt.datetime.fromisoformat(s) > now()]
    state["scheduled"] = sorted(keep + [slot.isoformat()])


def nothing_to_do(state: dict) -> bool:
    """True if this run can stop at once: no unfinished video and either the buffer is full or
    NotebookLM's 6-hour gap has not passed yet."""
    if state.get("job"):
        return False
    if next_slot(state) is None:
        return True
    last = state.get("notebooklm_started_at")
    return bool(last) and now() - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP


if __name__ == "__main__":  # used by the workflow: prints skip=true/false
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    slot = next_slot(state)
    print(f"scheduled: {sorted(taken(state))}; next free slot: {slot}", file=sys.stderr)
    print("skip=" + ("true" if nothing_to_do(state) else "false"))
