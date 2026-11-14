"""Writes the next true-crime case into ready-to-render episodes.

python -m pipeline.crime_writer [min_ahead]
Keeps at least `min_ahead` unpublished parts in crime/episodes/order.json. For the next case it
1) makes a cast (looks + fixed voices, saved in crime/cast/<id>.json so voices never change),
2) asks the LLM to dramatise each fact beat as shots in a small, safe vocabulary,
3) converts those into engine shots using camera/position layouts that were checked by eye.
The LLM may only dramatise the beat it is given; a second model checks for invented facts."""
import json, logging, os, re, sys, hashlib
from pathlib import Path
sys.path.insert(0, "crime")
from cases import CASES
from cases2 import CASES2
from cases3 import CASES3
from pipeline import llm

log = logging.getLogger("crime_writer")
ALL = CASES + CASES2 + CASES3
EP = Path("crime/episodes"); CAST = Path("crime/cast"); STATE = Path("state/crime.json")
SETS = ["home", "street", "forest", "prison", "court", "grave", "ward", "asylum", "dock", "shore"]
ACTS = ["idle", "smile", "think", "scared", "cry", "point", "give", "tuck", "cross", "cuffed", "kneel", "walk", "sick", "sleep", "peek"]
FRAMES = ["two", "solo", "face", "three", "bed", "grave", "court", "cell", "walk", "establish"]
LOOKS = ["plain", "rich", "worker", "police", "detective", "doctor", "nurse", "judge", "prisoner", "soldier", "royal"]
VOICES = {"f": ["af_bella", "af_nicole", "af_sarah", "af_sky", "af_nova", "bf_emma", "bf_isabella", "af_jessica", "af_river", "bf_alice", "af_kore", "af_aoede"],
          "m": ["am_adam", "am_eric", "am_liam", "bm_george", "bm_lewis", "bm_daniel", "bm_fable", "am_echo", "am_puck", "am_onyx", "am_fenrir"]}
SKIN = ["#e6b48e", "#d9a882", "#c99872", "#b9774a", "#a86a42", "#8a5232", "#e0aa84", "#d0a07c"]
HAIR = {"black": "#1d1d1d", "brown": "#4a3020", "blonde": "#c8a050", "red": "#a84a22", "grey": "#9a9a9a", "white": "#e0e0e0"}
CLOTH = {"plain": ("#5a4a3a", "#43372b"), "rich": ("#3a2a4a", "#2a1e36"), "worker": ("#4a5a6a", "#36424e"),
         "police": ("#1e2a4a", "#16203a"), "detective": ("#3b3f4a", "#2a2d35"), "doctor": ("#e8e8e8", "#bdbdbd"),
         "nurse": ("#2a2f45", "#232838"), "judge": ("#151515", "#101010"), "prisoner": ("#8a8a7a", "#6a6a5e"),
         "soldier": ("#4a5a3a", "#36422a"), "royal": ("#6a1a2a", "#4a1220")}
FEM_CLOTH = ["#7a2f3a", "#2f5a6a", "#5a3a5a", "#3a5a4a", "#6a4a2a", "#2a2f45"]


def h(s: str) -> int: return int(hashlib.md5(s.encode()).hexdigest(), 16)


