"""Full daily pipeline: trending topic -> script -> NotebookLM video -> edit -> thumbnail ->
YouTube upload. Safe to run every few hours: it makes at most one video per day (India time),
waits 5 hours between NotebookLM videos, and resumes a video that is still being generated.

Run:  python run.py            (normal scheduled run)
      python run.py --force    (ignore the once-per-day rule; 5-hour rule still applies)
"""

import asyncio
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from pipeline import editor, packaging
from pipeline.script_writer import create_script, save_history

log = logging.getLogger("run")

STATE_FILE = Path("state/current.json")
OUT = Path("output")
IST = ZoneInfo("Asia/Kolkata")
NOTEBOOKLM_GAP = dt.timedelta(hours=5)


def now() -> dt.datetime:
    return dt.datetime.now(IST)


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


async def main(force: bool) -> None:
    from notebooklm import NotebookLMClient
    from pipeline.notebooklm_video import finish_video, start_video

    OUT.mkdir(exist_ok=True)
    state = load_state()
    today = now().date().isoformat()

    if state.get("uploaded_date") == today and not force:
        log.info("Today's video is already uploaded - nothing to do")
        return

    job = state.get("job")
    if job and job.get("date") != today and not job.get("notebook_id"):
        job = None  # unfinished script from an earlier day - start fresh

    # 1. Script (reuse today's if a previous run already wrote it)
    if not job:
        last = state.get("notebooklm_started_at")
        if last and now() - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP:
            log.info("Less than 5 hours since the last NotebookLM video - try again later")
            return
        script = create_script()
        job = {"date": today, "script": script}
        state["job"] = job
        save_state(state)
    script = job["script"]
    (OUT / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))

    raw, final, thumb = OUT / "video_raw.mp4", OUT / "video_final.mp4", OUT / "thumbnail.jpg"
    async with NotebookLMClient.from_storage(allow_headless=True) as client:
        # 2. Start the NotebookLM video (once), remembering ids so a later run can resume
        if not job.get("notebook_id"):
            last = state.get("notebooklm_started_at")
            if last and now() - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP:
                log.info("Less than 5 hours since the last NotebookLM video - try again later")
                return
            kinds = ("explainer",) if job.get("retried") else ("cinematic", "explainer")
            job.update(await start_video(client, script["script"], script["title"],
                                         os.getenv("VIDEO_LANGUAGE", "en"), kinds=kinds))
            state["notebooklm_started_at"] = now().isoformat()
            save_state(state)

        # 3. Wait for it and download
        try:
            await finish_video(client, job, raw)
        except (TimeoutError, asyncio.TimeoutError):
            log.warning("Video still generating - the next run will continue waiting for it")
            raise
        except Exception:
            if job.get("kind") == "cinematic" and not job.get("retried"):
                log.warning("Cinematic video failed - next run will try the explainer style")
                job.update({"notebook_id": None, "task_id": None, "retried": True})
                save_state(state)
            raise

    # 4. Edit, 5. title/description/thumbnail
    editor.save_watermark_check(raw, OUT / "watermark_check.jpg")
    editor.edit_video(raw, final)
    meta = packaging.make_metadata(script)
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    packaging.make_thumbnail(meta, final, thumb)

    # 6. Upload
    if not os.getenv("YT_REFRESH_TOKEN"):
        log.warning("YouTube secrets not set - skipping upload (files are in the run artifacts)")
        video_id = None
    else:
        from pipeline.youtube_upload import upload
        video_id = upload(final, thumb, meta)

    save_history({"date": today, "topic": script["topic"], "title": meta["title"],
                  "youtube_id": video_id})
    state.pop("job", None)
    state["uploaded_date"] = today
    save_state(state)
    log.info("Done: %s", meta["title"])


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main(force="--force" in sys.argv))
