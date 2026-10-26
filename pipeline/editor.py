"""Part 3: clean up the NotebookLM video with ffmpeg.

- Removes the NotebookLM watermark if the website failed (delogo, position set by WATERMARK_BOX)
- Normalises loudness for YouTube
- Optionally mixes in quiet background music (assets/music.mp3)
- Optionally adds an intro clip (assets/intro.mp4) and an outro clip (assets/outro.mp4)

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
DEFAULT_BOX = "0.894,0.963,0.104,0.035"  # NotebookLM's "All Gemini Notebook" text, bottom-right


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-1500:]}")


def video_info(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,avg_frame_rate",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    num, _, den = video.get("avg_frame_rate", "0/1").partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    return {"width": video["width"], "height": video["height"], "fps": round(fps, 2),
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


def remove_watermark(src: Path, dst: Path, shots_dir: Path | None = None,
                     attempts: int = 2) -> bool:
    """Try notebooklmremover.com (twice if needed). Returns True if it worked (dst written)."""
    if (os.getenv("WATERMARK_SITE") or "on") == "off":
        return False
    from pipeline.watermark_site import remove_watermark as site_remove
    for attempt in range(1, attempts + 1):
        try:
            site_remove(src, dst, shots_dir)
            before, after = video_info(src), video_info(dst)  # make sure it is a real video
            log.info("Website result: %s (original %s)", after, before)
            if after["fps"] and after["fps"] < before["fps"] * 0.8:
                # Its "speed" mode halves the frame rate - choppy. Blur keeps it smooth.
                raise RuntimeError(f"website lowered the frame rate to {after['fps']} fps")
            return True
        except Exception as exc:
            log.warning("Watermark website attempt %d/%d failed: %s", attempt, attempts, exc)
    log.warning("Watermark website failed - using the blur method and cutting the ending instead")
    return False


def _channel_mark(info: dict, inputs: list[str]) -> str:
    """Filter that adds our own channel watermark in the bottom-right corner ([v0] -> [v]).

    Uses assets/logo.png if it exists (transparent PNG works best), otherwise the
    CHANNEL_NAME text (default GetYr_ENT). It sits where the NotebookLM logo was.
    """
    w, h = info["width"], info["height"]
    margin = h // 30
    bx, by, bw, bh = watermark_box(w, h)  # NotebookLM's logo spot - our mark covers it
    logo = ASSETS / "logo.png"
    if logo.exists():
        inputs += ["-i", str(logo)]
        idx = inputs.count("-i") - 1
        size = h // 9
        log.info("Adding channel logo watermark")
        return (f"[{idx}:v]scale=-1:{size},format=rgba,colorchannelmixer=aa=0.85[logo];"
                f"[v0][logo]overlay=W-w-{margin}:H-h-{margin},format=yuv420p[v]")
    name = (os.getenv("CHANNEL_NAME") or "GetYr_ENT").strip()
    if not name:
        return "[v0]format=yuv420p[v]"
    log.info("Adding channel name watermark: %s", name)
    text = name.replace("\\", "").replace("'", "").replace(":", "\\:").replace("%", "\\%")
    # Small soft-grey text, the same style as the NotebookLM mark it replaces.
    # Small soft-grey text, the same size and place as the NotebookLM mark it replaces.
    right, bottom = w - (bx + bw), h - (by + bh)
    return (f"[v0]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{text}':fontsize={max(14, bh * 4 // 5)}:fontcolor=0x9A9A9A@0.9:"
            f"shadowcolor=white@0.6:shadowx=1:shadowy=1:"
            f"x=w-tw-{right + 2}:y=h-th-{bottom + 2},format=yuv420p[v]")


def edit_video(src: Path, dst: Path, blur_watermark: bool = True) -> Path:
    """blur_watermark=True is the fallback when the website failed: it also cuts off
    NotebookLM's logo screen at the end (END_TRIM seconds, default 3.1)."""
    info = video_info(src)
    inputs = ["-i", str(src)]
    if blur_watermark:
        trim = float(os.getenv("END_TRIM") or 3.1)
        if info["duration"] > trim + 10:
            inputs = ["-t", f"{info['duration'] - trim:.3f}", "-i", str(src)]
            log.info("Cutting NotebookLM's ending (last %.1fs)", trim)
    if blur_watermark:
        x, y, w, h = watermark_box(info["width"], info["height"])
        log.info("Removing NotebookLM logo box x=%d y=%d w=%d h=%d", x, y, w, h)
        # delogo rebuilds the area from the surrounding pixels (much cleaner than a blur);
        # our own channel name is then drawn on the same spot.
        vf = f"[0:v]delogo=x={x}:y={y}:w={w}:h={h}:show=0[v0]"
    else:
        vf = "[0:v]null[v0]"
    vf += ";" + _channel_mark(info, inputs)

    music = ASSETS / "music.mp3"
    if not info["has_audio"]:
        audio = None
    elif music.exists():
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        audio = (f"[{inputs.count('-i') - 1}:a]volume=0.08[m];[0:a][m]amix=inputs=2:duration=first:"
                 "dropout_transition=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        log.info("Adding background music")
    else:
        audio = "[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"

    graph = vf + (";" + audio if audio else "")
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]"]
    if audio:
        cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    intro, outro = ASSETS / "intro.mp4", ASSETS / "outro.mp4"
    clips = [c for c in (intro, outro) if c.exists()]
    main = main_part(dst) if clips else dst
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart",
            str(main)]
    _run(cmd)

    if main != dst:
        parts = ([intro] if intro.exists() else []) + [main] + ([outro] if outro.exists() else [])
        _join(parts, dst, info)
    log.info("Edited video saved to %s", dst)
    return dst


def main_part(dst: Path) -> Path:
    """The edited video without intro/outro (kept for the thumbnail)."""
    return dst.with_name(dst.stem + "_main.mp4")


def _join(parts: list[Path], dst: Path, info: dict) -> None:
    """Join intro + main + outro, scaling every clip to the main video's size and 30 fps.
    Clips without sound get silence so the audio stays in sync."""
    w, h = info["width"], info["height"]
    inputs, graph, chain = [], [], ""
    for i, part in enumerate(parts):
        inputs += ["-i", str(part)]
        graph.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
                     f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v{i}]")
        part_info = video_info(part)
        if part_info["has_audio"]:
            graph.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
        else:
            graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{part_info['duration']}[a{i}]")
        chain += f"[v{i}][a{i}]"
    graph.append(f"{chain}concat=n={len(parts)}:v=1:a=1[v][a]")
    _run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(graph),
          "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst)])
    log.info("Added %s", " + ".join(p.stem for p in parts))
