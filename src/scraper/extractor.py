"""Extract clean text from HTML pages."""

import hashlib
import re

from bs4 import BeautifulSoup


# Elements to strip entirely
STRIP_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg"]

# Common boilerplate class/id patterns to remove
BOILERPLATE_PATTERNS = re.compile(
    r"(nav|menu|sidebar|footer|header|cookie|banner|popup|modal|social|share|widget|ad-|advertisement)",
    re.IGNORECASE,
)


def extract_text(html: str, url: str = "") -> dict:
    """Extract clean text and metadata from HTML.

    Returns:
        dict with keys: title, text, source_type
    """
    soup = BeautifulSoup(html, "lxml")

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

    # Remove boilerplate elements
    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove elements with boilerplate class/id names
    to_remove = []
    for tag in soup.find_all(True):
        if not hasattr(tag, "attrs") or tag.attrs is None:
            continue
        cls = tag.attrs.get("class")
        tag_id = tag.attrs.get("id")
        if cls:
            classes = " ".join(cls) if isinstance(cls, list) else str(cls)
            if BOILERPLATE_PATTERNS.search(classes):
                to_remove.append(tag)
                continue
        if tag_id and BOILERPLATE_PATTERNS.search(str(tag_id)):
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()

    # Get main content area if identifiable
    main = soup.find("main") or soup.find("article") or soup.find(role="main")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = ""

    # Fall back to body if main content was too short
    if len(text) < 100:
        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)

    # Collapse runs of blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Determine source type from URL
    source_type = classify_page(url)

    return {
        "title": title[:500] if title else "",
        "text": text,
        "source_type": source_type,
    }


def classify_page(url: str) -> str:
    """Classify a page type based on its URL path."""
    url_lower = url.lower()
    if any(p in url_lower for p in ["/issues", "/policy", "/policies", "/platform", "/priorities"]):
        return "issues_page"
    elif any(p in url_lower for p in ["/blog", "/news", "/updates"]):
        return "blog_post"
    elif any(p in url_lower for p in ["/press", "/media", "/release"]):
        return "press_release"
    elif any(p in url_lower for p in ["/about", "/bio", "/meet"]):
        return "about_page"
    else:
        return "general_page"


def content_hash(text: str) -> str:
    """Generate a SHA-256 hash of content for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
