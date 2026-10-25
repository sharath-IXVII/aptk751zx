"""Part 2 test: trending topic -> original script (-> NotebookLM video with --video).

Run:  python part2_test.py            (script only, ~1 min)
      python part2_test.py --video    (script + cinematic video, ~30 min)
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from pipeline.notebooklm_video import check_video, make_video
from pipeline.script_writer import create_script, save_history


async def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = Path("output")
    out.mkdir(exist_ok=True)

    result = create_script()
    (out / "script.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOPIC: {result['topic']}\nTITLE: {result['title']}\n\n{result['script']}\n")

    if "--video" in sys.argv:
        video = out / "video.mp4"
        await make_video(result["script"], result["title"], video,
                         language=os.getenv("VIDEO_LANGUAGE", "en"))
        print(f"SUCCESS: {video} ({check_video(video):.0f} seconds)")
        save_history({"date": result["date"], "topic": result["topic"], "title": result["title"]})


if __name__ == "__main__":
    asyncio.run(main())
