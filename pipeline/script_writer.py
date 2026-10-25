"""Part 2: pick today's best trending topic and write an original script about it."""

import datetime as dt
import json
import logging
import re
from pathlib import Path

from pipeline import llm
from pipeline.trends import (NewsItem, Topic, all_trending, article_text, google_news,
                             youtube_search)

log = logging.getLogger(__name__)

HISTORY_FILE = Path("state/history.json")

# Always blocked, from every source: content YouTube restricts/demonetizes or that can
# get the channel struck (also applied to trending YouTube videos).
HARD_BLOCKED_WORDS = [
    "election", "vote", "candidate", "murder", "suicide", "rape", "assault", "shooting",
    "terror", "terrorist", "porn", "nude", "nsfw", "18\\+", "betting", "casino", "gambling",
    "vaccine", "cure", "leaked", "scandal", "riot",
]

# Google Trends searches are mostly news; for those we only take positive stories.
BLOCKED_WORDS = HARD_BLOCKED_WORDS + [
    "election", "vote", "poll", "candidate", "dies", "dead", "death", "killed", "murder",
    "suicide", "rape", "assault", "shooting", "terror", "vaccine", "cancer", "cure",
    "child", "minor", "porn", "nude", "betting", "casino",
    "affair", "divorce", "rumour", "rumours", "rumor", "rumors", "dating", "breakup",
    "cheating", "scandal", "leaked", "arrested", "arrest", "attack", "cyberattack", "hack",
    "hacked", "scam", "fraud", "war", "strike", "crash", "accident", "flood", "earthquake",
    "fire", "injured", "injury", "lawsuit", "sued", "protest", "controversy", "layoffs",
    "fight", "ban", "banned", "police", "court", "jail", "hospital",
]

SYSTEM = (
    "You are the head writer of a popular YouTube explainer channel for a global audience "
    "(mainly India and the US). You write gripping, accurate, original documentary-style scripts."
)


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def save_history(entry: dict) -> None:
    history = load_history() + [entry]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history[-200:], indent=2, ensure_ascii=False), encoding="utf-8")


def _is_safe(name: str, words: list[str] = BLOCKED_WORDS) -> bool:
    return not re.search(r"\b(" + "|".join(words) + r")\b", name, flags=re.I)


def _topic_ok(t: Topic) -> bool:
    # Trending YouTube videos can be anything (memes, stickman animations, gaming, music...),
    # so only the hard blocks apply to them. Google Trends news must be positive.
    words = HARD_BLOCKED_WORDS if t.origin.startswith("youtube") else BLOCKED_WORDS
    return (_is_safe(t.name, words) and _is_safe(t.about[:300], words)
            and all(_is_safe(n.title, words) for n in t.news[:3]))


def pick_topic(topics: list[Topic]) -> tuple[Topic, str]:
    """Ask the LLM to choose the best topic. Returns (topic, search query)."""
    used = [h["topic"] for h in load_history()[-60:]]
    safe = [t for t in topics if _topic_ok(t)]
    # Trending YouTube videos come first; Google Trends is the backup.
    youtube = [t for t in safe if t.origin.startswith("youtube")]
    google = [t for t in safe if not t.origin.startswith("youtube")]
    candidates = (youtube[:60] + google[:20])[:80]
    if not candidates:
        raise RuntimeError("No usable trending topics today")
    listing = "\n".join(
        f"{i}. {t.name} [{t.origin}{', ' + t.traffic if t.traffic else ''}]"
        + (f" - news: {t.news[0].title}" if t.news else "")
        + (f" - about: {t.about[:220]}" if t.about else "")
        for i, t in enumerate(candidates)
    )
    prompt = f"""Today's trending content in India and the US, from two sources:
trending YouTube videos [youtube] and Google Trends searches [google-trends].

{listing}

Topics we already made videos about (do NOT repeat these or close variants):
{json.dumps(used, ensure_ascii=False)}

Choose ONE topic for today's video. PRIORITY: trending YouTube videos. Whatever is going
viral on YouTube right now is what we cover - any genre: viral formats (e.g. stickman
animations), memes, challenges, gaming, music, movie trailers, sports moments, tech,
creators, shows. Pick the one with the strongest trend (most views, several videos on the
same thing, broad appeal in India and the US). Our video explains the TREND - what it is,
where it came from, why everyone is watching it - in our own words; we never copy or
re-upload the other creator's video. Only pick a [google-trends] topic if no YouTube
video is usable.

Never pick: sexual content, hate, graphic violence or tragedy, politics/elections,
gambling, medical claims, private people, or anything that accuses a real person of
wrongdoing.

Return JSON: {{"index": <number from the list>, "search_query": "<short search query in English
describing the trend/story>", "reason": "<one sentence>"}}"""
    choice = llm.chat_json(prompt, SYSTEM, temperature=0.3, max_tokens=800)
    try:
        topic = candidates[int(choice["index"])]
    except (KeyError, TypeError, ValueError, IndexError):
        log.warning("Model returned an invalid topic number (%s) - using the top trend", choice)
        topic = candidates[0]
    log.info("Picked topic: %s [%s] (%s)", topic.name, topic.origin, choice.get("reason", ""))
    return topic, choice.get("search_query") or topic.name


