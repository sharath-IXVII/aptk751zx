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


def remove_watermark(src: Path, dst: Path, shots_dir: Path | None = None) -> bool:
    """Try notebooklmremover.com. Returns True if it worked (dst written)."""
    if (os.getenv("WATERMARK_SITE") or "on") == "off":
        return False
    try:
        from pipeline.watermark_site import remove_watermark as site_remove
        site_remove(src, dst, shots_dir)
        before, after = video_info(src), video_info(dst)  # make sure it is a real video
        log.info("Website result: %s (original %s)", after, before)
        if after["fps"] and after["fps"] < before["fps"] * 0.8:
            # Its "speed" mode halves the frame rate - choppy. Blur keeps it smooth.
            raise RuntimeError(f"website lowered the frame rate to {after['fps']} fps")
        return True
    except Exception as exc:
        log.warning("Watermark website failed (%s) - using the blur method instead", exc)
        return False


def _channel_mark(info: dict, inputs: list[str]) -> str:
    """Filter that adds our own channel watermark in the bottom-right corner ([v0] -> [v]).

    Uses assets/logo.png if it exists (transparent PNG works best), otherwise the
    CHANNEL_NAME text (default GetYr_ENT). It sits where the NotebookLM logo was.
    """
    w, h = info["width"], info["height"]
    margin = h // 30
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
    return (f"[v0]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
            f"text='{text}':fontsize={h // 30}:fontcolor=0xA0A0A0@0.85:"
            f"x=w-tw-{margin}:y=h-th-{margin},format=yuv420p[v]")


def edit_video(src: Path, dst: Path, blur_watermark: bool = True) -> Path:
    info = video_info(src)
    inputs = ["-i", str(src)]
    if blur_watermark:
        x, y, w, h = watermark_box(info["width"], info["height"])
        log.info("Hiding watermark box x=%d y=%d w=%d h=%d", x, y, w, h)
        # Blur the watermark area heavily (looks natural on moving footage).
        radius = max(1, min(20, min(w, h) // 4 - 1))  # chroma planes are half size
        vf = (f"[0:v]split[base][wm];[wm]crop={w}:{h}:{x}:{y},"
              f"boxblur=luma_radius={radius}:luma_power=3:chroma_radius={radius}:chroma_power=3[blur];"
              f"[base][blur]overlay={x}:{y}[v0]")
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
