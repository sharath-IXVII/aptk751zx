"""Post each Short to Instagram (Reel) and Facebook (Reel) - and later Telegram.

Each platform is used only if its secrets exist; any error is logged and never stops the run.
Instagram and Facebook download the video from a public link, so the Short is put on a
temporary GitHub release of this (public) repo and the release is deleted afterwards.

Secrets: META_PAGE_ID, META_PAGE_TOKEN, META_IG_USER_ID
"""

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


def post_short(short: Path, meta: dict, video_id: str | None) -> None:
    if not (os.getenv("META_PAGE_TOKEN") and short.exists()):
        return
    caption = _caption(meta, video_id)
    try:
        with _PublicLink(short) as url:
            for name, fn, needs in (("Instagram", _instagram, "META_IG_USER_ID"),
                                    ("Facebook", _facebook, "META_PAGE_ID")):
                if not os.getenv(needs):
                    continue
                try:
                    log.info("%s Reel posted (id %s)", name, fn(url, caption))
                except Exception as exc:
                    body = getattr(getattr(exc, "response", None), "text", "")[:300]
                    log.warning("%s Reel failed: %s %s", name, exc, body)
    except Exception as exc:
        log.warning("Reels skipped (could not make a public link): %s", exc)
