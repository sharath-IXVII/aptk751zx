"""Part 3: clean up the NotebookLM video with ffmpeg.

- Hides the NotebookLM watermark (blur box, position set by WATERMARK_BOX)
- Normalises loudness for YouTube
- Optionally mixes in quiet background music (assets/music.mp3)
- Optionally adds an outro clip (assets/outro.mp4)

WATERMARK_BOX is "x,y,w,h" as fractions of the frame, e.g. "0.84,0.88,0.15,0.10"
(= bottom-right corner). Check output/watermark_check.jpg after a run to see the box.
"""

import json
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

ASSETS = Path("assets")
DEFAULT_BOX = "0.84,0.88,0.15,0.10"  # bottom-right corner


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1500:]}")


def video_info(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {"width": video["width"], "height": video["height"],
            "duration": float(data["format"]["duration"]),
            "has_audio": any(s["codec_type"] == "audio" for s in data["streams"])}


def watermark_box(width: int, height: int) -> tuple[int, int, int, int]:
    """Pixel box (x, y, w, h) for the watermark, kept inside the frame."""
    fx, fy, fw, fh = (float(v) for v in (os.getenv("WATERMARK_BOX") or DEFAULT_BOX).split(","))
    w, h = max(8, int(width * fw)) // 2 * 2, max(8, int(height * fh)) // 2 * 2
    x = min(max(1, int(width * fx)), width - w - 2) // 2 * 2
    y = min(max(1, int(height * fy)), height - h - 2) // 2 * 2
    return x, y, w, h


def save_watermark_check(video: Path, out_jpg: Path) -> None:
    """Save a frame with the watermark box outlined in red, to verify the position."""
    info = video_info(video)
    x, y, w, h = watermark_box(info["width"], info["height"])
    _run(["ffmpeg", "-y", "-v", "error", "-ss", str(min(5, info["duration"] / 2)), "-i", str(video),
          "-frames:v", "1", "-vf", f"drawbox=x={x}:y={y}:w={w}:h={h}:color=red:t=4", str(out_jpg)])


def edit_video(src: Path, dst: Path) -> Path:
    info = video_info(src)
    x, y, w, h = watermark_box(info["width"], info["height"])
    log.info("Hiding watermark box x=%d y=%d w=%d h=%d", x, y, w, h)

    inputs = ["-i", str(src)]
    # Blur the watermark area heavily (looks natural on moving footage).
    vf = (f"[0:v]split[base][wm];[wm]crop={w}:{h}:{x}:{y},boxblur=20:3[blur];"
          f"[base][blur]overlay={x}:{y},format=yuv420p[v]")

    music = ASSETS / "music.mp3"
    if not info["has_audio"]:
        audio = None
    elif music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        audio = ("[1:a]volume=0.08[m];[0:a][m]amix=inputs=2:duration=first:"
                 "dropout_transition=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        log.info("Adding background music")
    else:
        audio = "[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"

    graph = vf + (";" + audio if audio else "")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]"]
    if audio:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    main = dst.with_name(dst.stem + "_main.mp4") if (ASSETS / "outro.mp4").exists() else dst
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
            str(main)]
    _run(cmd)

    if main != dst:
        _append_outro(main, ASSETS / "outro.mp4", dst, info)
    log.info("Edited video saved to %s", dst)
    return dst


def _append_outro(main: Path, outro: Path, dst: Path, info: dict) -> None:
    """Concatenate an outro clip, scaling it to the main video's size."""
    w, h = info["width"], info["height"]
    graph = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
             f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[ov];"
             f"[0:v]fps=30,setsar=1[mv];[1:a]aresample=48000[oa];"
             f"[mv][0:a][ov][oa]concat=n=2:v=1:a=1[v][a]")
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(main), "-i", str(outro),
          "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-movflags", "+faststart", str(dst)])
    log.info("Added outro")
