"""Part 1: turn a script into a NotebookLM video and download it as MP4.

Uses the unofficial notebooklm-py library. Login comes from either:
  - ~/.notebooklm/storage_state.json  (created by `notebooklm login` on your PC)
  - NOTEBOOKLM_AUTH_JSON env var      (same file's contents, used on GitHub Actions)
"""

import logging
import subprocess
from pathlib import Path

from notebooklm import NotebookLMClient
from notebooklm.types import VideoFormat

log = logging.getLogger(__name__)

# Video generation regularly takes 20-40 minutes.
GENERATION_TIMEOUT = 60 * 60


async def make_video(script: str, title: str, out_path: Path, language: str = "en") -> Path:
    """Create a notebook from the script, generate a cinematic video, download it.

    Falls back to the normal "explainer" video if cinematic generation fails.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async with NotebookLMClient.from_storage(allow_headless=True) as client:
        nb = await client.notebooks.create(title[:100])
        log.info("Created notebook %s", nb.id)

        await client.sources.add_text(nb.id, title[:100], script, wait=True)
        log.info("Script added as source")

        instructions = (
            "Follow the provided script closely. Keep its order, facts and tone. "
            "Do not add facts that are not in the script."
        )

        attempts = [
            ("cinematic", lambda: client.artifacts.generate_cinematic_video(
                nb.id, language=language, instructions=instructions)),
            ("explainer", lambda: client.artifacts.generate_video(
                nb.id, language=language, instructions=instructions,
                video_format=VideoFormat.EXPLAINER)),
        ]

        for name, start in attempts:
            log.info("Starting %s video generation (can take 30+ minutes)", name)
            try:
                status = await start()
                status = await client.artifacts.wait_for_completion(
                    nb.id, status.task_id, max_interval=30.0, timeout=GENERATION_TIMEOUT)
            except Exception as exc:
                log.warning("%s video failed: %s", name, exc)
                continue
            if not status.is_complete:
                log.warning("%s video ended with status=%s error=%s",
                            name, status.status, status.error)
                continue

            await client.artifacts.download_video(nb.id, str(out_path), status.task_id)
            check_video(out_path)
            log.info("Downloaded %s video to %s", name, out_path)
            return out_path

    raise RuntimeError("NotebookLM could not generate a video (cinematic and explainer both failed)")


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
