"""Growth mode: videos on what people are searching for right now in the channel's field
(e.g. "how to install kali linux", "python roadmap 2026", "how does 5g work").

Each run gathers live YouTube search suggestions (autocomplete) for the channel's seed
searches, scores the phrases (how often and how high they appear), drops anything already
made, lets the AI pick the strongest video idea, writes an in-depth script, fact-checks
it and packages it professionally. Topics are never repeated (state/search_topics_used.json).
Set CONTENT_MODE=courses (or electronics) to go back to the courses later.
"""

import datetime as dt
import json
import logging
import os
import re
from pathlib import Path

from pipeline import llm
from pipeline.packaging import search_suggestions

log = logging.getLogger(__name__)
USED_FILE = Path("state/search_topics_used.json")

DOMAINS = {
    "ent": {
        "about": "fascinating general knowledge: history and ancient civilisations, how famous "
                 "things were built, science and space, nature, the human body, mysteries and "
                 "the real story behind what is trending",
        "seeds": ["how were the pyramids built", "how was", "how did ancient", "ancient egypt",
                  "ancient civilizations", "history of", "what happened to", "mystery of",
                  "why did", "lost city", "roman empire", "titanic", "world war 2", "seven wonders",
                  "black hole", "universe", "space", "how big is", "what if", "deep ocean",
                  "bermuda triangle", "dinosaurs", "human body", "how does the brain",
                  "inventions that changed the world", "unsolved mysteries", "how was the great wall built",
                  "how did they build", "volcano", "earthquake", "solar eclipse"],
        "safety": "Separate proven facts from theories and say clearly when historians or "
                  "scientists disagree. No conspiracy theories presented as fact.",
        "trends": True,
    },
    "cybersec": {
        "about": "cybersecurity and ethical hacking (legal, educational, defensive mindset)",
        "seeds": ["kali linux", "how to install kali linux", "ethical hacking", "how hackers",
                  "nmap", "wireshark", "metasploit", "burp suite", "cybersecurity roadmap",
                  "how to become ethical hacker", "bug bounty", "tryhackme", "hack the box",
                  "password cracking", "phishing", "wifi hacking", "osint", "ctf for beginners",
                  "linux for hackers", "vpn", "is my phone hacked", "cybersecurity jobs",
                  "comptia security+", "ceh", "ransomware", "dark web", "sql injection",
                  "hashcat", "hydra", "john the ripper", "nmap tutorial", "metasploit tutorial",
                  "sqlmap", "aircrack-ng", "gobuster", "burp suite tutorial", "wireshark tutorial",
                  "kali linux tools", "password attacks", "cyber security course"],
        "safety": "Teach only legal, ethical use on your own lab or with permission. Never "
                  "give steps to attack real people or systems; focus on how it works and "
                  "how to defend.",
    },
    "cse": {
        "about": "programming, computer science, AI and developer careers",
        "seeds": ["python", "learn python", "java", "javascript", "dsa", "leetcode",
                  "how to learn coding", "coding roadmap", "web development", "react",
                  "chatgpt", "ai agents", "machine learning", "how to get a job as software engineer",
                  "git and github", "sql", "linux commands", "system design", "c programming",
                  "best programming language", "how computers work", "how ai works",
                  "placement preparation", "projects for resume", "vs code",
                  "python tutorial", "python for beginners", "python course", "java tutorial",
                  "java course", "c programming tutorial", "dsa course", "oops concepts",
                  "sql tutorial", "operating system", "computer networks", "dbms"],
        "safety": "",
    },
    "ece": {
        "about": "electronics, electrical engineering and how technology works",
        "seeds": ["how does", "how it works", "electronics", "arduino", "arduino projects",
                  "esp32", "raspberry pi", "how phone charger works", "how 5g works",
                  "how solar panel works", "electric car battery", "semiconductor",
                  "how chips are made", "pcb design", "transistor", "inverter",
                  "electronics projects", "ece projects", "vlsi", "embedded systems",
                  "how wifi works", "how batteries work", "motor",
                  "filters in electronics", "rectifier", "clipper circuit", "clamper circuit",
                  "zener diode", "diode", "voltage regulator", "bjt transistor", "mosfet",
                  "op amp", "oscillator", "amplifier", "analog electronics",
                  "digital electronics", "logic gates", "flip flop", "multiplexer",
                  "network theory", "signals and systems", "power electronics"],
        "safety": "Include electrical safety where relevant.",
    },
}

