"""robots.txt parser and compliance checker."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


_cache: dict[str, RobotFileParser] = {}


async def can_fetch(url: str, user_agent: str = "*") -> bool:
    """Check if we're allowed to fetch this URL per robots.txt."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    if robots_url not in _cache:
        parser = RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(robots_url, follow_redirects=True)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    # No robots.txt or error — assume allowed
                    parser.allow_all = True
        except (httpx.RequestError, httpx.TimeoutException):
            parser.allow_all = True
        _cache[robots_url] = parser

    parser = _cache[robots_url]
    return parser.can_fetch(user_agent, url)


def clear_cache():
    """Clear the robots.txt cache."""
    _cache.clear()
