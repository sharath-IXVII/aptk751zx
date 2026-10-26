"""Part 1: turn a script into a NotebookLM video and download it as MP4.

Uses the unofficial notebooklm-py library. Login comes from either:
  - ~/.notebooklm/storage_state.json  (created by `notebooklm login` on your PC)
  - NOTEBOOKLM_AUTH_JSON env var      (same file's contents, used on GitHub Actions)
"""

import logging
import subprocess
from pathlib import Path

from notebooklm import NotebookLMClient
from notebooklm.types import VideoFormat, VideoStyle

log = logging.getLogger(__name__)

# Video generation regularly takes 20-40 minutes.
GENERATION_TIMEOUT = 60 * 60


INSTRUCTIONS = (
    "Follow the provided script closely. Keep its order, facts and tone. "
    "Do not add facts that are not in the script."
)


def instructions_for(cover_text: str, style: str = "") -> str:
    """Ask for an opening title screen (its first frame becomes the YouTube thumbnail) and
    the series' visual style."""
    parts = []
    if cover_text:
        parts.append(f'Open the video with a clean title screen: a simple plain background '
                     f'showing only the words "{cover_text}" in large, bold, centred text, '
                     f'held for about 3 seconds.')
    if style:
        parts.append(style)
    return " ".join(parts + [INSTRUCTIONS])


async def start_video(client, script: str, title: str, language: str = "en",
                      kinds: tuple[str, ...] = ("cinematic",),
                      cover_text: str = "", style: str = "", style_prompt: str = "") -> dict:
    """Create a notebook from the script and start video generation.

    Returns {"notebook_id", "task_id", "kind"} so a later run can resume/download.
    """
    nb = await client.notebooks.create(title[:100])
    log.info("Created notebook %s", nb.id)
    await client.sources.add_text(nb.id, title[:100], script, wait=True)
    log.info("Script added as source")

    starters = {
        "cinematic": lambda: client.artifacts.generate_cinematic_video(
            nb.id, language=language, instructions=instructions_for(cover_text, style)),
        # Explainer videos accept a custom visual style (e.g. stickman animation).
        "explainer": lambda: client.artifacts.generate_video(
            nb.id, language=language, instructions=instructions_for(cover_text, style),
            video_format=VideoFormat.EXPLAINER,
            **({"video_style": VideoStyle.CUSTOM, "style_prompt": style_prompt}
               if style_prompt else {})),
        # Same, with NotebookLM's built-in whiteboard style if the custom style is refused.
        "whiteboard": lambda: client.artifacts.generate_video(
            nb.id, language=language, instructions=instructions_for(cover_text, style),
            video_format=VideoFormat.EXPLAINER, video_style=VideoStyle.WHITEBOARD),
    }
    errors = []
    for kind in kinds:
        try:
            status = await starters[kind]()
            log.info("Started %s video generation (task %s)", kind, status.task_id)
            return {"notebook_id": nb.id, "task_id": status.task_id, "kind": kind}
        except Exception as exc:
            log.warning("Could not start %s video: %s", kind, exc)
            errors.append(str(exc))
    try:  # don't leave an empty notebook behind
        await client.notebooks.delete(nb.id)
    except Exception:
        pass
    raise RuntimeError("NotebookLM refused to start a video (limit reached?): " + " | ".join(errors))


async def finish_video(client, job: dict, out_path: Path) -> Path:
    """Wait for a started video to finish and download it."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Waiting for %s video (can take 30+ minutes)", job["kind"])
    status = await client.artifacts.wait_for_completion(
        job["notebook_id"], job["task_id"], max_interval=30.0, timeout=GENERATION_TIMEOUT)
    if not status.is_complete:
        raise RuntimeError(f"{job['kind']} video ended with status={status.status} "
                           f"error={status.error}")
    await client.artifacts.download_video(job["notebook_id"], str(out_path), job["task_id"])
    check_video(out_path)
    log.info("Downloaded %s video to %s", job["kind"], out_path)
    return out_path


async def make_video(script: str, title: str, out_path: Path, language: str = "en") -> Path:
    """One-shot helper (used by the part tests): make a cinematic video and download it."""
    async with NotebookLMClient.from_storage(allow_headless=True) as client:
        job = await start_video(client, script, title, language)
        return await finish_video(client, job, out_path)


def check_video(path: Path) -> float:
    """Make sure the file is a real, playable video. Returns duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        raise RuntimeError(f"Downloaded file is not a valid video: {result.stderr.strip()}")
    if duration < 10:
        raise RuntimeError(f"Downloaded video is too short ({duration:.1f}s)")
    return duration
