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
import sys
from pathlib import Path

from pipeline import llm

log = logging.getLogger(__name__)
STUDIO = Path(__file__).resolve().parent.parent / "studio" / "explainer"
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL") or "deepseek-ai/deepseek-v4.1-flash"

COMMON = {
    "lab-title": 'opening card: {"kicker": "GETYR · <CHANNEL>", "title": "SHORT TITLE IN CAPS", "subtitle": "one line"}',
    "steps": 'numbered points that appear one by one: {"title": "...", "items": ["max 6 short items"]}',
    "flow": 'boxes joined by arrows, lit one by one with a moving dot (process, cause->effect, signal path): '
            '{"title": "...", "nodes": ["2-5 short labels"], "notes": ["one short sentence per node"]}',
    "formula": 'a formula with what each symbol means and a worked example: {"formula": "V = I × R", '
               '"terms": [["V", "voltage"], ...], "example": ["line 1", "line 2", "answer line"]}',
    "question": 'PAUSE & THINK card with a 3-2-1 countdown (narration asks the question, the NEXT scene '
                'answers it): {"q": "...", "options": ["2-3 short options"]}',
    "lab-outro": 'last card: {"title": "TOPIC", "lines": ["3 key takeaways"], "cta": "Subscribe for the next lesson"}',
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
    "ent": {"theme": "ent", "name": "ENT", "about": "today's big news explained (markets, economy, tech, science, world events)", "scenes": {}},
}


def _domain() -> dict:
    return DOMAIN.get(os.getenv("SEARCH_DOMAIN") or "ece", DOMAIN["ece"])


def _catalog(d: dict) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in {**COMMON, **d["scenes"]}.items())


def write_episode(script: dict, meta: dict) -> dict:
    """Turn the fact-checked narration into a lesson made of animated scenes."""
    d = _domain()
    ep = llm.chat_json(f"""You are the lead teacher and animation director of a YouTube channel about {d["about"]}.
Viewers are beginners who know nothing about this topic. Turn this narration into an animated LESSON.

TITLE: {meta.get("title")}
NARRATION:
{script["script"]}

Rules:
- Split the narration into 18-30 scenes, in order, 25-45 words each. Keep the narration's wording and
  facts; you may only add short connecting sentences and the questions below.
- Teach in depth like a great human teacher: explain how it ACTUALLY works, step by step, with the
  "why" behind every step. Talk to the viewer ("you"), use simple words and short sentences.
- Add 3 "question" scenes in the middle (after an idea is explained, before the next step), exactly like:
  {{"type": "question", "chapter": "2 · How it works", "q": "Which way does current flow now?",
    "options": ["Left to right", "Right to left"], "narration": "Quick question... Pause and think. Three, two, one."}}
  There is NO "answer" scene type: the scene right after a question is a normal visual scene whose
  narration starts by giving the answer.
- Every scene needs the visual that best SHOWS what is being said, chosen from this list only,
  with every field filled in correctly:
{_catalog(d)}
- Use "chapter" on every scene ("1 · The problem", "2 · How it works", ...).
- First scene "lab-title", last scene "lab-outro". Mix the scene types; never 3 of the same type in a row.
- "short": 4-6 scene numbers (0-based) that together make a gripping ~55 second vertical Short.
- "short_hook": one line (max 9 words) for the Short.

Return JSON: {{"scenes": [{{"type": "...", "chapter": "...", "narration": "...", <fields for that type>}}],
"short": [..], "short_hook": "..."}}""", "You design accurate, engaging animated lessons.",
                       temperature=0.4, max_tokens=12000, prefer=llm.WRITER_MODEL)
    ep.update({"title": meta.get("title", script.get("title")), "style": "lab", "theme": d["theme"],
               "badge": f"GETYR · {d['name']}", "tag": f"GETYR · {d['name']}", "engine": "kokoro",
               "kokoro_voice": os.getenv("STUDIO_VOICE") or "af_heart", "speed": float(os.getenv("STUDIO_SPEED") or 1.05)})
    return ep


