"""Remove the NotebookLM watermark (and ending screen) with notebooklmremover.com.

The site processes the MP4 inside the browser, so we drive a headless Chromium:
select file -> wait while it shows a percentage -> click Download -> save.
"""

import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

URL = "https://notebooklmremover.com/en"
FILE_INPUT = "#video-remover-file-input"
TIMEOUT = 25 * 60  # the site takes 5-10 minutes; allow extra on slower machines


def remove_watermark(src: Path, dst: Path, shots_dir: Path | None = None) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # CHROMIUM_PATH lets a different local Chromium be used (normally not needed).
        browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle", timeout=90_000)
        page.set_input_files(FILE_INPUT, str(src))
        log.info("Video selected on %s, waiting for processing", URL)

        start, last_pct, shot = time.time(), None, 0
        try:
            while time.time() - start < TIMEOUT:
                button = page.locator("button:visible, a:visible").filter(
                    has_text=re.compile(r"download", re.I)).first
                if button.count():
                    with page.expect_download(timeout=120_000) as dl:
                        button.click()
                    dl.value.save_as(str(dst))
                    log.info("Downloaded clean video after %ds", time.time() - start)
                    return dst
                pct = re.search(r"(\d{1,3})\s?%", page.inner_text("body"))
                if pct and pct.group(1) != last_pct:
                    last_pct = pct.group(1)
                    log.info("Watermark removal: %s%%", last_pct)
                if shots_dir and (time.time() - start) // 60 >= shot:  # one screenshot a minute
                    shots_dir.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shots_dir / f"site_{shot:02d}.png"))
                    shot += 1
                time.sleep(5)
            raise TimeoutError(f"No Download button after {TIMEOUT // 60} minutes")
        except Exception:
            if shots_dir:
                shots_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots_dir / "site_error.png"), full_page=True)
            raise
        finally:
            browser.close()
