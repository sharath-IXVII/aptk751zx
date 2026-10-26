"""Part 4: YouTube title, description and tags, and the thumbnail.

The thumbnail is NOT generated separately: NotebookLM is asked to open the video with a
clean title screen, and that opening frame is saved as the thumbnail.
"""

import logging
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageStat

from pipeline import llm

log = logging.getLogger(__name__)

SIZE = (1280, 720)


def make_metadata(script: dict) -> dict:
    """Title, description, tags and the title-screen text, based on the research."""
    research = script.get("research", {})
    headlines = "\n".join(f"- {h}" for h in research.get("headlines", [])[:12])
    if script.get("series"):
        from pipeline import series
        meta = series.make_metadata(script)
    else:
        meta = trend_metadata(script, research, headlines)
    return finish_metadata(meta, script)


def trend_metadata(script: dict, research: dict, headlines: str) -> dict:
    return llm.chat_json(f"""You are a YouTube SEO expert for a channel that posts explainer videos
about what is trending on YouTube for viewers in India and the US.

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


def finish_metadata(meta: dict, script: dict) -> dict:
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
    # YouTube rejects titles/descriptions containing < or >.
    meta["description"] = meta["description"].replace("<", "").replace(">", "")
    meta["title"] = (meta.get("title") or script["title"]).replace("<", "").replace(">", "")
    meta["title"] = meta["title"].strip().strip('"')[:100]
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


def _frame(video: Path, at: float, out: Path) -> Image.Image | None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video),
                    "-frames:v", "1", str(out)], check=True)
    if not out.exists():
        return None
    img = Image.open(out).convert("RGB")
    img.load()
    out.unlink()
    return img


def _detail(img: Image.Image) -> float:
    """How much clear detail (text edges) a frame has - fades and blank frames score ~0."""
    small = img.convert("L").resize((320, 180))
    return ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES)).mean[0]


def thumbnail_from_video(video: Path, out: Path) -> Path:
    """Save the best frame of the opening title screen as a 1280x720 JPEG thumbnail.

    Several frames from the first seconds are compared and the sharpest, most detailed one
    (the fully shown title, not a fade-in) is used. Set THUMBNAIL_AT to force a second.
    """
    tmp = out.with_suffix(".png")
    if forced := os.getenv("THUMBNAIL_AT"):
        times = [float(forced)]
    else:
        times = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
    best, best_at, best_score = None, 0.0, -1.0
    for at in times:
        img = _frame(video, at, tmp)
        if img is None:
            continue
        score = _detail(img)
        log.info("Thumbnail candidate at %.1fs: detail %.1f", at, score)
        if score > best_score:
            best, best_at, best_score = img, at, score
    if best is None:
        raise RuntimeError("Could not read any frame from the video for the thumbnail")
    img = best
    scale = max(SIZE[0] / img.width, SIZE[1] / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (img.width - SIZE[0]) // 2, (img.height - SIZE[1]) // 2
    img = img.crop((left, top, left + SIZE[0], top + SIZE[1]))
    # Small boost so it stays crisp and readable at phone size.
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
    out.parent.mkdir(parents=True, exist_ok=True)
    for quality in (92, 80, 65):  # YouTube limit is 2 MB
        img.save(out, "JPEG", quality=quality)
        if out.stat().st_size < 2_000_000:
            break
    log.info("Thumbnail taken from the video at %.1fs -> %s", best_at, out)
    return out