# ------------------------------------------------------------------ checks done in code
REQUIRED = {"lab-title": ["title"], "steps": ["items"], "flow": ["nodes"], "formula": ["formula"], "question": ["q"],
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


def normalize(ep: dict) -> dict:
    """Repair what AI writers often get slightly wrong, in code, so a fixable slip never stops a video."""
    d = _domain(); allowed = set(COMMON) | set(d["scenes"])
    out = []
    for s in ep.get("scenes") or []:
        if not isinstance(s, dict):
            continue
        s["narration"] = (s.get("narration") or s.get("text") or "").strip()
        if len(s["narration"].split()) < 5:
            continue  # nothing to say -> no scene
        t = s.get("type")
        if t == "question":
            if not s.get("q"):
                qs = [x for x in _sentences(s["narration"]) if x.endswith("?")]
                last = _sentences(s["narration"])
                s["q"] = s.get("question") or (qs[-1] if qs else (last[-1] if last else s["narration"][:80]))
            s["options"] = [str(o) for o in (s.get("options") or s.get("choices") or [])][:3]
        elif t not in allowed:  # unknown type (e.g. "answer") -> numbered key points from the narration
            items = [x if len(x) <= 70 else x[:67].rsplit(" ", 1)[0] + "..." for x in _sentences(s["narration"])][:4]
            s = {"type": "steps", "chapter": s.get("chapter", ""), "narration": s["narration"],
                 "title": s.get("title", ""), "items": items or [s["narration"][:60]]}
        out.append(s)
    ep["scenes"] = out
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
        if len((s.get("narration") or "").split()) < 8:
            problems.append(f"scene {i}: narration missing or too short")
        for k in REQUIRED.get(t, []):
            if not s.get(k):
                problems.append(f"scene {i} ({t}): '{k}' is missing")
        if t == "question" and i + 1 < len(scenes) and scenes[i + 1].get("type") == "question":
            problems.append(f"scene {i}: two questions in a row")
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
    if scenes and scenes[0].get("type") != "lab-title":
        problems.append("first scene must be lab-title")
    if sum(s.get("type") == "question" for s in scenes) < 2:
        problems.append("needs at least 2 question scenes")
    ep["short"] = [i for i in ep.get("short", []) if isinstance(i, int) and 0 <= i < len(scenes)][:6] or [0, 1, 2, 3]
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
- every visual matches its narration exactly (labels, values, steps, which part does what, direction of
  current/flow, the order of steps, code output, command output);
- the explanation is deep and clear enough for a beginner, with no missing steps;
- each question is answered correctly by the next scene;
- only legal, ethical, defensive content; no invented statistics.
{lessons[:14000]}
Problems already found automatically: {"; ".join(problems) or "none"}

Allowed scene types and fields:
{_catalog(d)}

LESSON (JSON):
{json.dumps(ep, ensure_ascii=False)[:30000]}

Fix every problem directly in the lesson. Return JSON: {{"verdict": "ok" | "fixed" | "reject",
"issues": ["each problem you found and fixed"], "lesson": <the complete corrected lesson JSON, same format>}}
Use "reject" only if the topic cannot be taught correctly.""",
                              "You are an independent fact-checker. Be precise and strict.",
                              temperature=0.1, max_tokens=14000, prefer=REVIEWER_MODEL)
        except Exception as exc:
            log.warning("Reviewer round %d failed: %s", rnd, exc)
            break
        for issue in (r.get("issues") or [])[:20]:
            log.info("Reviewer %d: %s", rnd, issue)
        if r.get("verdict") == "reject":
            raise RuntimeError("Reviewer rejected the lesson: " + "; ".join(r.get("issues", [])[:3]))
        fixed = r.get("lesson")
        if isinstance(fixed, dict) and len(fixed.get("scenes") or []) >= 12:
            keep = {k: ep[k] for k in ("title", "style", "theme", "badge", "tag", "engine", "kokoro_voice", "speed") if k in ep}
            ep = {**fixed, **keep}
        if r.get("verdict") == "ok" and not check_episode(ep):
            log.info("Reviewer %d: lesson approved", rnd)
            break
    left = check_episode(ep)
    if left:
        raise RuntimeError("Lesson still has problems after review: " + "; ".join(left[:4]))
    return ep


# ------------------------------------------------------------------ render
def render(ep: dict, out_dir: Path) -> tuple[Path, Path]:
    """Voice + animation. Returns (16:9 lesson, 9:16 Short)."""
    work = STUDIO
    (work / "episodes").mkdir(exist_ok=True)
    epf = work / "episodes" / "current.json"
    epf.write_text(json.dumps(ep, ensure_ascii=False, indent=1))
    run = lambda *a: subprocess.run(list(a), cwd=work, check=True)
    run(sys.executable, "voice.py", "episodes/current.json", "public", "props.json")
    run("npx", "remotion", "render", "src/index.ts", "Explainer", "out/video.mp4", "--props=props.json", "--concurrency=4", "--crf=20")
    run("npx", "remotion", "render", "src/index.ts", "Short", "out/short.mp4", "--props=props_short.json", "--concurrency=4", "--crf=20")
    out_dir.mkdir(exist_ok=True)
    final, short = out_dir / "video_final.mp4", out_dir / "short_studio.mp4"
    for src, dst in ((work / "out" / "video.mp4", final), (work / "out" / "short.mp4", short)):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(work / "public" / "music.wav"),
                        "-filter_complex", "[1:a]volume=0.18[m];[0:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dst)], check=True)
    shutil.copy(epf, out_dir / "episode.json")
    return final, short


def make(script: dict, meta: dict, out_dir: Path, lessons: str = "") -> tuple[Path, Path, dict]:
    ep = write_episode(script, meta)
    if script.get("facts"):  # news: every claim must match today's reporting
        lessons += "\nSOURCE FACTS from today's reporting - every claim in the lesson must match these; remove anything not supported:\n" + script["facts"][:12000]
    ep = review_episode(ep, lessons)
    final, short = render(ep, out_dir)
    return final, short, ep
