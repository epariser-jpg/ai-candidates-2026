"""Playwright-based scraping for JavaScript-rendered campaign sites."""

import asyncio
from urllib.parse import urljoin, urlparse

from src.config import SCRAPE_PRIORITY_PATHS
from src.scraper.extractor import extract_text, content_hash


async def crawl_site_js(
    base_url: str,
    max_pages: int = 20,
    delay: float = 2.0,
) -> list[dict]:
    """Crawl a JS-rendered site using Playwright.

    Falls back gracefully if Playwright is not installed.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("    Playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc
    visited: set[str] = set()
    results: list[dict] = []

    # Prioritized queue: (url, priority)
    queue: list[tuple[str, int]] = [(base_url, 5)]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        while queue and len(results) < max_pages:
            queue.sort(key=lambda x: x[1])
            url, priority = queue.pop(0)

            url = url.split("#")[0].rstrip("/")
            if url in visited:
                continue
            visited.add(url)

            try:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=15000)

                # Wait a bit for dynamic content
                await page.wait_for_timeout(1500)

                html = await page.content()

                # Use Playwright's inner_text for better JS-rendered extraction
                try:
                    text = await page.inner_text("body")
                except Exception:
                    text = ""

                # Also try BeautifulSoup extraction as fallback
                if len(text) < 50:
                    extracted = extract_text(html, url)
                    text = extracted["text"]

                # Get title
                title = await page.title() or ""

                await page.close()

                if len(text) < 50:
                    continue

                # Clean up whitespace
                import re
                lines = [line.strip() for line in text.splitlines()]
                lines = [line for line in lines if line]
                text = "\n".join(lines)
                text = re.sub(r"\n{3,}", "\n\n", text)

                from src.scraper.extractor import classify_page
                results.append({
                    "url": url,
                    "title": title[:500],
                    "text": text,
                    "source_type": classify_page(url),
                    "content_hash": content_hash(text),
                })

                # Extract links from rendered HTML
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "lxml")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    abs_url = urljoin(url, href)
                    abs_parsed = urlparse(abs_url)

                    if abs_parsed.netloc != base_domain:
                        continue
                    if abs_parsed.scheme not in ("http", "https"):
                        continue
                    if any(abs_url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".zip"]):
                        continue

                    link_priority = 5
                    for pp in SCRAPE_PRIORITY_PATHS:
                        if pp in abs_parsed.path.lower():
                            link_priority = 1
                            break

                    clean = abs_url.split("#")[0].rstrip("/")
                    if clean not in visited:
                        queue.append((clean, link_priority))

            except Exception:
                continue

            await asyncio.sleep(delay)

        await browser.close()

    return results
