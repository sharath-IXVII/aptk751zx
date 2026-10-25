"""Try the full watermark-remover flow with a sample video and record everything:
screenshots every 15 s, visible buttons, console messages, and the downloaded result.
Also saves the site's JavaScript so the processing settings can be inspected.
Output: output/site/flow/"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://notebooklmremover.com/en"
OUT = Path("output/site/flow")
OUT.mkdir(parents=True, exist_ok=True)
sample = Path(sys.argv[1])

log = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: log.append(f"console {m.type}: {m.text[:300]}"))
    scripts = []
    page.on("response", lambda r: scripts.append(r.url) if r.url.endswith(".js") else None)
    page.goto(URL, wait_until="networkidle", timeout=60000)

    page.set_input_files("#video-remover-file-input", str(sample))
    log.append("file selected")

    start, shot = time.time(), 0
    downloaded = None
    while time.time() - start < 15 * 60 and not downloaded:
        page.screenshot(path=str(OUT / f"step_{shot:02d}.png"), full_page=True)
        buttons = page.evaluate("""() => [...document.querySelectorAll('button, a')]
            .filter(e => e.offsetParent !== null)
            .map(e => (e.innerText || '').trim()).filter(t => t)""")
        progress = page.evaluate("""() => [...document.querySelectorAll(
            '[role=progressbar], progress, [class*=progress]')].map(e =>
            (e.getAttribute('aria-valuenow') || e.value || e.innerText || '').toString().slice(0, 60))""")
        log.append(f"t={int(time.time() - start)}s buttons={buttons[:25]} progress={progress}")
        for label in [b for b in buttons if re.search(r"download", b, re.I)]:
            try:
                with page.expect_download(timeout=60000) as dl:
                    page.get_by_text(label, exact=True).first.click()
                target = OUT / ("result_" + dl.value.suggested_filename)
                dl.value.save_as(str(target))
                downloaded = target
                log.append(f"downloaded {target}")
                break
            except Exception as exc:
                log.append(f"download click '{label}' failed: {exc}")
        shot += 1
        time.sleep(15)

    page.screenshot(path=str(OUT / "final.png"), full_page=True)
    (OUT / "final.html").write_text(page.content())

    js_dir = OUT / "js"
    js_dir.mkdir(exist_ok=True)
    for i, url in enumerate(sorted(set(scripts))):
        try:
            body = ctx.request.get(url).text()
            if re.search(r"delogo|drawbox|crop|ffmpeg|-ss|watermark", body):
                (js_dir / f"{i:02d}_{url.rsplit('/', 1)[-1][:60]}").write_text(body)
        except Exception as exc:
            log.append(f"js {url}: {exc}")
    browser.close()

if downloaded:
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration:stream=codec_type,width,height", "-of", "json",
                           str(downloaded)], capture_output=True, text=True).stdout
    log.append(f"result info: {info}")
(OUT / "log.txt").write_text("\n".join(log))
print("\n".join(log[-40:]))
