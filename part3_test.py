"""Part 3 test: remove the watermark from a video with notebooklmremover.com, then edit it.

Run:  python part3_test.py path/to/video.mp4
"""

import logging
import sys
from pathlib import Path

from pipeline import editor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
src, out = Path(sys.argv[1]), Path("output")
out.mkdir(exist_ok=True)
clean = out / "video_clean.mp4"
if editor.remove_watermark(src, clean, out / "site_screens"):
    print("WEBSITE OK:", editor.video_info(clean))
    editor.edit_video(clean, out / "video_final.mp4", blur_watermark=False)
else:
    print("WEBSITE FAILED - used blur fallback")
    editor.save_watermark_check(src, out / "watermark_check.jpg")
    editor.edit_video(src, out / "video_final.mp4")
print("FINAL:", editor.video_info(out / "video_final.mp4"))
