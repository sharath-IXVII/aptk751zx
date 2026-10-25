"""Full pipeline: trending topic -> script -> NotebookLM video -> edit -> thumbnail ->
YouTube upload. Runs every 6 hours: each run makes one video (NotebookLM needs 5 hours between
videos) and schedules it into the next free publishing slot (1 video one day, 2 the next, up to
4 days ahead - see pipeline/plan.py). A video still being generated is resumed by the next run.

Run:  python run.py            (normal scheduled run)
      python run.py --force    (make a video even if all slots are filled; 5-hour rule still applies)
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

from pipeline import editor, packaging, plan
from pipeline.script_writer import create_script, save_history

log = logging.getLogger("run")

STATE_FILE = Path("state/current.json")
OUT = Path("output")
IST = ZoneInfo("Asia/Kolkata")
NOTEBOOKLM_GAP = dt.timedelta(hours=5)
MAX_ATTEMPTS = 3  # runs that may work on one video before it is dropped


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

    if not state.get("job") and plan.next_slot(state) is None and not force:
        log.info("Every publishing slot for the next days is already filled - nothing to do")
        return
    log.info("Already scheduled: %s", state.get("scheduled", []))

    job = state.get("job")
    if job and job.get("date") != today and not job.get("notebook_id"):
        job = None  # unfinished script from an earlier day - start fresh
    if job:
        job["attempts"] = job.get("attempts", 0) + 1
        if job["attempts"] > MAX_ATTEMPTS:
            log.warning("Video '%s' failed %d times - giving up on it and starting a new one",
                        job["script"].get("title"), MAX_ATTEMPTS)
            state.pop("job", None)
            job = None
        save_state(state)

    # 1. Script (reuse today's if a previous run already wrote it)
    if not job:
        last = state.get("notebooklm_started_at")
        if last and now() - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP:
            log.info("Less than 5 hours since the last NotebookLM video - try again later")
            return
        script = create_script()
        job = {"date": today, "script": script, "meta": packaging.make_metadata(script)}
        state["job"] = job
        save_state(state)
    script = job["script"]
    if not job.get("meta"):
        job["meta"] = packaging.make_metadata(script)
        save_state(state)
    meta = job["meta"]
    (OUT / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))

    raw, final, thumb = OUT / "video_raw.mp4", OUT / "video_final.mp4", OUT / "thumbnail.jpg"
    if job.get("video_id"):  # uploaded by an earlier run that stopped right after
        return finish_job(state, job, job["video_id"], today)
    async with NotebookLMClient.from_storage(allow_headless=True) as client:
        # 2. Start the NotebookLM video (once), remembering ids so a later run can resume
        if not job.get("notebook_id"):
            last = state.get("notebooklm_started_at")
            if last and now() - dt.datetime.fromisoformat(last) < NOTEBOOKLM_GAP:
                log.info("Less than 5 hours since the last NotebookLM video - try again later")
                return
            kinds = ("explainer",) if job.get("retried") else ("cinematic", "explainer")
            job.update(await start_video(client, script["script"], script["title"],
                                         os.getenv("VIDEO_LANGUAGE", "en"), kinds=kinds,
                                         cover_text=meta["cover_text"]))
            state["notebooklm_started_at"] = now().isoformat()
            # Remember every notebook we create so it can be deleted after the upload.
            state.setdefault("notebooks_to_delete", []).append(job["notebook_id"])
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

    # 4. Remove watermark + edit, 5. thumbnail = opening title screen of the video
    clean = OUT / "video_clean.mp4"
    if editor.remove_watermark(raw, clean, OUT / "site_screens"):
        editor.edit_video(clean, final, blur_watermark=False)
    else:
        editor.save_watermark_check(raw, OUT / "watermark_check.jpg")
        editor.edit_video(raw, final)
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    # Thumbnail from the NotebookLM title screen, not from our intro clip.
    body = editor.main_part(final)
    packaging.thumbnail_from_video(body if body.exists() else final, thumb)

    # 6. Upload
    if not os.getenv("YT_REFRESH_TOKEN"):
        log.warning("YouTube secrets not set - skipping upload (files are in the run artifacts)")
        video_id = None
    else:
        from pipeline.youtube_upload import upload
        # Schedule into the next free slot (1 video one day, 2 the next...). If every slot is
        # taken (only with --force), it goes public right away.
        slot = plan.next_slot(state)
        video_id = upload(final, thumb, meta, publish_at=slot)
        if slot:
            plan.book(state, slot)
        job["video_id"] = video_id
        save_state(state)  # saved at once, so a later error can never upload it twice

    finish_job(state, job, video_id, today)

    # 7. Clean up: delete the NotebookLM notebooks this pipeline made (the video is on
    #    YouTube now). Notebooks you created yourself are never touched.
    await cleanup_notebooks(state)


def finish_job(state: dict, job: dict, video_id: str | None, today: str) -> None:
    save_history({"date": today, "topic": job["script"]["topic"], "title": job["meta"]["title"],
                  "youtube_id": video_id})
    state.pop("job", None)
    state["uploaded_date"] = today
    state["uploads"] = {today: state.get("uploads", {}).get(today, 0) + 1}
    save_state(state)
    log.info("Done: %s", job["meta"]["title"])


async def cleanup_notebooks(state: dict) -> None:
    from notebooklm import NotebookLMClient

    ids = state.get("notebooks_to_delete", [])
    if not ids:
        return
    left = []
    try:
        async with NotebookLMClient.from_storage(allow_headless=True) as client:
            for nb_id in ids:
                try:
                    await client.notebooks.delete(nb_id)
                    log.info("Deleted old NotebookLM notebook %s", nb_id)
                except Exception as exc:
                    log.warning("Could not delete notebook %s: %s", nb_id, exc)
                    left.append(nb_id)
    except Exception as exc:
        log.warning("NotebookLM cleanup skipped: %s", exc)
        left = ids
    state["notebooks_to_delete"] = left[-20:]  # retried next time
    save_state(state)


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main(force="--force" in sys.argv))
