"""Part 4 test: check the YouTube login and upload one video as PRIVATE.

Run:  python part4_test.py [folder with video_final.mp4, metadata.json, thumbnail.jpg]
Without the files, a short sample video is made and uploaded.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from pipeline import packaging
from pipeline.youtube_upload import _client, upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
os.environ["YT_PRIVACY"] = "private"  # test uploads are never public

me = _client().channels().list(part="snippet,status", mine=True).execute().get("items", [])
if not me:
    sys.exit("LOGIN OK but this Google account has no YouTube channel")
print("LOGIN OK - channel:", me[0]["snippet"]["title"])

src, out = Path(sys.argv[1] if len(sys.argv) > 1 else "/nonexistent"), Path("output")
out.mkdir(exist_ok=True)
video = src / "video_final.mp4"
if video.exists():
    meta = json.loads((src / "metadata.json").read_text(encoding="utf-8"))
    thumb = src / "thumbnail.jpg"
    meta["title"] = ("[TEST] " + meta["title"])[:100]
else:
    video = out / "sample.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "15", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-shortest", str(video)], check=True)
    thumb = packaging.thumbnail_from_video(video, out / "thumbnail.jpg")
    meta = {"title": "[TEST] Upload test - please delete", "description": "Automation test.",
            "tags": ["test"]}
video_id = upload(video, thumb, meta)
print(f"UPLOAD OK: https://youtu.be/{video_id} (private - delete it in YouTube Studio)")
