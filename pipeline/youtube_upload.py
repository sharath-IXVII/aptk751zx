"""Part 5: upload the video + thumbnail to YouTube (official YouTube Data API v3).

Needs three GitHub secrets, created once with tools/get_youtube_token.py:
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Privacy comes from YT_PRIVACY (private / unlisted / public, default private).
run.py passes publish_at (the next free slot from pipeline/plan.py): the video is uploaded as
private and scheduled to go public then. Without it, a public video goes live at once.
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


def upload(video: Path, thumbnail: Path | None, meta: dict,
           publish_at: dt.datetime | None = None) -> str:
    """Upload and return the YouTube video id. With publish_at (and YT_PRIVACY public), the
    video is uploaded as private and YouTube makes it public at that time."""
    from pipeline.brandsafe import clean_meta
    meta = clean_meta(meta)  # never use other channels' names in our metadata
    youtube = _client()
    privacy = os.getenv("YT_PRIVACY") or "private"
    if privacy != "public":
        publish_at = None
    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags", []),
            "categoryId": os.getenv("YT_CATEGORY") or "27",  # 27 = Education, 28 = Science & Tech
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            # Scheduled videos must be uploaded as private; YouTube makes them public at publishAt.
            "privacyStatus": "private" if publish_at else privacy,
            **({"publishAt": publish_at.astimezone(dt.timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ")} if publish_at else {}),
            "selfDeclaredMadeForKids": False,
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
    when = f"scheduled to go public at {publish_at.astimezone(IST):%Y-%m-%d %H:%M} IST" if publish_at else privacy
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


def add_to_playlist(video_id: str, title: str) -> None:
    """Add a video to the channel's playlist with this title, creating it if needed.
    Videos are added in upload order, so a course playlist stays in lesson order."""
    youtube = _client()
    playlist_id, page = None, None
    while not playlist_id:
        res = youtube.playlists().list(part="snippet", mine=True, maxResults=50,
                                       pageToken=page).execute()
        playlist_id = next((p["id"] for p in res.get("items", [])
                            if p["snippet"]["title"] == title), None)
        page = res.get("nextPageToken")
        if not page:
            break
    if not playlist_id:
        playlist_id = youtube.playlists().insert(part="snippet,status", body={
            "snippet": {"title": title,
                        "description": f"{title}: watch in order, every video builds on the last."},
            "status": {"privacyStatus": "public"}}).execute()["id"]
        log.info("Created playlist: %s", title)
    import time
    for attempt in range(4):  # YouTube sometimes answers 409 "service unavailable": retry
        try:
            youtube.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(20 * (attempt + 1))
    log.info("Added to playlist: %s", title)