def make_cast(case) -> dict:
    p = CAST / f"{case['id']}.json"
    if p.exists(): return json.loads(p.read_text())
    prompt = (f"True crime case: {case['name']} ({case['setting']}).\nPeople: {case['people']}\n"
              f"Story beats: {json.dumps(case['parts'])}\n\nList up to 9 on-screen characters needed to act out these beats "
              f"(real people named above, plus unnamed roles like 'police officer', 'neighbour', 'doctor', 'judge' if needed). "
              f'JSON: {{"cast":[{{"id":"short lowercase id, letters only","name":"display name","gender":"m|f","age":"young|adult|old",'
              f'"look":"one of {LOOKS}","hair":"one of {list(HAIR)}","beard":true|false}}]}}')
    raw = llm.chat_json(prompt, temperature=0.3, max_tokens=2000).get("cast", [])
    used = {"m": 0, "f": 0}; cast = {}
    for c in raw[:9]:
        cid = re.sub(r"[^a-z]", "", str(c.get("id", "")).lower())[:10]
        if not cid or cid in cast or cid == "nar": continue
        g = "f" if str(c.get("gender", "m")).lower().startswith("f") else "m"
        look = c.get("look") if c.get("look") in CLOTH else "plain"
        hair = HAIR.get(c.get("hair"), "#4a3020")
        if c.get("age") == "old" and c.get("hair") not in ("grey", "white"): hair = "#b0b0b0"
        cl, cl2 = CLOTH[look]
        if g == "f" and look in ("plain", "rich", "worker"): cl = FEM_CLOTH[h(cid) % len(FEM_CLOTH)]; cl2 = cl
        spec = {"name": c.get("name", cid), "skin": SKIN[h(cid + case["id"]) % len(SKIN)], "cloth": cl, "cloth2": cl2, "hair": hair,
                "voice": VOICES[g][used[g] % len(VOICES[g])]}
        used[g] += 1
        if g == "f": spec["long"] = True
        if g == "m" and c.get("beard"): spec["beard"] = True
        if look == "police": spec["cap"] = True
        if look == "detective": spec.update(coat=True, hat=True)
        if look in ("doctor", "judge"): spec["glasses"] = True
        if look == "nurse": spec["nurse"] = True
        cast[cid] = spec
    CAST.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(cast, indent=1))
    return cast


SYSTEM = ("You write scripts for 60-90 second animated YouTube Shorts that dramatise REAL historical crimes. "
          "Movie style: SHOW the story through characters acting and talking, not a narrator explaining. "
          "Strict rules: show ONLY this part's facts, in order (no arrests, trials, verdicts or discoveries unless they are in this part's facts); each person only does what the facts say they did; use only the facts given; never invent new names, dates, numbers, places or events; "
          "invented dialogue and small everyday actions are fine. No gore, no detailed violence, no methods of killing or poison "
          "amounts - the worst moments happen off-screen or are implied. Simple English a 12-year-old understands.")


def write_part(case, k, cast) -> dict:
    n = len(case["parts"]); beat = case["parts"][k - 1]
    prev = case["parts"][k - 2] if k > 1 else ""
    ids = {cid: v["name"] for cid, v in cast.items()}
    prompt = f"""Case: {case['name']} - {case['setting']}
People: {case['people']}
Characters you may use (id: name): {json.dumps(ids)}
Part {k} of {n}. THIS PART'S FACTS (dramatise only these): {beat}
{"Previous part's facts (for the recap only): " + prev if prev else "This is the first part."}
{"Next part's facts (do NOT reveal, only tease): " + case['parts'][k] if k < n else "This is the final part: end with the outcome."}

Write 11 to 15 shots. Each shot is one moment with ONE line of speech (max 16 words).
- Shot 1: speaker "nar". {"A hook that names the key person and pulls viewers in (no spoilers of later parts)." if k == 1 else "Recap starting 'Previously:' in max 16 words."}
- Shots 2 to the second-last: mostly characters talking to each other (at least 70% of shots). Narrator only if a fact cannot be shown.
- Second-last shot: speaker "nar", a suspenseful cliffhanger line.
- Last shot: speaker "nar": a question for viewers to answer in the comments (that is the end card).
- Use "title" (optional, max 5 words, CAPS) for place/time cards like "LONDON · 1888" or "THAT NIGHT", only when the scene changes.
Vocabulary:
- set: one of {SETS} (home = any indoor room; street = town street at night; ward = hospital ward; asylum/prison = cell; court = courtroom; grave = graveyard; dock = harbour; shore = coast)
- frame: one of {FRAMES}. two = 2 characters talking; solo = 1 character; face = close-up of 1 character's face (for strong emotion); three = 3 characters; bed = 1st character ill/asleep in bed, 2nd standing by (set home or ward); grave = 1-2 mourners at a graveside (set grave); court = [judge id, accused id] (set court); cell = 1 prisoner behind bars (set prison); walk = 1 character walking; establish = empty scene, no characters (narrator lines only).
- acts per character: one of {ACTS} (sick/sleep only for the bed character; peek = in bed pretending to sleep; cuffed = arrested; give = handing something).
Total spoken words at most 190.
JSON: {{"title":"catchy part title, max 6 words","shots":[{{"set":"","frame":"","who":["ids"],"acts":{{"id":"act"}},"speaker":"nar or id","text":"","title":""}}]}}"""
    for attempt in range(3):
        d = llm.chat_json(prompt, system=SYSTEM, temperature=0.75, max_tokens=5000)
        if check(case, beat, d): return d
        log.warning("checker rejected part %s of %s, retrying", k, case["id"])
    return d


