"""Part 2: pick today's best trending topic and write an original script about it."""

import datetime as dt
import json
import logging
import re
from pathlib import Path

from pipeline import llm
from pipeline.trends import NewsItem, Topic, all_trending, article_text, google_news

log = logging.getLogger(__name__)

HISTORY_FILE = Path("state/history.json")

# Topics YouTube restricts or demonetizes, or that are risky to get wrong.
BLOCKED_WORDS = [
    "election", "vote", "poll", "candidate", "dies", "dead", "death", "killed", "murder",
    "suicide", "rape", "assault", "shooting", "terror", "vaccine", "cancer", "cure",
    "child", "minor", "porn", "nude", "betting", "casino",
    "affair", "divorce", "rumour", "rumours", "rumor", "rumors", "dating", "breakup",
    "cheating", "scandal", "leaked", "arrested",
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


def _is_safe(name: str) -> bool:
    return not re.search(r"\b(" + "|".join(BLOCKED_WORDS) + r")\b", name, flags=re.I)


def pick_topic(topics: list[Topic]) -> tuple[Topic, str]:
    """Ask the LLM to choose the best topic. Returns (topic, news search query)."""
    used = [h["topic"] for h in load_history()[-60:]]
    candidates = [t for t in topics
                  if _is_safe(t.name) and all(_is_safe(n.title) for n in t.news[:3])][:80]
    listing = "\n".join(
        f"{i}. {t.name} [{t.origin}{', ' + t.traffic if t.traffic else ''}]"
        + (f" - news: {t.news[0].title}" if t.news else "")
        for i, t in enumerate(candidates)
    )
    prompt = f"""Today's trending topics in India and the US:
{listing}

Topics we already made videos about (do NOT repeat these or close variants):
{json.dumps(used, ensure_ascii=False)}

Choose ONE topic for today's explainer video. Prefer:
- big real-world stories people want explained (tech, cyberattacks, science, business,
  space, sports moments, viral events, movies/entertainment news)
- topics interesting to BOTH Indian and US viewers
- topics with enough factual news coverage to explain properly
Avoid: elections/politics campaigns, deaths/tragedies/crime victims, medical claims,
anything involving children, gambling, adult content, plain music video titles, and
celebrity personal-life gossip (affairs, divorces, dating, rumours, feuds) - only
verifiable public news, not claims about someone's private life.

Return JSON: {{"index": <number from the list>, "search_query": "<short Google News query in English>",
"reason": "<one sentence>"}}"""
    choice = llm.chat_json(prompt, SYSTEM, temperature=0.3, max_tokens=800)
    topic = candidates[int(choice["index"])]
    log.info("Picked topic: %s (%s)", topic.name, choice.get("reason", ""))
    return topic, choice.get("search_query") or topic.name


def gather_facts(topic: Topic, query: str) -> tuple[str, list[NewsItem]]:
    """Collect news headlines, snippets and some article text for the topic."""
    news = topic.news + google_news(query)
    blocks = []
    for n in news[:15]:
        blocks.append(f"- {n.title} ({n.source}) {n.snippet}".strip())
    # Full text from a few direct article links (Google News links are redirects).
    direct = [n for n in news if n.url and "news.google.com" not in n.url][:3]
    for n in direct:
        if text := article_text(n.url):
            blocks.append(f"\nARTICLE from {n.source or n.url}:\n{text}")
    if len(blocks) < 3:
        raise RuntimeError(f"Not enough news facts found for: {query}")
    return "\n".join(blocks), news


def write_script(topic_name: str, facts: str) -> dict:
    prompt = f"""Write an original YouTube explainer script about: {topic_name}

Use ONLY the facts in the news material below. If something is unclear or not in the
material, leave it out - never invent names, numbers, dates or quotes.

NEWS MATERIAL:
{facts}

Requirements:
- 450-650 words, spoken narration only (no scene directions, no [brackets], no emojis)
- Strong hook in the first 2 sentences, then: what happened, why it matters,
  how it works / background, what happens next, a short memorable ending
- Simple English that Indian and American viewers both understand
- Completely original wording - do not copy sentences from the material
- Neutral and factual; say "reportedly" for unconfirmed claims

Return JSON: {{"title": "<working title>", "script": "<the full narration>"}}"""
    result = llm.chat_json(prompt, SYSTEM, temperature=0.7, max_tokens=4000)
    words = len(result.get("script", "").split())
    if words < 250:
        raise RuntimeError(f"Script too short ({words} words)")
    log.info("Script written: %s (%d words)", result["title"], words)
    return result


def create_script() -> dict:
    """Full Part 2: trending topics -> pick -> facts -> script."""
    topic, query = pick_topic(all_trending())
    facts, news = gather_facts(topic, query)
    result = write_script(topic.name, facts)
    result["topic"] = topic.name
    result["sources"] = [{"title": n.title, "source": n.source, "url": n.url}
                         for n in news[:8] if n.url]
    result["date"] = dt.date.today().isoformat()
    return result
