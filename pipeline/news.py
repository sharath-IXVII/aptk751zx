"""ENT news mode: explain today's biggest story ("Why did the market crash this morning?").

1. Candidates: Google News top stories (India + world, business, technology, science) and
   Google Trends - all free, no API key.
2. The AI picks the biggest fresh story that needs explaining (never a repeat).
3. Research: headlines from many outlets + the full text of several articles (Bing News RSS links
   go straight to the article, so they can be read).
4. Script: what happened -> why -> what it means for you -> what's next, ONLY from those facts.
   The facts go with the script, so the second AI reviewer checks every claim against them.
"""

import datetime as dt
import logging
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

from pipeline import llm
from pipeline.trends import UA, NewsItem, article_text, google_news, google_trends, parse_google_news

log = logging.getLogger(__name__)
FEEDS = {  # Google News top stories + sections (India and world editions)
    "top-IN": "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en",
    "business-IN": "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en",
    "tech": "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
    "science": "https://news.google.com/rss/headlines/section/topic/SCIENCE?hl=en-US&gl=US&ceid=US:en",
    "world": "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-IN&gl=IN&ceid=IN:en",
}
SYSTEM = ("You run a fast, trusted news-explainer channel. You explain big stories clearly and "
          "accurately for ordinary people, using only verified facts, never rumours.")


def headlines() -> list[str]:
    out = []
    for name, url in FEEDS.items():
        try:
            r = httpx.get(url, headers=UA, timeout=30, follow_redirects=True); r.raise_for_status()
            out += [f"[{name}] {n.title}" for n in parse_google_news(r.text, 25)]
        except Exception as exc:
            log.warning("News feed %s failed: %s", name, exc)
    for c in ("IN", "US"):
        try:
            out += [f"[trending-{c}] {t.name}" + (f" - {t.news[0].title}" if t.news else "") for t in google_trends(c)[:20]]
        except Exception as exc:
            log.warning("Google Trends %s failed: %s", c, exc)
    if len(out) < 10:
        raise RuntimeError("Not enough news headlines found")
    return out


def bing_news(query: str, limit: int = 12) -> list[NewsItem]:
    """Bing News RSS: links go straight to the article (Google's are redirects)."""
    try:
        r = httpx.get("https://www.bing.com/news/search?format=rss&q=" + urllib.parse.quote(query),
                      headers=UA, timeout=30, follow_redirects=True); r.raise_for_status()
        items = []
        for it in ET.fromstring(r.text).iter("item"):
            g = lambda tag: (it.findtext(tag) or "").strip()
            items.append(NewsItem(title=g("title"), source=g("{https://www.bing.com/news/search?format=rss}Source") or "",
                                  url=g("link"), snippet=g("description")))
        return items[:limit]
    except Exception as exc:
        log.warning("Bing News failed: %s", exc)
        return []


def pick_story(used: list[str]) -> dict:
    listing = "\n".join(f"- {h}" for h in headlines()[:140])
    r = llm.chat_json(f"""Today's headlines (India + world) and trending searches, {dt.date.today().isoformat()}:
{listing}

Already covered (never repeat, not even a follow-up unless there is big new news): {"; ".join(used[-40:]) or "none"}

Pick the ONE story that most people are talking about RIGHT NOW and want EXPLAINED: markets,
economy, prices, technology, science, space, big business, major world events, sports milestones,
new laws or rules that affect people. Prefer "why did this happen / what does it mean for me"
stories. Never pick: deaths or tragedies of private people, crime accusations against named
people, partisan election fights, celebrity gossip, sexual content, rumours.

Describe the story ONLY with what the headlines say - never add numbers, years or details from your
own memory (they may be outdated). The search query: 3-6 plain words, no year, no numbers.

Return JSON: {{"story": "<the story in plain words, from the headlines>", "query": "<short news search query>",
"angle": "<the question viewers want answered, e.g. Why did the Sensex fall 1,000 points today?>"}}""",
                      SYSTEM, temperature=0.3, max_tokens=800)
    import re
    r["query"] = re.sub(r"\b(19|20)\d\d\b", "", r.get("query", "")).strip()  # never search an old year
    log.info("News story: %s (search '%s')", r.get("story"), r.get("query"))
    return r


def gather(query: str) -> tuple[str, list[NewsItem]]:
    news = bing_news(query) + google_news(query, limit=10)
    blocks = [f"- {n.title} ({n.source}) {n.snippet}".strip() for n in news[:20]]
    read = 0
    for n in news:
        if read >= 4:
            break
        if n.url and "news.google.com" not in n.url:
            if text := article_text(n.url):
                blocks.append(f"\nARTICLE from {n.source or n.url}:\n{text}"); read += 1
    if len(news) < 5 or read == 0:
        raise RuntimeError(f"Not enough reliable reporting yet for: {query}")
    log.info("News research: %d headlines, %d full articles", len(news), read)
    return "\n".join(blocks), news


def create_script(used: list[str]) -> dict:
    s = pick_story(used)
    facts, news = gather(s["query"])
    r = llm.chat_json(f"""Write the narration for a news-explainer video (about 5-6 minutes, 750-900 words).
Story: {s["story"]}
The question viewers have: {s.get("angle", "")}
Today: {dt.date.today().strftime("%d %B %Y")}

FACTS (from today's reporting - use ONLY these; if a detail is not here, do not say it):
{facts[:14000]}

Structure:
1. Hook (first 10 seconds): the news in one punchy line + the question we'll answer.
2. What happened - clear numbers, dates, who and where (only from the facts).
3. WHY it happened - explain the causes step by step, simply, like a good teacher. Explain any
   jargon (e.g. what an index is, what a rate cut does) for someone who has never heard of it.
4. What it means for ordinary people.
5. What happens next / what to watch, without predictions presented as facts.
6. Ask viewers one question to answer in the comments, then invite them to subscribe.
Rules: neutral and factual; say "according to reports" when only one outlet says it; no
rumours, no invented numbers, no financial advice. Simple English for India and the US.

Return JSON: {{"title": "<working title>", "script": "<narration>"}}""", SYSTEM, temperature=0.4, max_tokens=6000,
                      prefer=llm.WRITER_MODEL)
    if len(r.get("script", "").split()) < 400:
        raise RuntimeError("News script too short")
    r.update({"topic": s["story"], "search_phrase": s["query"], "visual_style": "", "news_angle": s.get("angle", ""),
              "facts": facts[:14000], "date": dt.date.today().isoformat(),
              "sources": [{"title": n.title, "source": n.source, "url": n.url} for n in news[:8] if n.url]})
    return r
