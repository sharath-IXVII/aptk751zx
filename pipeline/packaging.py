"""Part 4: YouTube title, description and tags (from the trend research), and the thumbnail.

The thumbnail is NOT generated separately: NotebookLM is asked to open the video with a
clean title screen, and that opening frame is saved as the thumbnail.
"""

import logging
import os
import subprocess
from pathlib import Path

from PIL import Image

from pipeline import llm

log = logging.getLogger(__name__)

SIZE = (1280, 720)


def make_metadata(script: dict) -> dict:
    """Title, description, tags and the title-screen text, based on the research."""
    research = script.get("research", {})
    headlines = "\n".join(f"- {h}" for h in research.get("headlines", [])[:12])
    meta = llm.chat_json(f"""You are a YouTube SEO expert for a channel that posts positive,
uplifting explainer videos for viewers in India and the US.

RESEARCH
- Trending search/topic: {research.get("trend", script.get("topic", ""))}
- Where it is trending: {research.get("origin", "")} {research.get("traffic", "")}
- News search used: {research.get("query", "")}
- Trending YouTube video about it (if any): {research.get("youtube_video", "")[:400]}
- Current news headlines about it:
{headlines}

VIDEO SCRIPT TITLE: {script["title"]}
VIDEO SCRIPT:
{script["script"]}

Write:
- title: the best-performing YouTube title. 45-65 characters. Put the main search keyword
  (the trending term people search for) near the start. Curiosity-driven but 100% honest -
  only what the video actually covers. No emojis, no ALL CAPS sentences, no clickbait lies.
- cover_text: 2-5 words for the opening title screen of the video (also the thumbnail),
  short and punchy, e.g. "INDIA GOES TO SPACE"
- description: 3 parts separated by blank lines:
  1) two hook sentences that contain the main keywords,
  2) a 3-4 sentence summary of what the viewer learns,
  3) "Key points:" followed by 3-5 short lines starting with "- ".
  No links and no hashtags (they are added automatically).
- hashtags: 3 relevant hashtags without spaces, e.g. "#ISRO"
- tags: 15 search tags people would type, most important first

Return JSON: {{"title": "...", "cover_text": "...", "description": "...",
"hashtags": ["#..."], "tags": ["..."]}}""", temperature=0.5, max_tokens=2500,
                         prefer=llm.WRITER_MODEL)

    sources = "\n".join(f"- {s.get('source') or 'Source'}: {s['url']}"
                        for s in script.get("sources", [])[:5] if s.get("url"))
    hashtags = " ".join(h if h.startswith("#") else f"#{h}"
                        for h in meta.get("hashtags", [])[:3]).replace(" #", " #")
    meta["description"] = "\n\n".join(part for part in [
        meta.get("description", "").strip(),
        f"Sources:\n{sources}" if sources else "",
        "This video was made with the help of AI tools (script and visuals).",
        hashtags,
    ] if part)[:4900]
    meta["title"] = meta.get("title", script["title"]).strip().strip('"')[:100]
    meta["cover_text"] = (meta.get("cover_text") or meta["title"]).strip().strip('"').upper()[:60]
    tags, total = [], 0
    for tag in meta.get("tags", []):  # YouTube allows ~500 characters of tags
        tag = str(tag).strip().replace("<", "").replace(">", "").lstrip("#")
        if tag and total + len(tag) + 2 < 480:
            tags.append(tag)
            total += len(tag) + 2
    meta["tags"] = tags
    log.info("YouTube title: %s", meta["title"])
    return meta


def thumbnail_from_video(video: Path, out: Path) -> Path:
    """Save the opening title screen of the video as a 1280x720 JPEG thumbnail."""
    at = os.getenv("THUMBNAIL_AT") or "1.5"  # seconds into the video
    raw = out.with_suffix(".png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", at, "-i", str(video),
                    "-frames:v", "1", str(raw)], check=True)
    img = Image.open(raw).convert("RGB")
    scale = max(SIZE[0] / img.width, SIZE[1] / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - SIZE[0]) // 2, (img.height - SIZE[1]) // 2
    img = img.crop((left, top, left + SIZE[0], top + SIZE[1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    for quality in (92, 80, 65):  # YouTube limit is 2 MB
        img.save(out, "JPEG", quality=quality)
        if out.stat().st_size < 2_000_000:
            break
    raw.unlink(missing_ok=True)
    log.info("Thumbnail taken from the video at %ss -> %s", at, out)
    return out
