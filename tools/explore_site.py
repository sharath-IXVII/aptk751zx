"""Open the watermark-remover site in a headless browser and save what it looks like,
so the upload/download steps can be automated. Output goes to output/site/."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://notebooklmremover.com/en"
OUT = Path("output/site")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    page.goto(URL, wait_until="networkidle", timeout=60000)
    page.screenshot(path=str(OUT / "page.png"), full_page=True)
    (OUT / "page.html").write_text(page.content())

    elements = page.evaluate("""() => [...document.querySelectorAll(
        'input, button, a, [role=button], form, label, select, textarea')].map(e => ({
        tag: e.tagName, type: e.type || null, id: e.id || null, name: e.name || null,
        cls: (e.className && e.className.toString().slice(0, 80)) || null,
        text: (e.innerText || e.value || '').trim().slice(0, 80),
        href: e.href || null, accept: e.accept || null }))""")
    (OUT / "elements.json").write_text(json.dumps(elements, indent=2))

    links = sorted({e["href"] for e in elements if e.get("href")})
    print("TITLE:", page.title())
    print("FILE INPUTS:", [e for e in elements if e["type"] == "file"])
    print("BUTTONS:", [e["text"] for e in elements if e["tag"] == "BUTTON"][:40])
    print("LINKS:", links[:60])
    browser.close()