def check(case, beat, d) -> bool:
    shots = d.get("shots") or []
    if len(shots) < 7: return False
    lines = "\n".join(f"{s.get('speaker')}: {s.get('text')}" for s in shots)
    try:
        r = llm.chat_json(f"Facts allowed: {beat}\nPeople in the case: {case['people']}\nScript:\n{lines}\n\n"
                          "The script may ONLY show the allowed facts above. Reject it (ok=false) if it: invents a new fact (name, date, number, place, event); "
                          "shows anything that is not in the allowed facts, like an arrest, trial, verdict, death or discovery from another part of the story; "
                          "has a person do something the facts say someone else did (e.g. a detective being arrested, a victim planning the crime); "
                          "or shows gore or a killing method in detail. Imagined dialogue and feelings are fine. "
                          'JSON: {"ok": true|false, "why": ""}', temperature=0, max_tokens=400, prefer=os.getenv("CHECKER_MODEL") or "qwen/qwen3-235b-a22b")
        if not r.get("ok", True): log.warning("checker: %s", r.get("why"))
        return bool(r.get("ok", True))
    except Exception as exc:
        log.warning("checker failed (%s); accepting", exc); return True


def place(fr, who, st, acts):
    """Engine characters + camera for one frame. Layouts match the checked crime.html cameras."""
    A = lambda i, x, z, ry=0, act=None: {"id": i, "x": x, "z": z, "ry": ry, "act": act or acts.get(i, "idle")}
    w = who
    if fr == "bed" and w:
        if st == "ward":
            ch = [A(w[0], -2.8, -2.4, 0, acts.get(w[0]) if acts.get(w[0]) in ("sick", "sleep", "peek") else "sick")]
            if len(w) > 1: ch.append(A(w[1], -1.6, -4.5, -0.8))
            return ch, "over", {}
        ch = [A(w[0], 2.2, -0.2, 0, acts.get(w[0]) if acts.get(w[0]) in ("sick", "sleep", "peek") else "sick")]
        if len(w) > 1: ch.append(A(w[1], 1.1, -2.0, 0.5))
        return ch, "bedroom", {"bed": True}
    if fr == "grave": return ([A(w[0], 0, 1.6, 0)] if len(w) == 1 else [A(i, x, 1.6, ry) for i, x, ry in zip(w[:2], (-0.8, 0.8), (0.3, -0.3))]), "grave", {}
    if fr == "court" and len(w) >= 2: return [A(w[0], 0, -8.9, 0), A(w[1], 1.0, -4.5, 3.14)], "courtw", {}
    if fr == "cell": return [A(w[0], 0, 0, 0)], "cell", {}
    if fr == "face": return [A(w[0], 0, 0, 0)], "face", {}
    if fr == "walk": return [A(w[0], 0, -2, 0, "walk")], "scene", {}
    if fr == "three" and len(w) >= 3: return [A(w[0], -1.2, 0.3, 0.4), A(w[1], 0, 0, 0), A(w[2], 1.2, 0.3, -0.4)], "scene", {}
    if len(w) >= 2: return [A(w[0], -0.8, 0.4, 0.5), A(w[1], 0.8, 0.4, -0.5)], "office", {}
    if len(w) == 1: return [A(w[0], 0, 0.3, 0)], "office", {}
    return [], {"ward": "ward", "shore": "wide"}.get(st, "scene"), {}


SAFE = {"bed": {"home", "ward"}, "grave": {"grave"}, "court": {"court"}, "cell": {"prison", "asylum"}}


TRIAL = re.compile(r"trial|tried|court|guilty|jury|acquit|verdict|sentenced|not proven|convict", re.I)
ARREST = re.compile(r"arrest|jail|prison|cell|caught|captur|held|custody|alcatraz|newgate|asylum|walled", re.I)