def gather_facts(topic: Topic, query: str) -> tuple[str, list[NewsItem]]:
    """Collect facts for the topic: the trending video(s), news headlines and articles."""
    news = topic.news + google_news(query)
    blocks = []
    if topic.about:
        blocks.append(f"THE TRENDING YOUTUBE VIDEO (context only, do not copy): "
                      f"{topic.name} ({topic.traffic}) - {topic.about}")
        try:
            similar = youtube_search(query)
        except Exception as exc:
            log.warning("YouTube search failed: %s", exc)
            similar = []
        if similar:
            blocks.append("OTHER RECENT VIDEOS ON THE SAME TREND (shows how big it is):")
            blocks += [f"- {v.name} ({v.traffic}) - {v.about[:300]}" for v in similar[:8]]
    for n in news[:15]:
        blocks.append(f"- {n.title} ({n.source}) {n.snippet}".strip())
    # Full text from a few direct article links (Google News links are redirects).
    direct = [n for n in news if n.url and "news.google.com" not in n.url][:3]
    for n in direct:
        if text := article_text(n.url):
            blocks.append(f"\nARTICLE from {n.source or n.url}:\n{text}")
    # YouTube trends (memes, animations...) often have little news coverage; the videos
    # themselves are enough material for those.
    if len(blocks) < (2 if topic.about else 3):
        raise RuntimeError(f"Not enough facts found for: {query}")
    return "\n".join(blocks), news


def write_script(topic_name: str, facts: str) -> dict:
    prompt = f"""Write an original YouTube explainer script about: {topic_name}

Use ONLY the facts in the research material below. If something is unclear or not in the
material, leave it out - never invent names, numbers, dates or quotes.

RESEARCH MATERIAL:
{facts}

Requirements:
- 450-650 words, spoken narration only (no scene directions, no [brackets], no emojis)
- Strong hook in the first 2 sentences, then: what it is / what happened, why it is
  trending and why people love it, the background, what happens next, a short memorable ending
- If it is a viral YouTube trend, explain the trend itself (the format, who started it,
  how big it got) - do not retell another creator's video scene by scene
- Simple English that Indian and American viewers both understand
- Completely original wording - do not copy sentences from the material
- Engaging, upbeat and factual tone that fits the topic; say "reportedly" for unconfirmed claims

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}"""
    result = llm.chat_json(prompt, SYSTEM, temperature=0.7, max_tokens=4000,
                           prefer=llm.WRITER_MODEL)
    words = len(result.get("script", "").split())
    # Smaller models often write short scripts - ask them to expand it.
    for _ in range(2):
        if words >= 400:
            break
        log.info("Script only %d words, asking for a longer version", words)
        longer = llm.chat_json(f"""This YouTube narration script is too short ({words} words).
Rewrite it to 500-600 words. Keep the same facts, title and tone; add more
background, explanation and context from the research material. Do not invent facts.

RESEARCH MATERIAL:
{facts}

CURRENT SCRIPT:
{result.get("script", "")}

Return JSON: {{"title": "<working title>", "script": "<the full longer narration>"}}""",
                               SYSTEM, temperature=0.7, max_tokens=4000,
                               prefer=llm.WRITER_MODEL)
        if len(longer.get("script", "").split()) > words:
            result, words = longer, len(longer["script"].split())
    if words < 250:
        raise RuntimeError(f"Script too short ({words} words)")
    log.info("Script written: %s (%d words)", result["title"], words)
    return fact_check(result, facts)


def fact_check(result: dict, facts: str) -> dict:
    """Remove or correct claims the news material does not support."""
    try:
        checked = llm.chat_json(f"""You are a strict fact-checker for a news video.
Compare the SCRIPT with the NEWS MATERIAL. Find every claim (names, titles/roles,
numbers, dates, results, series standings, descriptions of events) that is NOT clearly
supported by the material. Remove or reword those claims so everything is supported.
Use exact names from the material where the script is vague (e.g. "a young player").
Keep the length, structure, positive tone and spoken style. Do not add new facts.

NEWS MATERIAL:
{facts}

SCRIPT TITLE: {result.get("title", "")}
SCRIPT:
{result.get("script", "")}

Return JSON: {{"title": "<title, corrected if needed>", "script": "<corrected script>",
"changes": ["<short note of each fix>"]}}""", SYSTEM, temperature=0.2, max_tokens=4000,
                                prefer=llm.WRITER_MODEL)
    except Exception as exc:
        log.warning("Fact-check failed, keeping original script: %s", exc)
        return result
    words = len(checked.get("script", "").split())
    if words < 300:
        log.warning("Fact-checked script too short (%d words), keeping original", words)
        return result
    for change in checked.get("changes", []):
        log.info("Fact-check fix: %s", change)
    return {"title": checked.get("title") or result["title"], "script": checked["script"]}


def create_script() -> dict:
    """Full Part 2: trending topics (YouTube first) -> pick -> facts -> script."""
    topic, query = pick_topic(all_trending())
    facts, news = gather_facts(topic, query)
    # Topic names can be vague (e.g. "mlb"); the search query describes the story.
    result = write_script(f"{query} (trending as: {topic.name})", facts)
    result["topic"] = topic.name
    result["sources"] = [{"title": n.title, "source": n.source, "url": n.url}
                         for n in news[:8] if n.url]
    result["research"] = {"trend": topic.name, "origin": topic.origin, "traffic": topic.traffic,
                          "query": query, "headlines": [n.title for n in news[:12]],
                          "youtube_video": topic.about}
    result["date"] = dt.date.today().isoformat()
    return result
