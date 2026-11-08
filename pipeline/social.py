"""Post each Short to Instagram (Reel) and Facebook (Reel), at the same time its YouTube
episode goes live (2 a day; the rest wait for their day, like on YouTube).

Each platform is used only if its secrets exist; any error is logged and never stops the run.
Instagram and Facebook download the video from a public link, and Instagram's API cannot
schedule, so each Short waits as a GitHub release asset of this (public) repo
(state["reels"] holds the queue). An hourly run posts the Reels that are due and deletes
their releases. Releases don't count towards GitHub Actions storage.

Instagram (preferred, no Facebook needed - "Instagram API with Instagram Login"):
  IG_USER_ID, IG_ACCESS_TOKEN  (+ optional GH_ADMIN_TOKEN so the robot renews the token itself)
Old Facebook-Page method (still supported): META_PAGE_ID, META_PAGE_TOKEN, META_IG_USER_ID
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
IG_GRAPH = "https://graph.instagram.com/v21.0"


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
    if os.getenv("IG_ACCESS_TOKEN"):  # Instagram Login (no Facebook)
        ig, token, graph = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"], IG_GRAPH
    else:
        ig, token, graph = os.environ["META_IG_USER_ID"], os.environ["META_PAGE_TOKEN"], GRAPH
    r = httpx.post(f"{graph}/{ig}/media", timeout=60, data={
        "media_type": "REELS", "video_url": url, "caption": caption,
        "share_to_feed": "true", "access_token": token})
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram refused the Reel ({r.status_code}): {r.text[:500]}")
    container = r.json()["id"]
    for _ in range(60):  # Instagram processes the video: up to ~10 minutes
        time.sleep(10)
        s = httpx.get(f"{graph}/{container}", timeout=30,
                      params={"fields": "status_code", "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram could not process the video: {s}")
    r = httpx.post(f"{graph}/{ig}/media_publish", timeout=60,
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


def _ig_ready(src: Path) -> Path:
    """Re-encode to exactly what Instagram Reels accepts: H.264 + AAC 48 kHz, 30 fps, 1080x1920."""
    dst = src.with_name("reel_ig.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-crf", "21",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k",
                    "-movflags", "+faststart", "-t", "89", str(dst)], check=True)
    return dst


def _instagram_upload(path: Path, caption: str) -> str:
    """Instagram Login: upload the file straight to Instagram (no public link needed)."""
    ig, token = os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"]
    r = httpx.post(f"{IG_GRAPH}/{ig}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": caption,
        "share_to_feed": "true", "access_token": token})
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram refused the Reel ({r.status_code}): {r.text[:500]}")
    container, uri = r.json()["id"], r.json()["uri"]
    data = path.read_bytes()
    up = httpx.post(uri, timeout=600, content=data, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))})
    if up.status_code >= 400:
        raise RuntimeError(f"Instagram upload failed ({up.status_code}): {up.text[:500]}")
    for _ in range(60):
        time.sleep(10)
        st = httpx.get(f"{IG_GRAPH}/{container}", timeout=30, params={
            "fields": "status_code,status", "access_token": token}).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram could not process the video: {st}")
    r = httpx.post(f"{IG_GRAPH}/{ig}/media_publish", timeout=60,
                   data={"creation_id": container, "access_token": token})
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram publish failed ({r.status_code}): {r.text[:500]}")
    return r.json()["id"]


def queue_short(state: dict, short: Path, meta: dict, video_id: str | None, slot) -> None:
    """Post the Short as a Reel. Instagram Login: direct upload now. Otherwise (old Facebook
    method) keep it as a release asset until posted."""
    if not (_enabled() and short.exists()):
        return
    if os.getenv("IG_ACCESS_TOKEN"):
        renew_ig_token(state)
        ready = short
        try:
            ready = _ig_ready(short)
            log.info("Instagram Reel posted (id %s)", _instagram_upload(ready, _caption(meta, video_id)))
            return
        except Exception as exc:
            log.warning("Instagram direct upload failed: %s - trying the public-link method", exc)
        try:  # backup: Instagram downloads the file from a temporary public link
            with _PublicLink(ready) as url:
                log.info("Instagram Reel posted via link (id %s)", _instagram(url, _caption(meta, video_id)))
        except Exception as exc:
            body = getattr(getattr(exc, "response", None), "text", "")[:500]
            log.warning("Instagram Reel failed: %s %s", exc, body)
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
    if not _enabled():
        return
    renew_ig_token(state)
    now = dt.datetime.now(dt.timezone.utc)
    left = []
    for reel in state.get("reels", []):
        if dt.datetime.fromisoformat(reel["at"]) > now:
            left.append(reel)
            continue
        for name, fn, needs in (("Instagram", _instagram, "IG_USER_ID|META_IG_USER_ID"),
                                ("Facebook", _facebook, "META_PAGE_ID")):
            if any(os.getenv(n) for n in needs.split("|")):
                try:
                    log.info("%s Reel posted (id %s)", name, fn(reel["url"], reel["caption"]))
                except Exception as exc:
                    body = getattr(getattr(exc, "response", None), "text", "")[:300]
                    log.warning("%s Reel failed: %s %s", name, exc, body)
        _delete_release(reel["tag"])
    state["reels"] = left


def _enabled() -> bool:
    return bool(os.getenv("IG_ACCESS_TOKEN") or os.getenv("META_PAGE_TOKEN"))


def renew_ig_token(state: dict) -> None:
    """Instagram Login tokens last 60 days. Every ~30 days, get a fresh one and save it as the
    IG_ACCESS_TOKEN secret (needs GH_ADMIN_TOKEN: a fine-grained token for this repo with
    "Secrets: read and write"). Without GH_ADMIN_TOKEN, renew it by hand every ~50 days."""
    token, admin = os.getenv("IG_ACCESS_TOKEN"), os.getenv("GH_ADMIN_TOKEN")
    if not (token and admin):
        return
    last = state.get("ig_token_renewed")
    if last and dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last) < dt.timedelta(days=30):
        return
    try:
        r = httpx.get("https://graph.instagram.com/refresh_access_token", timeout=30,
                      params={"grant_type": "ig_refresh_token", "access_token": token})
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
        new = r.json()["access_token"]
        from base64 import b64encode
        from nacl import encoding, public
        repo = os.environ["GITHUB_REPOSITORY"]
        h = {"Authorization": f"Bearer {admin}", "Accept": "application/vnd.github+json"}
        key = httpx.get(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                        headers=h, timeout=30).json()
        box = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder()))
        enc = b64encode(box.encrypt(new.encode())).decode()
        httpx.put(f"https://api.github.com/repos/{repo}/actions/secrets/IG_ACCESS_TOKEN",
                  headers=h, timeout=30,
                  json={"encrypted_value": enc, "key_id": key["key_id"]}).raise_for_status()
        os.environ["IG_ACCESS_TOKEN"] = new
        state["ig_token_renewed"] = dt.datetime.now(dt.timezone.utc).isoformat()
        log.info("Instagram token renewed for another 60 days")
    except Exception as exc:
        log.warning("Could not renew the Instagram token: %s", exc)