SYSTEM = (
    "You are the head writer of a fast-growing, professional educational YouTube channel. "
    "You make videos on exactly what people search for, accurate and in depth, with a hook "
    "that keeps viewers watching to the end."
)

VISUAL_STYLE = (
    "Animate the whole video as a premium, modern explainer: smooth motion graphics, "
    "animated diagrams that build step by step, realistic screens and terminals where "
    "relevant, cutaways and zoom-ins, clear labels and arrows. Every scene moves - no still "
    "slides. On-screen text only for the title and short labels. No logos or brand names. "
    "TECHNICAL ACCURACY COMES FIRST: every circuit, symbol and diagram must be exactly as "
    "the source describes it - standard component symbols, correct polarity (electrolytic "
    "capacitor + side to the higher voltage, diode arrow pointing in the direction of "
    "conventional current, battery + and - correct), correct transistor pins, correct current "
    "and signal direction, correct wiring, and commands/code shown exactly as written in the "
    "source. Never invent a circuit or a connection. If a detail is not stated in the source, "
    "show a simple labelled block diagram instead of a detailed schematic."
)


TUTORIAL_STYLE = (
    "THIS IS A STEP-BY-STEP TUTORIAL: the viewer must be able to follow along and finish the "
    "task. Show EVERY step from the source, in the same order, each as its own scene, with the "
    "exact command, menu path, button or setting written clearly on screen (realistic "
    "terminal / settings screens). Never skip, merge or summarise steps, and never replace the "
    "steps with background or history. Keep each command on screen long enough to copy."
)
_HOWTO = re.compile(r"\b(how to|install|setup|set up|configure|tutorial|step by step|"
                    r"fix|enable|download|commands?|guide)\b", re.I)


def is_tutorial(pick: dict) -> bool:
    """The searcher wants to DO something (install, set up, use a tool), not just understand it."""
    return bool(_HOWTO.search(f'{pick.get("search_phrase", "")} {pick.get("topic", "")}'))


def _domain() -> dict:
    return DOMAINS[os.getenv("SEARCH_DOMAIN") or DEFAULT_DOMAIN]


DEFAULT_DOMAIN = "ent"


def used() -> list[str]:
    return json.loads(USED_FILE.read_text()) if USED_FILE.exists() else []


def mark_used(topic: str) -> None:
    USED_FILE.parent.mkdir(parents=True, exist_ok=True)
    USED_FILE.write_text(json.dumps(used() + [topic], indent=1, ensure_ascii=False))


_CHANNEL: dict = {}


def channel_videos() -> dict:
    """The channel's real long videos from YouTube: {"titles": [...], "winners": [(views, title)]}.
    Winners = most-viewed videos; new topics follow what this audience already watches."""
    if _CHANNEL:
        return _CHANNEL
    titles, winners = [], []
    try:
        from pipeline.youtube_upload import _client
        yt = _client()
        up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0][
            "contentDetails"]["relatedPlaylists"]["uploads"]
        ids, tok = [], None
        while len(ids) < 200:
            r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50,
                                        pageToken=tok).execute()
            ids += [i["contentDetails"]["videoId"] for i in r["items"]]
            tok = r.get("nextPageToken")
            if not tok:
                break
        for i in range(0, len(ids), 50):
            for v in yt.videos().list(part="snippet,statistics,contentDetails",
                                      id=",".join(ids[i:i + 50])).execute()["items"]:
                t = v["snippet"]["title"]
                titles.append(t)
                if "M" in v["contentDetails"]["duration"] or "H" in v["contentDetails"]["duration"]:
                    if "#shorts" not in t.lower():
                        winners.append((int(v["statistics"].get("viewCount", 0)), t))
        winners = [w for w in sorted(winners, reverse=True)[:12] if w[0] >= 20]
        log.info("Channel winners: %s", "; ".join(f"{t[:50]} ({n})" for n, t in winners[:6]))
    except Exception as exc:
        log.warning("Could not read the channel's videos: %s", exc)
    _CHANNEL.update({"titles": titles, "winners": winners})
    return _CHANNEL


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#]+", s.lower()) if len(w) > 2}


