"""Depth-limited website crawler with link prioritization."""

import asyncio
from urllib.parse import urljoin, urlparse

import httpx

from src.config import SCRAPE_DELAY_SECONDS, SCRAPE_MAX_DEPTH, SCRAPE_PRIORITY_PATHS
from src.scraper.robots import can_fetch
from src.scraper.extractor import extract_text, content_hash


USER_AGENT = "AI-Candidates-2026-Research/1.0 (academic research)"


async def crawl_site(
    base_url: str,
    max_depth: int = SCRAPE_MAX_DEPTH,
    max_pages: int = 20,
    delay: float = SCRAPE_DELAY_SECONDS,
) -> list[dict]:
    """Crawl a campaign website up to max_depth, prioritizing issue/policy pages.

    Returns:
        List of dicts with keys: url, title, text, source_type, content_hash
    """
    if not base_url:
        return []

    # Normalize base URL
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    base_parsed = urlparse(base_url)
    base_domain = base_parsed.netloc

    visited: set[str] = set()
    results: list[dict] = []
    # Queue: (url, depth, priority) — lower priority number = higher priority
    queue: list[tuple[str, int, int]] = [(base_url, 0, 5)]

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        while queue and len(results) < max_pages:
            # Sort by priority (lower = better), then depth
            queue.sort(key=lambda x: (x[2], x[1]))
            url, depth, priority = queue.pop(0)

            # Normalize URL
            url = url.split("#")[0].rstrip("/")
            if url in visited:
                continue
            visited.add(url)

            # Check robots.txt
            if not await can_fetch(url):
                continue

            try:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    continue

                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type:
                    continue

                html = resp.text
                if len(html) < 100:
                    continue

                # Extract text
                extracted = extract_text(html, url)
                text = extracted["text"]

                # Skip very short pages (likely redirects or empty)
                if len(text) < 50:
                    continue

                results.append({
                    "url": str(resp.url),
                    "title": extracted["title"],
                    "text": text,
                    "source_type": extracted["source_type"],
                    "content_hash": content_hash(text),
                })

                # Find links to follow (only if within depth limit)
                if depth < max_depth:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "lxml")
                    for a_tag in soup.find_all("a", href=True):
                        href = a_tag["href"]
                        abs_url = urljoin(url, href)
                        abs_parsed = urlparse(abs_url)

                        # Only follow same-domain links
                        if abs_parsed.netloc != base_domain:
                            continue
                        # Skip non-http
                        if abs_parsed.scheme not in ("http", "https"):
                            continue
                        # Skip file downloads
                        if any(abs_url.lower().endswith(ext) for ext in [".pdf", ".jpg", ".png", ".gif", ".zip", ".doc", ".docx"]):
                            continue

                        # Prioritize issue/policy pages
                        link_priority = 5
                        path_lower = abs_parsed.path.lower()
                        for pp in SCRAPE_PRIORITY_PATHS:
                            if pp in path_lower:
                                link_priority = 1
                                break

                        clean_url = abs_url.split("#")[0].rstrip("/")
                        if clean_url not in visited:
                            queue.append((clean_url, depth + 1, link_priority))

            except (httpx.RequestError, httpx.TimeoutException) as e:
                continue

            # Rate limiting
            await asyncio.sleep(delay)

    # If we got very little content, the site is likely JS-rendered
    total_text = sum(len(r["text"]) for r in results)
    if total_text < 200 and max_pages > 0:
        from src.scraper.playwright_fallback import crawl_site_js
        print(f"    Static scrape yielded {total_text} chars, trying Playwright...")
        js_results = await crawl_site_js(base_url, max_pages=max_pages, delay=delay)
        if js_results:
            return js_results

    return results