def convert(case, k, cast, d) -> dict:
    n = len(case["parts"]); shots = []; beat = case["parts"][k - 1]
    shots.append({"set": "home", "cam": "office", "chars": [], "hold": 2.8,
                  "intro": {"name": case["name"], "years": case["years"], "crime": case["tag"], "part": f"PART {k} OF {n}"}})
    raw = [s for s in d.get("shots", []) if isinstance(s, dict) and str(s.get("text", "")).strip()][:16]
    for i, s in enumerate(raw):
        last = i == len(raw) - 1
        st = s.get("set") if s.get("set") in SETS else "home"
        fr = s.get("frame") if s.get("frame") in FRAMES else "two"
        if fr in SAFE and st not in SAFE[fr]: st = sorted(SAFE[fr])[0] if fr != "bed" else "home"
        who = [x for x in s.get("who", []) if x in cast][:3]
        spk = s.get("speaker") if s.get("speaker") in cast else "nar"
        if spk != "nar" and spk not in who: who = [spk] + who
        if fr == "court" and (len(who) < 2 or not TRIAL.search(beat)): fr = "two"; st = "home" if st == "court" else st
        if fr == "cell" and not ARREST.search(beat): fr = "solo"; st = "home" if st in ("prison", "asylum") else st
        if st == "court" and not TRIAL.search(beat): st = "home"
        if fr == "establish" or not who: fr, who = "establish", []
        acts = {x: a for x, a in (s.get("acts") or {}).items() if a in ACTS}
        if fr != "bed": acts = {x: ("idle" if a in ("sick", "sleep", "peek") else a) for x, a in acts.items()}
        if not ARREST.search(beat): acts = {x: ("idle" if a == "cuffed" else a) for x, a in acts.items()}
        ch, cam, extra = place(fr, who, st, acts)
        text = " ".join(str(s["text"]).split()[:22])
        sh = {"set": st, "cam": cam, "chars": ch, "line": {"who": spk, "text": text}, **extra}
        if s.get("title"): sh["title"] = str(s["title"]).upper()[:40]
        if st in ("street", "forest", "dock", "shore") and h(case["id"] + str(k) + str(i)) % 3 == 0: sh["fx"] = ["rain"]
        if st in ("ward", "asylum", "home", "prison") and spk == "nar" and i > 0: sh["flick"] = True
        if last:
            if not text.endswith("?"): text = "What do you think happens next?"
            q = text
            sh = {"set": st, "cam": "office", "chars": [],
                  "card": {"h": q.upper()[:60], "p": "Comment below 👇", "f": f"Part {k + 1} next" if k < n else "Next true story coming soon"},
                  "line": {"who": "nar", "text": text + (f" Part {k + 1} is next." if k < n else "")}}
        elif i == len(raw) - 2:
            sh.setdefault("fx", []).append("lightning")
        shots.append(sh)
    title = str(d.get("title") or f"Part {k}")[:50]
    pretty = case["name"].title()
    return {"key": f"{case['id']}_p{k:02d}",
            "yt": {"title": f"{title} | {pretty} (True Story) Part {k} #shorts"[:100],
                   "description": f"Part {k} of {n}: {case['name'].title()}, {case['setting']}. A dramatised retelling of a real case; "
                                  f"dialogue and some scenes are imagined, the key events are real.\n\n#truecrime #horror #history #shorts",
                   "tags": ["true crime", "horror story", "history", "shorts", pretty.lower()]},
            "narrator": "am_michael", "cast": cast, "shots": shots}


def next_case(order):
    have = {k.rsplit("_p", 1)[0] for k in order}
    return next((c for c in ALL if c["id"] not in have), None)


def main(min_ahead=8):
    order = json.loads((EP / "order.json").read_text())
    done = json.loads(STATE.read_text())["done"] if STATE.exists() else {}
    left = [k for k in order if k not in done]
    if len(left) >= min_ahead: print("queue ok:", len(left), "parts ahead"); return
    case = next_case(order)
    if not case: print("CASE LIBRARY EMPTY"); return
    cast = make_cast(case)
    for k in range(1, len(case["parts"]) + 1):
        ep = convert(case, k, cast, write_part(case, k, cast))
        (EP / f"{ep['key']}.json").write_text(json.dumps(ep, indent=1, ensure_ascii=False))
        order.append(ep["key"]); print("wrote", ep["key"], "-", ep["yt"]["title"])
    (EP / "order.json").write_text(json.dumps(order, indent=1))
    remaining = len([c for c in ALL if c["id"] not in {k.rsplit("_p", 1)[0] for k in order}])
    print("cases left in library:", remaining)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
