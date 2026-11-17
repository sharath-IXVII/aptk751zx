"""ENT long videos: one 'full story' documentary per case, made by joining its Short parts.
Only long videos earn watch hours, so each finished case (all parts posted as Shorts) gets one.

python -m pipeline.crime_full next              -> case id to make now (or nothing)
python -m pipeline.crime_full build <case> <out.json>
python -m pipeline.crime_full upload <case> <video>
Schedule: FULL_DAYS (weekday numbers, Mon=0) at FULL_TIME IST, default Mon/Wed/Fri 14:30."""
import datetime as dt, json, os, sys
from pathlib import Path

EP = Path("crime/episodes"); STATE = Path("state/crime_full.json"); SHORTS = Path("state/crime.json")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
load = lambda p, d: json.loads(p.read_text()) if p.exists() else d


def cases_in_order():
    seen = []
    for k in json.loads((EP / "order.json").read_text()):
        c = k.rsplit("_p", 1)[0]
        if c not in seen: seen.append(c)
    return seen


def parts(case):
    order = json.loads((EP / "order.json").read_text())
    return [k for k in order if k.rsplit("_p", 1)[0] == case]


def due(state) -> bool:
    days = [int(d) for d in (os.getenv("FULL_DAYS") or "0,2,4").split(",")]
    hh, mm = map(int, (os.getenv("FULL_TIME") or "14:30").split(":"))
    now = dt.datetime.now(IST)
    last = dt.datetime.fromisoformat(state["last"]) if state.get("last") else now - dt.timedelta(days=30)
    d = last.date()
    while True:
        s = dt.datetime.combine(d, dt.time(hh, mm), IST)
        if s > last and d.weekday() in days: return now >= s
        d += dt.timedelta(days=1)


def next_case():
    st = load(STATE, {"done": {}}); posted = load(SHORTS, {"done": {}})["done"]
    if not due(st): return ""
    for c in cases_in_order():
        if c in st["done"]: continue
        ks = parts(c)
        if ks and all(k in posted for k in ks): return c   # every part already out as a Short
    return ""


def build(case, out):
    ks = parts(case); eps = [json.loads((EP / f"{k}.json").read_text()) for k in ks]
    first = eps[0]; shots = []
    for i, e in enumerate(eps):
        for sh in e["shots"]:
            if sh.get("intro"):
                if i: continue
                sh = dict(sh, intro=dict(sh["intro"], part="THE FULL STORY"), hold=3.5)
            if sh.get("card") and i < len(eps) - 1: continue   # only the final question card
            shots.append(sh)
    shots[-1] = dict(shots[-1], card=dict(shots[-1]["card"], f="Subscribe for the next true story"))
    name = first["yt"]["title"].split("|")[1].split("(True Story)")[0].strip()
    cast = {}
    for e in eps: cast.update(e["cast"])
    ep = {"key": f"{case}_full", "narrator": first.get("narrator", "am_michael"), "cast": cast, "shots": shots,
          "yt": {"title": f"{name}: The Full True Story | True Crime Documentary"[:100],
                 "description": f"The complete story of {name}, all {len(eps)} parts in one film. "
                                f"A dramatised retelling of a real historical case; dialogue and some scenes are imagined, "
                                f"the key events are real.\n\nWatch each part as a Short on this channel.\n\n#truecrime #history #documentary",
                 "tags": ["true crime", "documentary", "history", "full story", name.lower()]}}
    Path(out).write_text(json.dumps(ep, indent=1, ensure_ascii=False))
    print(f"{case}: {len(eps)} parts, {len(shots)} shots")


def upload(case, video):
    from pipeline import youtube_upload as yt
    st = load(STATE, {"done": {}}); ep = json.loads(Path("build/full.json").read_text())
    os.environ["YT_PRIVACY"] = "public"
    try:
        vid = yt.upload(Path(video), None, ep["yt"])
    except Exception as exc:
        if "uploadLimitExceeded" in str(exc) or "exceeded the number of videos" in str(exc):
            print("YouTube upload limit reached - will retry next run."); return
        raise
    now = dt.datetime.now(IST).isoformat()
    st["done"][case] = {"id": vid, "at": now}; st["last"] = now
    STATE.parent.mkdir(exist_ok=True); STATE.write_text(json.dumps(st, indent=1))
    print(f"https://youtu.be/{vid}")


if __name__ == "__main__":
    import logging; logging.basicConfig(level=logging.INFO)
    if sys.argv[1] == "next": print(next_case())
    elif sys.argv[1] == "build": build(sys.argv[2], sys.argv[3])
    else: upload(sys.argv[2], sys.argv[3])
