"""ENT story Shorts ('The Human Journey'): Instagram Reel as soon as a part is rendered,
YouTube Short scheduled 3 a day (SAGA_TIMES, IST).
python -m pipeline.saga next <order.json>
python -m pipeline.saga upload <key> <ep.json> <video> [preview]"""
import datetime as dt, json, os, sys
from pathlib import Path
from pipeline import youtube_upload as yt

STATE = Path("state/saga.json"); IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
load = lambda: json.loads(STATE.read_text()) if STATE.exists() else {"done": {}, "last_slot": None}


def slot(state):
    times = [tuple(map(int, t.split(":"))) for t in (os.getenv("SAGA_TIMES") or "09:00,14:00,20:00").split(",")]
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


def upload(key, ep_path, video, preview=False):
    state = load(); ep = json.loads(Path(ep_path).read_text()); meta = dict(ep["yt"])
    if preview:  # owner check: unlisted, no Instagram, not recorded
        os.environ["YT_PRIVACY"] = "unlisted"
        print(f"PREVIEW https://youtu.be/{yt.upload(Path(video), None, meta)}"); return
    os.environ["YT_PRIVACY"] = "public"; when = slot(state)
    vid = yt.upload(Path(video), None, meta, publish_at=when)
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
        done = load()["done"]; print(next((e for e in json.loads(Path(sys.argv[2]).read_text()) if e not in done), ""))
    else:
        upload(sys.argv[2], sys.argv[3], sys.argv[4], len(sys.argv) > 5 and sys.argv[5] == "preview")
