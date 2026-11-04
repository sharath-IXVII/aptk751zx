"""Post each Short to Instagram (Reel) and Facebook (Reel), at the same time its YouTube
episode goes live (2 a day; the rest wait for their day, like on YouTube).

Each platform is used only if its secrets exist; any error is logged and never stops the run.
Instagram and Facebook download the video from a public link, and Instagram's API cannot
schedule, so each Short waits as a GitHub release asset of this (public) repo
(state["reels"] holds the queue). An hourly run posts the Reels that are due and deletes
their releases. Releases don't count towards GitHub Actions storage.

Secrets: META_PAGE_ID, META_PAGE_TOKEN, META_IG_USER_ID
"""

import datetime as dt
import logging
import os
import subprocess
import time
from pathlib import Path

import httpx

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


def _caption(meta: dict, video_id: str | None) -> str:
    hook = meta.get("short_hook") or meta["title"]
    tags = meta.get("description", "").strip().split("\n")[-1]  # the hashtag line
    yt = "Full video on our YouTube channel - link in bio."
    return f"{hook}\n\n{meta['title']}\n\n{yt}\n\n{tags}"[:2100]


class _PublicLink:
    """A temporary public download link for a file (GitHub release asset)."""

    def __init__(self, path: Path):
        self.path, self.tag = path, f"tmp-short-{int(time.time())}"

    def __enter__(self) -> str:
        repo = os.environ["GITHUB_REPOSITORY"]
        subprocess.run(["gh", "release", "create", self.tag, str(self.path), "--repo", repo,
                        "--title", "temporary", "--notes", "temporary upload for Reels",
                        "--prerelease"], check=True, capture_output=True, text=True)
        return f"https://github.com/{repo}/releases/download/{self.tag}/{self.path.name}"

    def __exit__(self, *exc):
        subprocess.run(["gh", "release", "delete", self.tag, "--repo",
                        os.environ["GITHUB_REPOSITORY"], "--yes", "--cleanup-tag"],
                       capture_output=True, text=True)


def _instagram(url: str, caption: str) -> str:
    ig, token = os.environ["META_IG_USER_ID"], os.environ["META_PAGE_TOKEN"]
    r = httpx.post(f"{GRAPH}/{ig}/media", timeout=60, data={
        "media_type": "REELS", "video_url": url, "caption": caption,
        "share_to_feed": "true", "access_token": token})
    r.raise_for_status()
    container = r.json()["id"]
    for _ in range(60):  # Instagram processes the video: up to ~10 minutes
        time.sleep(10)
        s = httpx.get(f"{GRAPH}/{container}", timeout=30,
                      params={"fields": "status_code", "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram could not process the video: {s}")
    r = httpx.post(f"{GRAPH}/{ig}/media_publish", timeout=60,
                   data={"creation_id": container, "access_token": token})
    r.raise_for_status()
    return r.json()["id"]


def _facebook(url: str, caption: str) -> str:
    page, token = os.environ["META_PAGE_ID"], os.environ["META_PAGE_TOKEN"]
    r = httpx.post(f"{GRAPH}/{page}/video_reels", timeout=60,
                   data={"upload_phase": "start", "access_token": token})
    r.raise_for_status()
    start = r.json()
    up = httpx.post(start["upload_url"], timeout=300,
                    headers={"Authorization": f"OAuth {token}", "file_url": url})
    up.raise_for_status()
    r = httpx.post(f"{GRAPH}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": start["video_id"], "video_state": "PUBLISHED",
        "description": caption, "access_token": token})
    r.raise_for_status()
    return start["video_id"]


def _release(path: Path, tag: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    subprocess.run(["gh", "release", "create", tag, str(path), "--repo", repo,
                    "--title", "Reel waiting to be posted", "--notes", "temporary",
                    "--prerelease"], check=True, capture_output=True, text=True)
    return f"https://github.com/{repo}/releases/download/{tag}/{path.name}"


def _delete_release(tag: str) -> None:
    subprocess.run(["gh", "release", "delete", tag, "--repo", os.environ["GITHUB_REPOSITORY"],
                    "--yes", "--cleanup-tag"], capture_output=True, text=True)


def queue_short(state: dict, short: Path, meta: dict, video_id: str | None, slot) -> None:
    """Keep the Short for Instagram/Facebook until its episode's publish time."""
    if not (os.getenv("META_PAGE_TOKEN") and short.exists()):
        return
    try:
        tag = f"reel-{int(time.time())}"
        url = _release(short, tag)
        at = slot.isoformat() if slot else dt.datetime.now(dt.timezone.utc).isoformat()
        state.setdefault("reels", []).append(
            {"tag": tag, "url": url, "caption": _caption(meta, video_id), "at": at})
        log.info("Reel queued for %s", at)
    except Exception as exc:
        log.warning("Reel not queued (could not make a public link): %s", exc)


def publish_due(state: dict) -> None:
    """Post every queued Reel whose time has come (called at the start of every run)."""
    if not os.getenv("META_PAGE_TOKEN"):
        return
    now = dt.datetime.now(dt.timezone.utc)
    left = []
    for reel in state.get("reels", []):
        if dt.datetime.fromisoformat(reel["at"]) > now:
            left.append(reel)
            continue
        for name, fn, needs in (("Instagram", _instagram, "META_IG_USER_ID"),
                                ("Facebook", _facebook, "META_PAGE_ID")):
            if os.getenv(needs):
                try:
                    log.info("%s Reel posted (id %s)", name, fn(reel["url"], reel["caption"]))
                except Exception as exc:
                    body = getattr(getattr(exc, "response", None), "text", "")[:300]
                    log.warning("%s Reel failed: %s %s", name, exc, body)
        _delete_release(reel["tag"])
    state["reels"] = left
