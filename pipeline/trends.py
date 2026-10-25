"""Find today's trending topics and collect news facts about them.

Sources (all free):
  - Google Trends daily trending searches RSS (India + US), includes news links
  - YouTube "most popular" chart (India + US), needs YOUTUBE_API_KEY
  - Google News RSS search, for extra facts on the chosen topic
"""

import html
import logging
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)

COUNTRIES = ["IN", "US"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


@dataclass
class NewsItem:
    title: str
    source: str = ""
    url: str = ""
    snippet: str = ""


@dataclass
class Topic:
    name: str
    origin: str               # e.g. "google-trends:IN" or "youtube:US"
    traffic: str = ""
    news: list[NewsItem] = field(default_factory=list)


def _local(tag: str) -> str:
    """Tag name without XML namespace."""
    return tag.rsplit("}", 1)[-1]


def _clean(text: str | None) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def parse_google_trends(xml_text: str, country: str) -> list[Topic]:
    topics = []
    for item in ET.fromstring(xml_text).iter("item"):
        t = Topic(name="", origin=f"google-trends:{country}")
        for child in item:
            name = _local(child.tag)
            if name == "title":
                t.name = _clean(child.text)
            elif name == "approx_traffic":
                t.traffic = _clean(child.text)
            elif name == "news_item":
                fields = {_local(c.tag): _clean(c.text) for c in child}
                t.news.append(NewsItem(
                    title=fields.get("news_item_title", ""),
                    source=fields.get("news_item_source", ""),
                    url=fields.get("news_item_url", ""),
                    snippet=fields.get("news_item_snippet", ""),
                ))
        if t.name:
            topics.append(t)
    return topics


def google_trends(country: str) -> list[Topic]:
    resp = httpx.get(f"https://trends.google.com/trending/rss?geo={country}",
                     headers=UA, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_google_trends(resp.text, country)


def youtube_trending(country: str, limit: int = 25) -> list[Topic]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    resp = httpx.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "chart": "mostPopular",
                "regionCode": country, "maxResults": limit, "key": key},
        timeout=30,
    )
    resp.raise_for_status()
    topics = []
    for v in resp.json().get("items", []):
        views = int(v.get("statistics", {}).get("viewCount", 0))
        # Only the title is used, to understand the topic - never the content.
        topics.append(Topic(name=v["snippet"]["title"], origin=f"youtube:{country}",
                            traffic=f"{views:,} views"))
    return topics


def all_trending() -> list[Topic]:
    """Trending topics from every source. A failing source is skipped, not fatal."""
    topics = []
    for country in COUNTRIES:
        for source in (google_trends, youtube_trending):
            try:
                found = source(country)
                log.info("%s %s: %d topics", source.__name__, country, len(found))
                topics.extend(found)
            except Exception as exc:
                log.warning("%s %s failed: %s", source.__name__, country, exc)
    if not topics:
        raise RuntimeError("No trending topics found from any source")
    return topics


def parse_google_news(xml_text: str, limit: int) -> list[NewsItem]:
    items = []
    for item in ET.fromstring(xml_text).iter("item"):
        source = item.find("source")
        items.append(NewsItem(
            title=_clean(item.findtext("title")),
            source=_clean(source.text if source is not None else ""),
            url=item.findtext("link") or "",
            snippet=_clean(item.findtext("description")),
        ))
        if len(items) >= limit:
            break
    return items


def google_news(query: str, limit: int = 10) -> list[NewsItem]:
    """Latest news headlines for a topic (India + US editions)."""
    results: list[NewsItem] = []
    for hl, gl, ceid in (("en-IN", "IN", "IN:en"), ("en-US", "US", "US:en")):
        url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query + " when:3d")
               + f"&hl={hl}&gl={gl}&ceid={ceid}")
        try:
            resp = httpx.get(url, headers=UA, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            results.extend(parse_google_news(resp.text, limit))
        except Exception as exc:
            log.warning("Google News %s failed: %s", gl, exc)
    seen, unique = set(), []
    for n in results:
        if n.title not in seen:
            seen.add(n.title)
            unique.append(n)
    return unique[:limit]


def article_text(url: str, max_chars: int = 4000) -> str:
    """Best-effort plain text of a news article (paragraphs only)."""
    try:
        resp = httpx.get(url, headers=UA, timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return ""
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", resp.text, flags=re.S | re.I)
    text = "\n".join(p for p in (_clean(x) for x in paragraphs) if len(p) > 60)
    return text[:max_chars]
