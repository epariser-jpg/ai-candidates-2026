"""Discover campaign website URLs for candidates."""

import asyncio
import httpx
from src.db.models import Candidate


async def search_campaign_url(candidate: Candidate, client: httpx.AsyncClient) -> str | None:
    """Try to find a candidate's campaign website URL.

    Uses a simple heuristic: search for common campaign URL patterns.
    Falls back to None if we can't find one reliably.
    """
    # Common campaign URL patterns
    name_slug = candidate.name.lower().replace(" ", "").replace(".", "").replace("'", "")
    first = candidate.first_name.lower().replace(".", "").replace("'", "")
    last = candidate.last_name.lower().replace(".", "").replace("'", "")

    # Try common patterns
    patterns = [
        f"https://www.{last}forsenate.com" if candidate.office == "Senate" else None,
        f"https://www.{last}forcongress.com" if candidate.office == "House" else None,
        f"https://www.{last}forgovernor.com" if candidate.office == "Governor" else None,
        f"https://www.{name_slug}.com",
        f"https://www.{first}{last}.com",
        f"https://www.elect{last}.com",
        f"https://www.{last}{candidate.election_year}.com",
    ]

    for url in patterns:
        if url is None:
            continue
        try:
            resp = await client.head(url, follow_redirects=True, timeout=10.0)
            if resp.status_code < 400:
                return str(resp.url)
        except (httpx.RequestError, httpx.TimeoutException):
            continue
        await asyncio.sleep(0.3)

    return None


async def discover_urls(candidates: list[Candidate], max_concurrent: int = 5) -> dict[str, str]:
    """Discover campaign URLs for a list of candidates.

    Returns a dict mapping fec_candidate_id to discovered URL.
    """
    results = {}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _discover_one(candidate: Candidate, client: httpx.AsyncClient):
        async with semaphore:
            url = await search_campaign_url(candidate, client)
            if url and candidate.fec_candidate_id:
                results[candidate.fec_candidate_id] = url

    async with httpx.AsyncClient() as client:
        tasks = [_discover_one(c, client) for c in candidates if not c.campaign_url]
        await asyncio.gather(*tasks)

    return results
