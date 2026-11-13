"""GetYr Studio: our own animated lessons instead of NotebookLM.

1. write_episode: the AI turns the fact-checked script into a lesson made of animated scenes
   (the channel's template: blueprint circuits, code editor, terminal, flow diagrams...).
2. review_episode: a SECOND, different AI checks every scene (facts, numbers, formulas, code,
   commands, and that each picture matches what is said) and fixes it. Python code in CSE
   lessons is actually run, so the output shown on screen is the real output.
3. render: Kokoro voice + Remotion animation -> 16:9 lesson + 9:16 Short.
The channel is chosen by SEARCH_DOMAIN (ece | cse | cybersec | ent).
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
import sys
from pathlib import Path

from pipeline import llm

log = logging.getLogger(__name__)
STUDIO = Path(__file__).resolve().parent.parent / "studio" / "explainer"
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL") or "deepseek-ai/deepseek-v4.1-flash"
QUIZ = (os.getenv("STUDIO_QUIZ") or "off") == "on"   # questions are switched off for now

COMMON = {
    "lab-title": 'opening card: {"kicker": "GETYR · <CHANNEL>", "title": "SHORT TITLE IN CAPS", "subtitle": "one line"}',
    "steps": 'numbered points that appear one by one: {"title": "...", "items": ["max 6 short items"]}',
    "flow": 'boxes joined by arrows, lit one by one with a moving dot (process, cause->effect, signal path): '
            '{"title": "...", "nodes": ["2-5 short labels"], "notes": ["one short sentence per node"]}',
    "formula": 'a formula with what each symbol means and a worked example: {"formula": "V = I × R", '
               '"terms": [["V", "voltage"], ...], "example": ["line 1", "line 2", "answer line"]}',
    **({} if not QUIZ else {}),
    "question": 'PAUSE & THINK card with a 3-2-1 countdown; the answer is revealed automatically right after: '
                '{"q": "...", "options": ["2-3 short options"], "answer": "<the correct option, copied exactly>", '
                '"why": "<one sentence: why that is the answer>"}',
    "lab-outro": 'last card: {"title": "TOPIC", "lines": ["3 key takeaways"], "cta": "Subscribe for the next lesson"}',
    "image": 'a REAL photo or diagram of the exact thing being talked about (fetched from Wikimedia Commons): '
             '{"query": "<2-5 English words that find that exact thing, e.g. printed circuit board, Great Wall of China>", '
             '"label": "<short label>", "points": [{"x": 0-100, "y": 0-100, "label": "<part to point at>"}] (optional, only if sure where)}',
    "screen": 'a software window for "how to" steps - the menu path is clicked, a dialog opens, options are ticked: '
              '{"app": "KiCad PCB Editor", "menu": ["File", "Edit", "View", "Place", "Tools"], "path": ["File", "Plot"], '
              '"dialog": {"title": "Plot", "checks": ["All copper layers", "Mirror bottom layer"], "button": "Plot"}, "result": "Gerber files created"}',
    "installer": 'download + setup wizard, page by page: {"app": "KiCad 8", "site": "kicad.org/download", '
                 '"pages": ["Welcome", "License agreement", "Choose location", "Installing", "Finish"], "notes": ["one short note per page"]}',
    "terminal": 'terminal typing commands with their output: {"title": "terminal", "lines": [{"cmd": "..."}, {"out": "...", "good": true}]}',
    "diagram": 'labelled parts placed anywhere, joined by arrows, lit step by step (any process, structure or system): '
               '{"title": "...", "parts": [{"id": "a", "label": "Schematic", "x": 10, "y": 50, "shape": "box|circle|pill"}] (x/y 0-100, 2-6 parts), '
               '"arrows": [["a", "b", "label"]], "steps": [{"highlight": ["a"], "note": "short sentence"}]}',
}
DOMAIN = {
    "ece": {"theme": "ece", "name": "ECE", "about": "electronics and electrical engineering", "scenes": {
        "capacitor": 'close-up of capacitor plates with electrons: {"mode": "charge" | "discharge" | "cycle"}',
        "rectifier": 'ONLY for bridge rectifier / filter topics: live circuit + oscilloscope: {"cap": true|false, '
                     '"cycles": 0.25-3, "start": 0-1, "slow": true|false, "ripple": true|false, "tau": 0.5-3}',
        "wave": 'ONLY for rectifier/filter topics: oscilloscope: {"label": "...", "cycles": 2-3, "cap": true|false, '
                '"tau": 0.5-3, "ripple": true|false}',
    }},
    "cse": {"theme": "cse", "name": "CSE", "about": "programming and computer science", "scenes": {
        "code": 'code editor, typed line by line, then run step by step: {"lang": "python", "code": "lines joined '
                'with \\n (max 12 lines)", "steps": [{"line": 1, "note": "what this line does", "vars": {"x": 0}, '
                '"out": "printed text (only on print lines)"}]}',
        "array": 'array boxes with pointers i/j and animated swaps (sorting, searching): {"title": "...", '
                 '"values": [5, 2, 8], "steps": [{"i": 0, "j": 1, "note": "...", "swap": true, "done": [2]}]}',
    }},
    "cybersec": {"theme": "cyber", "name": "CYBERSEC", "about": "cybersecurity and ethical hacking (legal, own lab only, defensive)", "scenes": {
        "terminal": 'terminal typing real commands with their output (own lab IPs like 192.168.56.101 only): '
                    '{"title": "kali - your own lab only", "lines": [{"cmd": "..."}, {"out": "...", "bad": true|false, "good": true|false}]}',
        "network": 'network map, packets move between nodes one after another: {"title": "...", "nodes": [{"id": "a", '
                   '"label": "Attacker", "x": 250, "y": 400, "kind": "attacker|server|router|user|firewall|db|cloud"}], '
                   '"links": [["a", "b"]], "packets": [{"from": "a", "to": "b", "label": "SYN :80", "bad": true, "blocked": false}]} '
                   '(x 150-1450, y 150-650)',
    }},
    "ent": {"theme": "ent", "name": "ENT NEWS", "about": "today's big news, told as the story of what actually happened (markets, economy, tech, science, world events)",
            "story": True, "scenes": {
        "story": 'a moment of the story with flat illustrated characters (generic roles, never a real person\'s likeness): {"figures": [{"pose": '
                 '"stand|walk|point|shock|think|phone|sit|cheer|sad", "label": "Trader", "flip": false, "prop": "briefcase|mic"}] (1-3 figures), '
                 '"bubble": {"who": 0, "text": "max 6 words"}, "prop": "desk|screen|podium|city|rocket", "hud": HUD}',
        "phone": 'phone screen with news alerts / messages / market app: {"app": "News", "items": [{"from": "BREAKING", "text": "...", "alert": true}], "hud": HUD}',
        "chart": 'a number drawn live with a counter (prices, index, rate) - ONLY real numbers from the facts: {"label": "SENSEX", '
                 '"points": [82000, 81500, 80950], "unit": "" or "%", "bad": "down" or "up" (which direction is bad news), "note": "...", "hud": HUD}',
        "stamp": 'big rubber-stamp word: {"text": "BREAKING" | "WHY?" | "CONFIRMED" | "WHAT NEXT?", "sub": "one line", "hud": HUD}',
        }},
}


def _domain() -> dict:
    return DOMAIN.get(os.getenv("SEARCH_DOMAIN") or "ece", DOMAIN["ece"])


def _catalog(d: dict) -> str:
    c = "\n".join(f"- {k}: {v}" for k, v in {**COMMON, **d["scenes"]}.items())
    if d.get("story"):
        c += ('\nHUD = the live news corner: {"date": "12 NOV 2026", "time": "9:15 AM", "place": "MUMBAI", '
              '"stats": ["SENSEX 80,950 ▼"]} - real date/time/place/number from the facts; put it on story/phone/chart/stamp scenes.')
    return c


QUIZ_RULES = """- NO questions while teaching. First teach the whole concept completely. Then, at the very END (after the
  recap, before the last "lab-outro"), add a "Quick quiz" chapter with 3-5 "question" scenes that test ONLY
  what this lesson taught. Each question's narration must, in this order: read the question, explain in one
  or two sentences what it is really asking, then read EVERY option and explain what each one means.
  Exactly like:
  {"type": "question", "chapter": "Quick quiz", "q": "<question about something taught in THIS lesson>",
    "options": ["<option A>", "<option B>", "<option C>"], "answer": "<the correct option, copied exactly>",
    "why": "<one or two sentences: why it is correct, and why the others are wrong>",
    "narration": "Question two. <the question>. <what it is asking>. Option A, <option A> - <what that means>.
    Option B, <option B> - <what that means>. Option C, <option C> - <what that means>. Which one is right?"}
  Never say "pause and think" or count "three, two, one" - the countdown is shown silently. Never reveal
  the answer in the question's narration: the answer scene ("The correct answer is ...") is added after it
  automatically.
"""


def write_episode(script: dict, meta: dict) -> dict:
    """Turn the fact-checked narration into a lesson made of animated scenes (retries if the AI
    returns nothing usable)."""
    need = int(len(script.get("script", "").split()) * 0.7)
    best = None
    for attempt in range(3):
        ep = _write_once(script, meta, attempt, need)
        sc = ep.get("scenes") or (ep.get("lesson") or {}).get("scenes") or ep.get("Scenes") or []
        words = sum(len(str(x.get("narration", "")).split()) for x in sc if isinstance(x, dict)) if isinstance(sc, list) else 0
        if isinstance(sc, list) and len(sc) >= 10:
            ep["scenes"] = sc
            if words >= need:
                return ep
            if best is None or words > best[0]:
                best = (words, ep)
        log.warning("Lesson writer returned %d scenes, %d of the %d words needed - trying again",
                    len(sc) if isinstance(sc, list) else 0, words, need)
    if best and best[0] >= need * 0.6:
        log.info("Using the longest lesson (%d words)", best[0])
        return best[1]
    raise RuntimeError("Lesson writer returned no usable lesson")


def _write_once(script: dict, meta: dict, attempt: int, need: int = 600) -> dict:
    d = _domain()
    ep = llm.chat_json(f"""You are the lead teacher and animation director of a YouTube channel about {d["about"]}.
Viewers are beginners who know nothing about this topic. Turn this narration into an animated LESSON.
{"For this NEWS channel: tell it as the STORY of what actually happened, in time order, like a gripping animated story - who, where, when (show it in the HUD), what people saw on their phones, how the numbers moved, then WHY, then what it means and what happens next. Start with a 'stamp' BREAKING scene. Mostly use story/phone/chart/stamp scenes. Only real facts." if d.get("story") else ""}

TITLE: {meta.get("title")}
NARRATION:
{script["script"]}

Rules:
- Split the narration into 18-30 scenes, in order, 25-45 words each. Use ALL of the narration - do not
  summarise or shorten it: the scenes' narration together must be at least {need} words. Keep its wording
  and facts; you may only add short connecting sentences.
- Teach in depth like a great human teacher: explain how it ACTUALLY works, step by step, with the
  "why" behind every step. Talk to the viewer ("you"), use simple words and short sentences.
{QUIZ_RULES if QUIZ else "- No questions anywhere in the lesson. Just teach."}
- SHOW, DON'T JUST TELL: every scene's picture must show EXACTLY what its narration is saying at that
  moment - the real object (image), the real menu clicks (screen), the real parts and connections (diagram,
  circuit, code, network...). A title card or a text list is NOT a visual: use "steps" only for a recap,
  never more than 2 "steps" scenes in the whole lesson. If you talk about a thing, show that thing.
- The viewer knows NOTHING. For anything they must download, install or set up, SHOW every step, one scene per
  step, and explain in the narration what the step does and why: "installer" for a setup wizard (with the
  official site), "screen" for clicks inside an app, "terminal" for commands (say what each command means).
  Chosen from this list only, with every field filled in correctly:
{_catalog(d)}
- Use "chapter" on every scene ("1 · The problem", "2 · How it works", ...).
- First scene "lab-title", last scene "lab-outro". Mix the scene types; never 3 of the same type in a row.
- "short_scenes": a SEPARATE vertical Short that explains the WHOLE concept of this lesson in 50-60 seconds
  (about 140-160 words in total), so a viewer who only sees the Short still understands it - 6-9 scenes,
  same scene types, narration 12-25 words each, fast and clear:
  scene 1 = hook (surprising fact or question in the first 2 seconds, on a "lab-title" or "stamp"),
  then the complete idea in order: what it is -> how it works, step by step -> the key takeaway,
  each step shown with its best visual,
  last scene = "lab-outro" with "cta": "Full video on our channel" and narration
  "For the detailed explanation, watch the full video on our channel."
  No questions in the Short.

Return JSON: {{"scenes": [{{"type": "...", "chapter": "...", "narration": "...", <fields for that type>}}],
"short_scenes": [...], "cover": "<2-4 BIG words for the thumbnail, the hook>", "cover_highlight": "<the one word to colour>"}}""", "You design accurate, engaging animated lessons.",
                       temperature=0.4 + 0.1 * attempt, max_tokens=16000,
                       prefer=llm.WRITER_MODEL if attempt < 2 else REVIEWER_MODEL)
    ep.update({"title": meta.get("title", script.get("title")), "style": "lab", "theme": d["theme"],
               "badge": f"GETYR · {d['name']}", "tag": f"GETYR · {d['name']}", "engine": "kokoro",
               "kokoro_voice": os.getenv("STUDIO_VOICE") or "af_heart", "speed": float(os.getenv("STUDIO_SPEED") or 1.05)})
    if d.get("captions"):
        ep["captions"] = d["captions"]
    return ep


# ------------------------------------------------------------------ checks done in code
REQUIRED = {"installer": ["pages"], "image": ["query"], "screen": ["path"], "diagram": ["parts"], "story": ["figures"], "phone": ["items"], "chart": ["points"], "stamp": ["text"], "lab-title": ["title"], "steps": ["items"], "flow": ["nodes"], "formula": ["formula"], "question": ["q"],
            "lab-outro": ["title"], "capacitor": [], "rectifier": [], "wave": [], "code": ["code", "steps"],
            "array": ["values", "steps"], "terminal": ["lines"], "network": ["nodes", "links", "packets"]}


def _run_python(code: str) -> list[str] | None:
    try:
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=10)
        return r.stdout.splitlines() if r.returncode == 0 else None
    except Exception:
        return None


def _sentences(t: str) -> list[str]:
    return [x.strip() for x in re.findall(r"[^.!?]+[.!?]", t or "") if len(x.split()) >= 3]


def normalize(ep: dict, final_pass: bool = False) -> dict:
    """Repair what AI writers often get slightly wrong, in code, so a fixable slip never stops a video."""
    d = _domain(); allowed = set(COMMON) | set(d["scenes"])
    out = []
    for s in ep.get("scenes") or []:
        if not isinstance(s, dict):
            continue
        s["narration"] = (s.get("narration") or s.get("text") or "").strip()
        if len(s["narration"].split()) < 5:
            pts = s.get("items") or s.get("nodes") or s.get("lines") or []
            pts = [p if isinstance(p, str) else (p.get("cmd") or p.get("out") or "") for p in pts]
            said = ". ".join(p.rstrip(".") for p in pts if p).strip()
            if len(said.split()) >= 5:
                s["narration"] = (s["narration"] + " " + said + ".").strip()  # read out what is on screen
            else:
                continue  # nothing to say -> no scene
        t = s.get("type")
        if t == "question":
            if not s.get("q"):
                qs = [x for x in _sentences(s["narration"]) if x.endswith("?")]
                last = _sentences(s["narration"])
                s["q"] = s.get("question") or (qs[-1] if qs else (last[-1] if last else s["narration"][:80]))
            s["options"] = [str(o) for o in (s.get("options") or s.get("choices") or [])][:3]
        elif t not in allowed or any(not s.get(k) for k in REQUIRED.get(t, [])):
            # unknown type (e.g. "answer") or missing parts -> numbered key points from the narration
            items = [x if len(x) <= 70 else x[:67].rsplit(" ", 1)[0] + "..." for x in _sentences(s["narration"])][:4]
            s = {"type": "steps", "chapter": s.get("chapter", ""), "narration": s["narration"],
                 "title": s.get("title", ""), "items": items or [s["narration"][:60]]}
        out.append(s)
    # questions go to the end (Quick quiz), before the outro; at most 3
    qs = [x for x in out if x.get("type") == "question" and not x.get("reveal")][:5] if QUIZ else []
    rest = [x for x in out if x.get("type") != "question"]  # (without QUIZ every question is removed)
    outro = [x for x in rest if x.get("type") == "lab-outro"]
    rest = [x for x in rest if x.get("type") != "lab-outro"]
    for q in qs:
        q["chapter"] = "Quick quiz"
        q["narration"] = re.sub(r"(?i)\b(pause and think|take a moment to think|think about it)\b[.!,]*|\b(three|3)[,.]?\s*(two|2)[,.]?\s*(one|1)\b[.!]*", "", q["narration"]).strip()
        if len(q["narration"].split()) < 4:
            q["narration"] = q.get("q", "")
    out = rest + qs + outro
    final = []
    for i, s in enumerate(out):
        final.append(s)
        if s.get("type") == "question" and not s.get("reveal"):
            nxt = out[i + 1] if i + 1 < len(out) else {}
            if nxt.get("reveal"):
                continue
            if s.get("answer"):
                why = (s.get("why") or "").strip()
                opts = [str(o) for o in s.get("options", [])]
                norm = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower())
                k = next((j for j, o in enumerate(opts) if norm(o) == norm(s["answer"])), -1)
                letter = f"option {chr(65 + k)}, " if k >= 0 else ""
                final.append({"type": "question", "reveal": True, "chapter": s.get("chapter", ""), "q": s.get("q", ""),
                              "options": opts, "answer": s["answer"],
                              "narration": f"The correct answer is {letter}{s['answer']}. {why}".strip()})
            elif final_pass:
                final.pop()  # a question nobody answers is worse than no question
    ep["scenes"] = final
    return ep


def check_episode(ep: dict) -> list[str]:
    """Problems we can find without an AI. Also corrects code output to the real output."""
    d = _domain(); allowed = set(COMMON) | set(d["scenes"])
    problems = []
    normalize(ep)
    scenes = ep.get("scenes") or []
    if len(scenes) < 12:
        problems.append(f"only {len(scenes)} scenes - the lesson is too short")
    for i, s in enumerate(scenes):
        t = s.get("type")
        if t not in allowed:
            problems.append(f"scene {i}: type '{t}' is not allowed"); continue
        if len((s.get("narration") or "").split()) < 5:
            problems.append(f"scene {i}: narration missing or too short")
        for k in REQUIRED.get(t, []):
            if not s.get(k):
                problems.append(f"scene {i} ({t}): '{k}' is missing")
        if t == "question" and not s.get("reveal") and not s.get("answer"):
            problems.append(f"scene {i} (question): 'answer' and 'why' are missing - add the correct answer")
        if t == "code" and s.get("lang", "python") == "python" and s.get("code"):
            real = _run_python(s["code"])
            if real is None:
                problems.append(f"scene {i}: the Python code does not run")
            else:
                shown = [st for st in s.get("steps", []) if st.get("out") is not None]
                if [str(st["out"]) for st in shown] != real[:len(shown)] or len(shown) != len(real):
                    log.info("Scene %d: code output corrected to the real output %s", i, real)
                    for st in s.get("steps", []):
                        st.pop("out", None)
                    if s.get("steps"):
                        s["steps"][-1]["out"] = "\n".join(real) if real else "(no output)"
        if t == "network":
            ids = {n.get("id") for n in s.get("nodes", [])}
            if any(a not in ids or b not in ids for a, b in s.get("links", [])) or \
               any(p.get("from") not in ids or p.get("to") not in ids for p in s.get("packets", [])):
                problems.append(f"scene {i}: network refers to a node that does not exist")
    if scenes and scenes[0].get("type") not in ("lab-title", "stamp"):
        problems.append("first scene must be lab-title")
    if QUIZ and sum(s.get("type") == "question" and not s.get("reveal") for s in scenes) < 1:
        problems.append("needs at least 1 quiz question scenes")
    ep["short"] = [i for i in ep.get("short", []) if isinstance(i, int) and 0 <= i < len(scenes)][:6] or [0, 1, 2, 3]
    ss = [x for x in (ep.get("short_scenes") or []) if isinstance(x, dict) and x.get("type") in allowed - {"question"}
          and len((x.get("narration") or "").split()) >= 3 and all(x.get(k) for k in REQUIRED.get(x.get("type"), []))]
    if len(ss) >= 3:
        if ss[-1].get("type") != "lab-outro":
            ss.append({"type": "lab-outro", "title": (ep.get("title") or "").upper()[:40], "lines": [], "cta": "Full video on our channel",
                       "narration": "For the detailed explanation, watch the full video on our channel."})
        ep["short_scenes"] = ss[:10]
    else:
        ep.pop("short_scenes", None)
    return problems


def review_episode(ep: dict, lessons: str = "") -> dict:
    """A second, different AI checks the lesson scene by scene and fixes it (2 rounds)."""
    d = _domain()
    for rnd in (1, 2):
        problems = check_episode(ep)
        try:
            r = llm.chat_json(f"""You are a strict senior professor and engineer in {d["about"]}, reviewing an animated
lesson for complete beginners BEFORE it is published. Check EVERY scene:
- every fact, number, unit, formula, definition, date, command and line of code is correct;
- every visual SHOWS exactly what its narration says at that moment (labels, values, steps, which part does
  what, direction of current/flow, the order of steps, code output, command output). If a scene only shows text
  or a title while the narration talks about a real thing, change it to a visual that shows that thing
  (image with a precise query, screen for software steps, diagram, or the channel's own scenes);
- the explanation is deep and clear enough for a beginner, with no missing steps;
- each quiz question (3-5, only at the end) has the CORRECT "answer" (one of its options) and a correct "why";
  its narration reads the question, explains it, and reads and explains every option, without revealing the answer;
- only legal, ethical, defensive content; no invented statistics.
{lessons[:14000]}
Problems already found automatically: {"; ".join(problems) or "none"}

Allowed scene types and fields:
{_catalog(d)}

LESSON (JSON):
{json.dumps(ep, ensure_ascii=False)[:30000]}

Return ONLY the changes (do not repeat the whole lesson). JSON:
{{"verdict": "ok" | "fixed" | "reject", "issues": ["each problem you found"],
  "fixes": [{{"scene": <scene number, 0-based>, "set": {{<only the fields to replace, e.g. "narration": "...", "items": [...]}}}}]}}
Use "reject" only if the topic cannot be taught correctly.""",
                              "You are an independent fact-checker. Be precise and strict.",
                              temperature=0.1, max_tokens=6000, prefer=REVIEWER_MODEL)
        except Exception as exc:
            log.warning("Reviewer round %d failed: %s", rnd, exc)
            break
        for issue in (r.get("issues") or [])[:20]:
            log.info("Reviewer %d: %s", rnd, issue)
        if r.get("verdict") == "reject":
            raise RuntimeError("Reviewer rejected the lesson: " + "; ".join(r.get("issues", [])[:3]))
        applied = 0
        for fx in r.get("fixes") or []:
            try:
                i = int(fx.get("scene")); upd = fx.get("set") or {}
                if 0 <= i < len(ep["scenes"]) and isinstance(upd, dict) and upd:
                    ep["scenes"][i].update(upd); applied += 1
            except (TypeError, ValueError):
                continue
        log.info("Reviewer %d: %d fixes applied", rnd, applied)
        if r.get("verdict") == "ok" and not check_episode(ep):
            log.info("Reviewer %d: lesson approved", rnd)
            break
    normalize(ep, final_pass=True)
    left = [p for p in check_episode(ep) if "answer" not in p and "question scenes" not in p]
    if left:
        raise RuntimeError("Lesson still has problems after review: " + "; ".join(left[:4]))
    return ep


# ------------------------------------------------------------------ render
OK_LICENSES = ("cc0", "public domain", "cc by", "cc-by", "pd")


def fetch_images(ep: dict, work: Path) -> list[str]:
    """Download a freely licensed photo for every image scene (Wikimedia Commons). Scenes whose
    image cannot be found become a diagram-free 'steps' recap of their narration (never a blank)."""
    import httpx
    (work / "public" / "img").mkdir(parents=True, exist_ok=True)
    credits, n = [], 0
    for sc in (ep.get("scenes") or []) + (ep.get("short_scenes") or []):
        if sc.get("type") != "image" or sc.get("src"):
            continue
        try:
            r = httpx.get("https://commons.wikimedia.org/w/api.php", timeout=30, headers={"User-Agent": "GetYrStudio/1.0 (educational videos)"},
                          params={"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 8,
                                  "gsrsearch": f"filetype:bitmap {sc['query']}", "prop": "imageinfo",
                                  "iiprop": "url|extmetadata|size", "iiurlwidth": 1600})
            pages = sorted((r.json().get("query") or {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
            for pg in pages:
                ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata") or {}
                lic = (md.get("LicenseShortName", {}).get("value") or "").lower()
                if not any(x in lic for x in OK_LICENSES) or ii.get("width", 0) < 800:
                    continue
                img = None
                for wait in (0, 4, 10, 20):  # Wikimedia asks for polite, slow downloads
                    time.sleep(wait + 1.5)
                    img = httpx.get(ii.get("thumburl") or ii["url"], timeout=60, follow_redirects=True,
                                    headers={"User-Agent": "GetYrStudio/1.0 (https://github.com/sharath-IXVII; educational videos)"})
                    if img.status_code != 429:
                        break
                if img is None or img.status_code >= 400:
                    continue
                n += 1; name = f"img/{n}.jpg"; (work / "public" / name).write_bytes(img.content)
                artist = re.sub(r"<[^>]+>", "", md.get("Artist", {}).get("value") or "Wikimedia Commons").strip()[:60]
                sc["src"] = name; sc["credit"] = f"{artist} / {md.get('LicenseShortName', {}).get('value', '')}"
                credits.append(f"{pg.get('title', '').replace('File:', '')} - {sc['credit']} - {ii.get('descriptionurl', '')}")
                break
        except Exception as exc:
            log.warning("Image search failed for '%s': %s", sc.get("query"), exc)
        if not sc.get("src"):
            log.info("No licensed image for '%s' - showing key points instead", sc.get("query"))
            said = sc.get("narration", ""); pts = [x for x in re.findall(r"[^.!?]+[.!?]", said) if len(x.split()) >= 3][:4]
            sc.clear(); sc.update({"type": "steps", "title": "", "items": [p.strip()[:70] for p in pts] or [said[:70]], "narration": said})
    return credits


def render(ep: dict, out_dir: Path) -> tuple[Path, Path]:
    """Voice + animation. Returns (16:9 lesson, 9:16 Short)."""
    work = STUDIO
    ep["credits"] = fetch_images(ep, work)
    (work / "episodes").mkdir(exist_ok=True)
    epf = work / "episodes" / "current.json"
    epf.write_text(json.dumps(ep, ensure_ascii=False, indent=1))
    run = lambda *a: subprocess.run(list(a), cwd=work, check=True)
    run(sys.executable, "voice.py", "episodes/current.json", "public", "props.json")
    run("npx", "remotion", "render", "src/index.ts", "Explainer", "out/video.mp4", "--props=props.json", "--concurrency=4", "--crf=20")
    run("npx", "remotion", "render", "src/index.ts", "Short", "out/short.mp4", "--props=props_short.json", "--concurrency=4", "--crf=20")
    out_dir.mkdir(exist_ok=True)
    final, short = out_dir / "video_final.mp4", out_dir / "short_studio.mp4"
    for src, dst, bedf in ((work / "out" / "video.mp4", final, "music.wav"), (work / "out" / "short.mp4", short, "music_short.wav")):
        bedp = work / "public" / bedf
        if not bedp.exists():
            bedp = work / "public" / "music.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(bedp),
                        "-filter_complex", "[1:a]volume=0.45[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dst)], check=True)
    shutil.copy(epf, out_dir / "episode.json")
    try:  # designed thumbnail: big bold words + highlighted keyword + channel icon
        props = json.loads((work / "props.json").read_text())
        props["ep"].setdefault("cover", ep.get("cover") or ep.get("title"))
        (work / "props_thumb.json").write_text(json.dumps(props, ensure_ascii=False))
        run("npx", "remotion", "still", "src/index.ts", "Thumbnail", str((out_dir / "thumb_studio.png").resolve()), "--props=props_thumb.json")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_dir / "thumb_studio.png"), "-q:v", "2", str(out_dir / "thumb_studio.jpg")], check=True)
    except Exception as exc:
        log.warning("Designed thumbnail failed, using a frame instead: %s", exc)
    return final, short


def make(script: dict, meta: dict, out_dir: Path, lessons: str = "") -> tuple[Path, Path, dict]:
    ep = write_episode(script, meta)
    ep.setdefault("cover", meta.get("cover_text") or meta.get("title"))
    if script.get("facts"):  # news: every claim must match today's reporting
        lessons += "\nSOURCE FACTS from today's reporting - every claim in the lesson must match these; remove anything not supported:\n" + script["facts"][:12000]
    ep = review_episode(ep, lessons)
    final, short = render(ep, out_dir)
    if ep.get("credits"):  # licence credits for the photos used
        meta["description"] = (meta.get("description", "") + "\n\nImage credits (Wikimedia Commons):\n" + "\n".join(ep["credits"]))[:4900]
    return final, short, ep
