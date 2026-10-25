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
STUCK_AFTER = 8 * 60  # stop if the page shows no change at all for this long


def remove_watermark(src: Path, dst: Path, shots_dir: Path | None = None) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # CHROMIUM_PATH lets a different local Chromium be used (normally not needed).
        browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle", timeout=90_000)

        downloads, console = [], []
        page.on("download", lambda d: downloads.append(d))  # catches automatic downloads too
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}"))
        page.on("pageerror", lambda e: console.append(f"pageerror: {str(e)[:300]}"))
        visible = """() => [...document.querySelectorAll('button, a, [role=button]')]
            .filter(e => e.offsetParent !== null)
            .map(e => (e.innerText || e.getAttribute('aria-label') || '').trim())
            .filter(t => t)"""
        before_buttons = set(page.evaluate(visible))
        before_pcts = set(re.findall(r"\d{1,3}\s?%", page.inner_text("body")))

        page.set_input_files(FILE_INPUT, str(src))
        log.info("Video selected on %s, waiting for processing", URL)

        notes = []
        start, last_pct, shot, clicked = time.time(), None, 0, set()
        last_change, last_seen = time.time(), None

        def snapshot(name: str) -> None:
            if shots_dir:
                shots_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shots_dir / name), full_page=True)
                (shots_dir / "log.txt").write_text("\n".join(notes))
                (shots_dir / "console.txt").write_text("\n".join(console[-300:]))
                (shots_dir / "page_text.txt").write_text(page.inner_text("body"))

        try:
            while time.time() - start < TIMEOUT:
                if downloads:
                    downloads[0].save_as(str(dst))
                    log.info("Downloaded clean video after %ds", time.time() - start)
                    return dst

                buttons = page.evaluate(visible)
                new_buttons = [b for b in buttons if b not in before_buttons]
                for label in new_buttons:
                    if label in clicked:
                        continue
                    # A start button that appears after choosing the file, or the download button.
                    if re.search(r"download|save|export|start|process|remove|convert|clean",
                                 label, re.I):
                        clicked.add(label)
                        notes.append(f"t={int(time.time() - start)}s clicking '{label}'")
                        log.info("Clicking '%s'", label)
                        page.get_by_text(label, exact=True).first.click()
                        page.wait_for_timeout(3000)
                        break

                body = page.inner_text("body")
                pcts = [p for p in re.findall(r"\d{1,3}\s?%", body) if p not in before_pcts]
                if pcts and pcts[-1] != last_pct:
                    last_pct = pcts[-1]
                    log.info("Watermark removal: %s", last_pct)
                if re.search(r"\b(error|failed|not supported|unsupported|invalid)\b", body, re.I) \
                        and not downloads:
                    notes.append(f"t={int(time.time() - start)}s page mentions an error")

                # Give up early if nothing on the page changes for STUCK_AFTER seconds.
                seen = (tuple(new_buttons), tuple(pcts[-3:]))
                if seen != last_seen:
                    last_seen, last_change = seen, time.time()
                elif time.time() - last_change > STUCK_AFTER:
                    raise TimeoutError(f"No progress on the page for {STUCK_AFTER // 60} minutes")

                if (time.time() - start) // 60 >= shot:  # one screenshot a minute
                    notes.append(f"t={int(time.time() - start)}s new buttons={new_buttons[:15]}")
                    snapshot(f"site_{shot:02d}.png")
                    shot += 1
                page.wait_for_timeout(5000)  # keeps processing browser events
            raise TimeoutError(f"No download after {TIMEOUT // 60} minutes")
        except Exception:
            snapshot("site_error.png")
            raise
        finally:
            browser.close()
