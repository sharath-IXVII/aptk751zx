"""A vertical YouTube Short (9:16, under 60 s) cut from each episode, to bring viewers to it.

It takes the opening of the story (right after the title screen - the cold-open hook), puts it
on a blurred full-screen background, adds the hook text on top and "Full story on the channel"
at the bottom. It is published at the same time as its full episode and links to it.
"""

import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _text(s: str) -> str:
    return s.replace("\\", "").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


def _wrap(s: str, width: int = 22) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return (lines + [cur])[:3]


def make_short(episode: Path, out: Path, hook: str, start: float = 3.5,
               length: float = 55.0) -> Path:
    """episode: the edited episode without intro/outro (editor.main_part)."""
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(episode)], capture_output=True, text=True, check=True).stdout.strip())
    start = min(start, max(0.0, dur - 20))
    length = min(length, dur - start)
    lines = _wrap(hook)
    texts = "".join(
        f",drawtext=fontfile={FONT}:text='{_text(line)}':fontsize=64:fontcolor=white:"
        f"borderw=5:bordercolor=black:x=(w-tw)/2:y={150 + i * 84}"
        for i, line in enumerate(lines))
    footer = _text(os.getenv("SHORTS_FOOTER") or "Full story on the channel")
    graph = (
        f"[0:v]split[a][b];"
        f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"boxblur=20:2,eq=brightness=-0.15[bg];"
        f"[b]scale=-2:1000,crop=min(iw\\,{W}):1000[fg];"  # bigger, centre of the scene
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2{texts},"
        f"drawtext=fontfile={FONT}:text='{footer}':fontsize=48:fontcolor=white:"
        f"box=1:boxcolor=black@0.55:boxborderw=18:x=(w-tw)/2:y=h-250,format=yuv420p[v]"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}",
           "-i", str(episode), "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-800:]}")
    log.info("Short made (%.0fs) -> %s", length, out)
    return out


def short_metadata(meta: dict, episode_id: str | None) -> dict:
    hook = meta.get("short_hook") or meta["title"]
    link = f"Watch the full story: https://youtu.be/{episode_id}\n\n" if episode_id else ""
    title = hook if len(hook) <= 90 else meta["title"]
    return {
        "title": f"{title} #shorts"[:100],
        "description": f"{hook}\n\n{link}{meta['title']}\n\n#shorts #story #plottwist",
        "tags": ["shorts", "story", "animated story", "plot twist"] + meta.get("tags", [])[:8],
    }
