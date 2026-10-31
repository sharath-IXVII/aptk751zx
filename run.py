"""Full pipeline: trending topic -> script -> NotebookLM video -> edit -> thumbnail ->
YouTube upload. Runs every hour; a new video is started every 6 hours (4 a day) and scheduled
into the next free publishing slot (2 a day, up to 7 days ahead - see pipeline/plan.py). A video still being generated is resumed by the next run.

Run:  python run.py            (normal scheduled run)
      python run.py --force    (make a video even if all slots are filled; 6-hour rule still applies)
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
NOTEBOOKLM_GAP = plan.NOTEBOOKLM_GAP
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
            log.info("Less than 6 hours since the last NotebookLM video - try again later")
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
                log.info("Less than 6 hours since the last NotebookLM video - try again later")
                return
            # Cinematic (animated) videos only - never the explainer format. If NotebookLM is
            # busy or its limit is reached, the next hourly run simply tries again.
            kinds = ("cinematic",)
            try:
                started = await start_video(client, script["script"], script["title"],
                                         os.getenv("VIDEO_LANGUAGE", "en"), kinds=kinds,
                                         cover_text=meta["cover_text"],
                                         style=script.get("visual_style", ""),
                                         style_prompt=script.get("style_prompt", ""))
            except Exception as exc:
                if "limit" in str(exc).lower() or "quota" in str(exc).lower():
                    job["attempts"] = 0  # waiting for NotebookLM is not a failure of this video
                    save_state(state)
                    log.warning("NotebookLM limit reached - trying again next hour")
                raise
            job.update(started)
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
            # The generation failed: start a fresh cinematic video for the same script after
            # the 6-hour gap (MAX_ATTEMPTS still limits how often).
            log.warning("Cinematic video failed - it will be made again after the 6-hour gap")
            job.update({"notebook_id": None, "task_id": None})
            save_state(state)
            raise

        # 3b. NotebookLM's own vertical Short from the same notebook (if today's Shorts limit
        #     is not reached). Any problem -> the Short is cut from the episode instead.
        short_raw = OUT / "short_raw.mp4"
        if shorts_left(state) and (os.getenv("SHORTS_SOURCE") or "notebooklm") == "notebooklm":
            try:
                from pipeline.notebooklm_video import make_short_video
                await make_short_video(client, job["notebook_id"], short_raw,
                                       os.getenv("VIDEO_LANGUAGE", "en"),
                                       meta.get("short_hook", ""))
            except Exception as exc:
                log.warning("NotebookLM Short failed (%s) - will cut the Short from the episode", exc)
                short_raw.unlink(missing_ok=True)

    # 4. Remove watermark + edit, 5. thumbnail = opening title screen of the video
    clean = OUT / "video_clean.mp4"
    # The website step drives a browser with Playwright's sync API, which cannot run inside
    # this asyncio loop - run it in a worker thread.
    if await asyncio.to_thread(editor.remove_watermark, raw, clean, OUT / "site_screens"):
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
        # Schedule into the next free slot (2 a day). If every slot is
        # taken (only with --force), it goes public right away.
        slot = plan.next_slot(state)
        video_id = upload(final, thumb, meta, publish_at=slot)
        if slot:
            plan.book(state, slot)
        job["video_id"] = video_id
        save_state(state)  # saved at once, so a later error can never upload it twice
        await upload_short(state, body if body.exists() else final, short_raw, meta,
                           video_id, slot)

    finish_job(state, job, video_id, today)

    # 7. Clean up: delete the NotebookLM notebooks this pipeline made (the video is on
    #    YouTube now). Notebooks you created yourself are never touched.
    await cleanup_notebooks(state)


def shorts_left(state: dict) -> bool:
    """At most SHORTS_PER_DAY Shorts a day (default 2): 4 episodes + 2 Shorts fit YouTube's
    daily upload quota. YouTube's quota day runs on Pacific time."""
    if (os.getenv("SHORTS") or "on") == "off":
        return False
    from zoneinfo import ZoneInfo
    day = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    return state.get("shorts", {}).get(day, 0) < int(os.getenv("SHORTS_PER_DAY") or 2)


async def upload_short(state: dict, episode: Path, short_raw: Path, meta: dict,
                       video_id: str, slot) -> None:
    """Upload a vertical Short, published together with its episode (it links to it).
    Preferred: NotebookLM's own Short, watermark removed by the website. Otherwise a clip cut
    from the episode. Never stops the run - a Short is a bonus."""
    if not shorts_left(state):
        log.info("Shorts limit for today reached - no Short for this episode")
        return
    from zoneinfo import ZoneInfo
    from pipeline import shorts
    from pipeline.youtube_upload import upload
    short = None
    if short_raw.exists():
        clean = OUT / "short_clean.mp4"
        if await asyncio.to_thread(editor.remove_watermark, short_raw, clean, OUT / "short_screens"):
            short = clean
            log.info("Using NotebookLM's Short (watermark removed)")
        else:
            log.warning("Watermark website failed for the Short - cutting it from the episode")
    try:
        if short is None:
            short = shorts.make_short(episode, OUT / "short.mp4",
                                      meta.get("short_hook") or meta["title"])
        short_id = upload(short, None, {**meta, **shorts.short_metadata(meta, video_id)},
                          publish_at=slot)
        day = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
        state["shorts"] = {day: state.get("shorts", {}).get(day, 0) + 1}
        save_state(state)
        log.info("Short uploaded: https://youtu.be/%s", short_id)
    except Exception as exc:
        log.warning("Short skipped: %s", exc)


def finish_job(state: dict, job: dict, video_id: str | None, today: str) -> None:
    if job["script"].get("genre"):
        from pipeline import stories
        stories.mark_used(job["meta"]["title"], job["script"].get("premise", ""),
                          job["script"]["genre"])
    if job["script"].get("word"):
        from pipeline import series
        series.mark_used(job["script"]["word"])
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
