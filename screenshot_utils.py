"""
Screenshot current site (before) and generated redesign (after) using Playwright.
Run once: playwright install chromium
"""
import os
from playwright.sync_api import sync_playwright


def screenshot_url(url: str, path: str, timeout_ms: int = 30000) -> bool:
    """Capture full-page screenshot of a live URL. Returns True on success."""
    if not url or not str(url).strip().startswith("http"):
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            page.screenshot(path=path, full_page=True)
            browser.close()
        return True
    except Exception:
        return False


def screenshot_local_html(html_path: str, output_path: str, timeout_ms: int = 10000) -> bool:
    """Render a local HTML file and screenshot it. html_path must be absolute."""
    if not os.path.isfile(html_path):
        return False
    abs_path = os.path.abspath(html_path)
    file_url = "file://" + abs_path
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(file_url, wait_until="load", timeout=timeout_ms)
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            page.screenshot(path=output_path, full_page=True)
            browser.close()
        return True
    except Exception:
        return False