_CANDS: list = []


def candidates() -> list[tuple[str, float]]:
    """Live search phrases with a popularity score (higher = searched more)."""
    if _CANDS:
        return _CANDS
    scores: dict[str, float] = {}
    for seed in _domain()["seeds"]:
        for rank, phrase in enumerate(search_suggestions(seed, limit=10)):
            scores[phrase] = scores.get(phrase, 0) + (10 - rank)
    done = [_words(u) for u in _made_before() + channel_videos()["titles"]]
    out = []
    for phrase, score in scores.items():
        w = _words(phrase)
        if len(w) < 2 or any(len(w & d) >= max(2, len(w) - 1) for d in done):
            continue  # too vague, or already made
        out.append((phrase, score))
    _CANDS.extend(sorted(out, key=lambda x: -x[1])[:60])
    return _CANDS


LOW_DEMAND_FILE = Path("state/low_demand.json")


def search_demand(phrase: str) -> int | None:
    """How big the audience for a search is. YouTube doesn't publish search counts, so we use
    the next best proof: the median views of the top 10 YouTube results for that phrase.
    Many people search it -> the top results have many views. None = could not check."""
    found = _demand_from_page(phrase)  # free; keeps the API key's daily quota for other jobs
    key = os.getenv("YOUTUBE_API_KEY")
    if found is not None or not key:
        return found
    import httpx
    try:
        r = httpx.get("https://www.googleapis.com/youtube/v3/search", timeout=30, params={
            "part": "id", "q": phrase, "type": "video", "maxResults": 10,
            "relevanceLanguage": "en", "key": key})
        r.raise_for_status()
        ids = [i["id"]["videoId"] for i in r.json().get("items", [])]
        if not ids:
            return 0
        r = httpx.get("https://www.googleapis.com/youtube/v3/videos", timeout=30, params={
            "part": "statistics", "id": ",".join(ids), "key": key})
        r.raise_for_status()
        views = sorted(int(v["statistics"].get("viewCount", 0)) for v in r.json()["items"])
        return views[len(views) // 2] if views else 0
    except Exception as exc:
        log.warning("Could not check search demand for '%s': %s", phrase, exc)
        return None


def _demand_from_page(phrase: str) -> int | None:
    """Same measure without an API key: read the view counts on YouTube's public search page."""
    import httpx
    try:
        r = httpx.get("https://www.youtube.com/results", timeout=30, follow_redirects=True,
                      params={"search_query": phrase, "sp": "EgIQAQ%3D%3D", "hl": "en", "gl": "US"},
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                               "Accept-Language": "en-US,en;q=0.9"},
                      cookies={"CONSENT": "YES+1", "SOCS": "CAI"})
        r.raise_for_status()
        counts = [int(n.replace(",", "")) for n in re.findall(
            r'"viewCountText":\{"simpleText":"([\d,]+) views"', r.text)][:10]
        if not counts:
            log.warning("No view counts on the YouTube search page for '%s'", phrase)
            return None
        counts.sort()
        return counts[len(counts) // 2]
    except Exception as exc:
        log.warning("Could not read the YouTube search page for '%s': %s", phrase, exc)
        return None


_STOP = {"the", "and", "for", "how", "what", "why", "with", "your", "you", "are", "does",
         "work", "works", "explained", "tutorial", "beginners", "beginner", "guide", "complete",
         "full", "course", "simple", "simply", "step", "from", "into", "that", "this", "best",
         "2024", "2025", "2026", "part", "basics", "introduction", "learn", "real", "method",
         "install", "use", "using", "working", "principle", "actually", "really", "explain",
         "what", "does", "about", "inside", "behind", "secret", "secrets", "truth", "ever",
         "minutes", "need", "know", "everything", "made", "easy", "free", "today", "new"}


def _key(s: str) -> set[str]:
    return _words(s) - _STOP


def already_made(pick: dict | str) -> str | None:
    """The existing topic/video this pick repeats, or None. Checked in code, not left to the AI.
    Same topic = at least 2 key words shared AND more than half of the key words of EACH title
    match (so "Aircrack-ng on Kali" is new next to "Install Kali on Windows 11", but
    "Full Wave Bridge Rectifier Working" repeats "How a Full Wave Bridge Rectifier Works")."""
    text = pick if isinstance(pick, str) else f'{pick.get("topic", "")} {pick.get("search_phrase", "")}'
    new = _key(text)
    if not new:
        return None
    for old in _made_before() + channel_videos()["titles"]:
        o = _key(old)
        overlap = len(new & o)
        if overlap >= 2 and overlap * 2 > len(new) and overlap * 2 > len(o):
            return old
    return None


def _low_demand() -> list[str]:
    return json.loads(LOW_DEMAND_FILE.read_text()) if LOW_DEMAND_FILE.exists() else []


def pick_topic() -> dict:
    """Pick a topic with proven big search demand. Topics whose top YouTube results have a
    median below MIN_SEARCH_VIEWS (default 50,000) are skipped and never suggested again."""
    need = int(os.getenv("MIN_SEARCH_VIEWS") or 50000)
    # Too big is also bad: when the top results all have millions of views, giant channels
    # own that search and a small channel never shows up (python tutorial: 8M -> we got 4 views).
    cap = int(os.getenv("MAX_SEARCH_VIEWS") or 1000000)
    rejected: list[str] = []
    for attempt in range(6):
        r = _pick_once(rejected + _low_demand()[-60:], attempt)
        dup = already_made(r)
        if dup:
            log.info("Skipping '%s': the channel already has '%s'", r.get("topic"), dup)
            rejected.append(r.get("search_phrase") or r.get("topic", ""))
            continue
        demand = search_demand(r.get("search_phrase") or r.get("topic", ""))
        if demand is None:  # can't measure (no key / quota): don't block the channel
            log.warning("Search demand unknown - using the pick")
            return r
        log.info("Search demand for '%s': median %s views of the top 10 results (want %s-%s)",
                 r.get("search_phrase"), f"{demand:,}", f"{need:,}", f"{cap:,}")
        if need <= demand <= cap:
            r["search_demand"] = demand
            return r
        rejected.append(r.get("search_phrase") or r.get("topic", ""))
        LOW_DEMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOW_DEMAND_FILE.write_text(json.dumps(_low_demand() + rejected[-1:], indent=1))
    raise RuntimeError(f"No new topic with enough search demand found this run (tried: {'; '.join(rejected)}) - "
                       "trying again next hour")


_TRENDS: list = []


def trending_today() -> list[str]:
    """Today's Google Trends (US + India) - only for channels whose domain asks for it."""
    if _TRENDS or not _domain().get("trends"):
        return _TRENDS
    try:
        from pipeline.trends import google_trends
        for c in ("US", "IN"):
            _TRENDS.extend(t.name for t in google_trends(c)[:15])
    except Exception as exc:
        log.warning("Could not read Google Trends: %s", exc)
    return _TRENDS


def _pick_once(avoid: list[str], attempt: int = 0) -> dict:
    cands = [c for c in candidates() if c[0] not in avoid and not already_made(c[0])]
    d = _domain()
    listing = "\n".join(f"- {p} (score {s:.0f})" for p, s in cands) or (
        "- (live data unavailable: use your knowledge of the most-searched YouTube topics in this field)")
    r = llm.chat_json(f"""Our channel covers {d["about"]}. Goal: grow fast and reach YouTube
monetization (watch hours). These are phrases people are typing into YouTube search right
now, with a popularity score:
{listing}

Already made (do not repeat, not even reworded): {"; ".join(_made_before()[-80:]) or "none"}
Rejected (too few searches, too crowded, or already made) - pick a DIFFERENT subject, not a reworded version of any of these: {"; ".join(avoid) or "none"}
Already on the channel: {"; ".join(t[:60] for t in channel_videos()["titles"][:120]) or "none"}

{("TRENDING TODAY (Google Trends): " + "; ".join(trending_today()) + chr(10) + "If one of these has a fascinating, accurate, evergreen explainer angle in our field (e.g. a trending eclipse -> how solar eclipses work), prefer it - it rides today's interest. Skip celebrity gossip, sports scores and politics." + chr(10)) if trending_today() else ""}
OUR MOST-VIEWED VIDEOS (a hint about who watches us and which title style works - NOT a
limit on topics):
{chr(10).join(f"- {t} ({n} views)" for n, t in channel_videos()["winners"]) or "- none yet"}
Choose mainly by SEARCH DEMAND: the topic millions of people are actively searching for
right now in our field (highest score above, plus your own knowledge of the biggest evergreen
YouTube searches in this field). Prefer searches with huge demand where a clear, complete,
well-animated answer can win - tutorials, "what is X", "how X works", courses, roadmaps,
installs, exam topics. Use our most-viewed videos only to break ties.

The video MUST be about {d["about"]} - nothing outside this field (no history, no general
science, no entertainment).

Pick the ONE best next video: strong search demand that a small channel can still win -
a specific, clearly-worded search (e.g. "full wave bridge rectifier working", "nmap scan
types", "python list comprehension") rather than a huge generic one ("python tutorial")
that giant channels own. Beginner-friendly but with
depth, evergreen enough to get views for months, and something a 8-10 minute animated
explainer can cover really well. {d["safety"]}

Return JSON: {{"topic": "<the video topic in plain words>", "search_phrase": "<the exact
search phrase it targets>", "angle": "<the hook/angle that makes people click and stay>"}}""",
                      SYSTEM, temperature=min(1.0, 0.5 + 0.12 * attempt), max_tokens=600, prefer=llm.WRITER_MODEL)
    log.info("Search-led topic: %s (targets '%s')", r.get("topic"), r.get("search_phrase"))
    return r


def write_script(pick: dict) -> dict:
    d = _domain()
    howto = ("""
THIS IS A HOW-TO / TUTORIAL SEARCH. The viewer wants to actually do it, so at least 70% of
the narration must be the real steps:
- What you need first (requirements, versions, hardware).
- Numbered steps in exact order: "Step 1: ...". For each step give the exact command (spoken
  clearly, e.g. "type: wsl --install"), the exact menu path or button, and what you should
  see when it worked.
- How to check it worked at the end, and fixes for the 2-3 most common errors.
- No long history or theory - one short line of context at most.
""" if is_tutorial(pick) else "")
    def draft() -> dict:
        return llm.chat_json(f"""Write the narration for a YouTube video.{howto}{viewer_lessons()}
    Topic: {pick["topic"]}
    People search: "{pick["search_phrase"]}"
    Angle: {pick.get("angle", "")}

    Spoken narration only, 1100-1300 words (about 9 minutes):
    1. Hook (first 15 seconds): answer why this matters right now, with a surprising fact or a
       question, and promise exactly what the viewer gets by the end.
    2. Deliver exactly what the searcher wants, step by step, in depth, with correct details,
       real examples and an everyday analogy for the hard part.
    3. Keep tension: every 60-90 seconds tease the next part ("but here's the part most people
       get wrong...").
    4. Common mistakes / myths, and pro tips.
    5. Short recap, then one line inviting viewers to subscribe for the next video.

    Rules: 100% accurate; if unsure, leave it out. Whenever you describe a circuit or setup,
say exactly how each part is connected (which way a diode or capacitor faces, which pin goes
where, which way the current flows), because the animation is drawn from your words. Simple, confident English for viewers in
    India and the US. {d["safety"]} No brand promotion, no scene directions, no [brackets], no
    emojis.

    Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}""",
                               SYSTEM, temperature=0.5, max_tokens=6000, prefer=llm.WRITER_MODEL)

    result = {}
    for _ in range(3):  # an empty or off-topic answer is thrown away and written again
        result = draft()
        if len(result.get("script", "").split()) >= 300 and on_topic(pick, result["script"]):
            break
        log.warning("Draft unusable (%d words, on topic: %s) - writing it again",
                    len(result.get("script", "").split()), on_topic(pick, result.get("script", "")))
    else:
        raise RuntimeError(f"Could not get a usable script about '{pick['topic']}'")
    for _ in range(2):  # too short: expand it instead of giving up
        words = len(result.get("script", "").split())
        if words >= 900:
            break
        log.info("Script has %d words - expanding", words)
        longer = llm.chat_json(f"""This narration is about: {pick["topic"]} (people search
"{pick["search_phrase"]}"). Stay on exactly this topic.
Expand it to 1100-1300 words: more depth, more
real examples, more step-by-step detail and teasers. Keep the hook, structure and accuracy.

{result.get("script", "")}

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}""",
                               SYSTEM, temperature=0.5, max_tokens=6000, prefer=llm.WRITER_MODEL)
        if len(longer.get("script", "").split()) > words and on_topic(pick, longer["script"]):
            result = longer
    if len(result.get("script", "").split()) < 500:
        raise RuntimeError("Script too short")
    if not on_topic(pick, result["script"]):
        raise RuntimeError(f"Script is not about '{pick['topic']}' - not making this video")
    # Two independent expert reviews: the second one checks the corrected script again.
    for review in (1, 2):
        try:
            r = llm.chat_json(f"""You are a strict senior professor and practising engineer in
{d["about"]}, reviewing a script before it is published to thousands of students. A viewer
already caught a wrong capacitor orientation in an earlier video - be that careful.
{viewer_lessons()}
Check EVERYTHING: every fact, number, unit, formula, definition, command, code line, step,
and every description of how parts are connected (component orientation and polarity,
diode/capacitor/battery direction, transistor pins, current direction, wiring, signal flow).
Fix anything wrong, misleading or vague, and make every connection explicit and correct.
Also check the script fully delivers what someone searching "{pick.get("search_phrase", "")}"
wants. {"It is a tutorial: every step must be there, numbered, in the right order, with the exact commands / menu paths and a final check - add any missing step." if is_tutorial(pick) else ""}
Keep the length, topic and spoken style. {d["safety"]}

SCRIPT:
{result["script"]}

Return JSON: {{"errors_found": ["<each mistake you fixed>"], "script": "<the corrected script>"}}""",
                              SYSTEM, temperature=0.1, max_tokens=6000, prefer=llm.WRITER_MODEL)
            errors = r.get("errors_found") or []
            for e in errors[:15]:
                log.info("Fact-check %d fix: %s", review, e)
            if len(r.get("script", "").split()) >= 600 and on_topic(pick, r["script"]):
                result["script"] = r["script"]
            if not errors:
                log.info("Fact-check %d: no mistakes found", review)
                break
        except Exception as exc:
            log.warning("Fact-check %d failed, keeping the script: %s", review, exc)
    return result


def viewer_lessons() -> str:
    """Mistakes real viewers caught in our earlier videos (tools/comments.py saves them)."""
    try:
        items = json.loads(Path("state/viewer_feedback.json").read_text())
    except Exception:
        return ""
    rules = list(dict.fromkeys(i["lesson"] for i in items if i.get("lesson")))[-25:]
    if not rules:
        return ""
    return ("\nMISTAKES VIEWERS CAUGHT IN OUR EARLIER VIDEOS - never repeat any of these:\n"
            + "\n".join(f"- {r}" for r in rules) + "\n")


def on_topic(pick: dict, script: str) -> bool:
    """True when the script is really about the picked topic: most of the topic's key words
    appear in it. Stops a wandering AI answer (e.g. a pyramid story) from becoming a video."""
    key = _key(pick.get("topic", "")) | _key(pick.get("search_phrase", ""))
    if not key or not script:
        return bool(script)
    text = _words(script)
    hits = {w for w in key if w in text or (len(w) > 4 and any(t.startswith(w[:5]) for t in text))}
    return len(hits) >= max(1, (len(key) + 1) // 2)


def _made_before() -> list[str]:
    """Everything this channel already covered (search topics + older topic lists)."""
    out = list(used())
    for f in ("state/used_topics.json",):
        try:
            out += json.loads(Path(f).read_text())
        except Exception:
            pass
    return out


def create_script() -> dict:
    pick = pick_topic()
    mark_used(pick["topic"])  # remembered at once, so a failed run never repeats it
    result = write_script(pick)
    try:  # keep the script, so a viewer complaint can be checked against what we wrote
        Path("state/scripts").mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", pick["topic"].lower())[:60].strip("-")
        Path(f"state/scripts/{dt.date.today().isoformat()}-{slug}.txt").write_text(
            f'{pick["topic"]}\nsearch: {pick.get("search_phrase")}\ntutorial: {is_tutorial(pick)}\n\n'
            + result["script"])
    except Exception as exc:
        log.warning("Could not save the script: %s", exc)
    result.update({"topic": pick["topic"], "search_topic": pick["topic"],
                   "search_phrase": pick.get("search_phrase", pick["topic"]),
                   "visual_style": VISUAL_STYLE + (" " + TUTORIAL_STYLE if is_tutorial(pick) else ""),
                   "sources": [], "research": {},
                   "date": dt.date.today().isoformat()})
    return result


PLAYLIST_FILE = Path("state/search_playlists.json")


def _playlists() -> list[str]:
    return json.loads(PLAYLIST_FILE.read_text()) if PLAYLIST_FILE.exists() else []


def make_metadata(script: dict) -> dict:
    meta = _package(script)
    name = (meta.get("playlist") or "").strip()[:60]
    if name:
        if name not in _playlists():
            PLAYLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
            PLAYLIST_FILE.write_text(json.dumps(_playlists() + [name], indent=1))
        meta["playlist"] = name
    else:
        meta.pop("playlist", None)
    return meta


def _package(script: dict) -> dict:
    return llm.chat_json(f"""You are the packaging lead of a professional YouTube channel
about {_domain()["about"]}. Package this video so it ranks in search and gets clicked.

Search phrase it targets: "{script["search_phrase"]}"
SCRIPT:
{script["script"][:6000]}

Write:
- title: 50-90 characters, the search phrase (or its natural form) at the start, then
  " | " and the subject/series, like this channel's most-viewed titles:
  {"; ".join(t for _, t in channel_videos()["winners"][:5]) or "What Is X? | How It Actually Works | Subject"}
  Honest, clear, may end with one fitting emoji. No clickbait that the video doesn't deliver.
  NEVER invent numbers, percentages, salaries or statistics - only use a number that the
  script states.
- cover_text: 2-4 bold words for the thumbnail/title screen.
- short_hook: one gripping sentence (max 12 words) for the vertical Short.
- description: 1) two sentences that naturally contain the search phrase and close
  variations, 2) "In this video:" with 5 lines starting with "- ", 3) one line asking a
  question for viewers to answer in the comments. No links, no hashtags.
- hashtags: 3 relevant hashtags.
- tags: 15 search tags people really type, most important first.
- playlist: a short series name (2-4 words) this video belongs to, so related videos
  autoplay one after another, e.g. "Kali Linux", "Ethical Hacking", "Python", "AI Tools",
  "Arduino Projects", "How Phones Work". Reuse one of these if it fits: {", ".join(_playlists()) or "none yet"}.

Return JSON: {{"title": "...", "cover_text": "...", "short_hook": "...", "description": "...",
"hashtags": ["#..."], "tags": ["..."], "playlist": "..."}}""", temperature=0.5, max_tokens=2000,
                          prefer=llm.WRITER_MODEL)
