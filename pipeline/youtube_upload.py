"""Part 5: upload the video + thumbnail to YouTube (official YouTube Data API v3).

Needs three GitHub secrets, created once with tools/get_youtube_token.py:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Privacy comes from YT_PRIVACY (private / unlisted / public, default private).
Public videos go live as soon as they are uploaded. Optionally set YT_PUBLISH_TIME (India
time, e.g. 18:00) to upload as private and schedule them for that time instead; if that time
has already passed today, the video goes public straight away.
"""

import datetime as dt
import logging
import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def _client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def publish_time(now: dt.datetime | None = None) -> dt.datetime | None:
    """Today's publish slot (India time), or None (publish now) if no YT_PUBLISH_TIME is set or
    it is less than 15 minutes away/past."""
    if not os.getenv("YT_PUBLISH_TIME"):
        return None
    now = now or dt.datetime.now(IST)
    hour, minute = (int(v) for v in os.environ["YT_PUBLISH_TIME"].split(":"))
    slot = now.astimezone(IST).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot if slot - now > dt.timedelta(minutes=15) else None


def upload(video: Path, thumbnail: Path | None, meta: dict) -> str:
    """Upload and return the YouTube video id."""
    youtube = _client()
    privacy = os.getenv("YT_PRIVACY") or "private"
    publish_at = publish_time() if privacy == "public" else None
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": os.getenv("YT_CATEGORY") or "24",  # 24 = Entertainment, 28 = Science & Tech
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            # Scheduled videos must be uploaded as private; YouTube makes them public at publishAt.
            "privacyStatus": "private" if publish_at else privacy,
            **({"publishAt": publish_at.astimezone(dt.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")} if publish_at else {}),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # YouTube's AI-content disclosure
        },
    }
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024,
                                   resumable=True),
    )
    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info("Upload %d%%", int(status.progress() * 100))
        except HttpError as exc:
            if exc.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    video_id = response["id"]
    when = f"scheduled to go public at {publish_at:%Y-%m-%d %H:%M} IST" if publish_at else privacy
    log.info("Uploaded: https://youtu.be/%s (%s)", video_id, when)

    if thumbnail and thumbnail.exists():
        try:
            youtube.thumbnails().set(videoId=video_id,
                                     media_body=MediaFileUpload(str(thumbnail),
                                                                mimetype="image/jpeg")).execute()
            log.info("Thumbnail set")
        except HttpError as exc:
            # Custom thumbnails need a phone-verified channel.
            log.warning("Could not set thumbnail (is the channel phone-verified?): %s", exc)
    return video_id
