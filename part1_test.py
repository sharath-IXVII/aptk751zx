"""Part 1 test: does NotebookLM video generation work on this account?

Run:  python part1_test.py
Success = a playable MP4 in output/part1_test.mp4
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from pipeline.notebooklm_video import check_video, make_video

TEST_SCRIPT = """\
Title: How the Internet Travels Under the Ocean

Every time you open a video or send a message to another country, the data most
likely travels through a cable lying on the ocean floor. More than 95 percent of
international internet traffic moves through about 500 undersea fibre-optic cables.

These cables are surprisingly thin - many are about as wide as a garden hose.
Inside are hair-thin glass fibres that carry data as pulses of light at close to
200,000 kilometres per second.

Special ships lay the cables slowly across the seabed, and repeaters every 50 to
100 kilometres boost the light signal so it can cross entire oceans.

Damage happens more often than people think - mostly from ship anchors and fishing
nets. Repair ships pull the broken ends to the surface, splice them, and lower the
cable back down.

So the next time your video loads instantly, remember the quiet cable on the
ocean floor that made it possible.
"""


async def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = Path("output/part1_test.mp4")
    await make_video(TEST_SCRIPT, "Part 1 test - undersea cables", out,
                     language=os.getenv("VIDEO_LANGUAGE", "en"))
    print(f"\nSUCCESS: {out} ({check_video(out):.0f} seconds)")


if __name__ == "__main__":
    asyncio.run(main())
