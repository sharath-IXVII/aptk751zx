"""ENT true-crime Shorts: 2 a day (CRIME_TIMES, IST); YouTube and Instagram post when a part is rendered.
python -m pipeline.crime next <order.json>      -> next key, or nothing if no slot is due yet
python -m pipeline.crime upload <key> <ep.json> <video> [preview]"""
import datetime as dt, json, os, sys
from pathlib import Path
from pipeline import youtube_upload as yt

STATE = Path("state/crime.json"); IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
load = lambda: json.loads(STATE.read_text()) if STATE.exists() else {"done": {}, "last_slot": None}


def slot(state):
    times = [tuple(map(int, t.split(":"))) for t in (os.getenv("CRIME_TIMES") or "09:00,14:00,20:00").split(",")]
    after = dt.datetime.now(IST) + dt.timedelta(minutes=40)
    if state.get("last_slot"):
        after = max(after, dt.datetime.fromisoformat(state["last_slot"]) + dt.timedelta(minutes=1))
    day = after.date()
    while True:
        for hh, mm in times:
            s = dt.datetime.combine(day, dt.time(hh, mm), IST)
            if s >= after:
                return s
        day += dt.timedelta(days=1)


def due(key, state) -> bool:
    """Jolly Jane (the launch story) posts hourly; everything else at the daily slot times."""
    if key.startswith("toppan"): return True
    times = [tuple(map(int, t.split(":"))) for t in (os.getenv("CRIME_TIMES") or "12:47,19:43").split(",")]
    now = dt.datetime.now(IST)
    last = dt.datetime.fromisoformat(state["last_slot"]) if state.get("last_slot") else now - dt.timedelta(days=1)
    day = last.date()
    while True:
        for hh, mm in times:
            s = dt.datetime.combine(day, dt.time(hh, mm), IST)
            if s > last: return now >= s - dt.timedelta(minutes=20)
        day += dt.timedelta(days=1)


def upload(key, ep_path, video, preview=False):
    state = load(); ep = json.loads(Path(ep_path).read_text()); meta = dict(ep["yt"])
    if preview:  # owner check: unlisted, no Instagram, not recorded
        os.environ["YT_PRIVACY"] = "unlisted"
        print(f"PREVIEW https://youtu.be/{yt.upload(Path(video), None, meta)}"); return
    os.environ["YT_PRIVACY"] = "public"; when = slot(state)
    if os.getenv("CRIME_NOW") == "1": when = dt.datetime.now(IST)  # post straight away
    vid = yt.upload(Path(video), None, meta, publish_at=None if os.getenv("CRIME_NOW") == "1" else when)
    try:
        from pipeline import social
        social.queue_short(state, Path(video), meta, None, None)  # Instagram: posts right away
    except Exception as exc:
        print("Instagram failed:", exc)
    state["done"][key] = {"id": vid, "publish": when.isoformat()}; state["last_slot"] = when.isoformat()
    STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(state, indent=1))
    print(f"https://youtu.be/{vid} publish={when.isoformat()}")


if __name__ == "__main__":
    import logging; logging.basicConfig(level=logging.INFO)
    if sys.argv[1] == "next":
        st = load(); k = next((e for e in json.loads(Path(sys.argv[2]).read_text()) if e not in st["done"]), "")
        print(k if k and due(k, st) else "")
    else:
        upload(sys.argv[2], sys.argv[3], sys.argv[4], len(sys.argv) > 5 and sys.argv[5] == "preview")
