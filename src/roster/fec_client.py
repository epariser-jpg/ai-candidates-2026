"""FEC API client for fetching candidate data."""

import asyncio
import httpx
from src.config import FEC_API_KEY, FEC_BASE_URL, FEC_ELECTION_YEAR
from src.db.models import Candidate


# Map FEC office codes to readable names
OFFICE_MAP = {"S": "Senate", "H": "House", "P": "President"}

# Map FEC incumbent challenge codes
INCUMBENT_MAP = {
    "I": "Incumbent",
    "C": "Challenger",
    "O": "Open Seat",
}


async def fetch_candidates(
    office: str = "S",
    election_year: int = FEC_ELECTION_YEAR,
    state: str | None = None,
) -> list[Candidate]:
    """Fetch candidates from the FEC API.

    Args:
        office: "S" for Senate, "H" for House, "P" for President
        election_year: Election year to query
        state: Optional two-letter state filter
    """
    candidates = []
    page = 1
    per_page = 100

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params = {
                "api_key": FEC_API_KEY,
                "election_year": election_year,
                "office": office,
                "per_page": per_page,
                "page": page,
                "sort": "name",
            }
            if state:
                params["state"] = state

            # Retry with backoff on rate limiting
            for attempt in range(7):
                resp = await client.get(f"{FEC_BASE_URL}/candidates/", params=params)
                if resp.status_code == 429:
                    wait = min(5 * (2 ** attempt), 120)
                    print(f"  Rate limited (page {page}), waiting {wait}s... (attempt {attempt+1}/7)")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                print(f"  Failed after 7 retries on page {page}, continuing with what we have")
                break
            data = resp.json()

            results = data.get("results", [])
            if not results:
                break

            for r in results:
                # Extract name parts
                full_name = r.get("name", "")
                # FEC names are typically "LASTNAME, FIRSTNAME"
                parts = full_name.split(", ", 1)
                last_name = parts[0].strip().title() if parts else ""
                first_name = parts[1].strip().title() if len(parts) > 1 else ""
                display_name = f"{first_name} {last_name}".strip()

                candidate = Candidate(
                    fec_candidate_id=r.get("candidate_id"),
                    name=display_name or full_name.title(),
                    first_name=first_name,
                    last_name=last_name,
                    party=r.get("party", ""),
                    party_full=r.get("party_full", ""),
                    office=OFFICE_MAP.get(office, office),
                    state=r.get("state", ""),
                    district=r.get("district") if office == "H" else None,
                    incumbent_status=INCUMBENT_MAP.get(
                        r.get("incumbent_challenge", ""), r.get("incumbent_challenge", "")
                    ),
                    election_year=election_year,
                    roster_source="fec",
                )
                candidates.append(candidate)

            pagination = data.get("pagination", {})
            total_pages = pagination.get("pages", 1)
            if page >= total_pages:
                break
            page += 1

            # Rate limit: DEMO_KEY has low limits
            await asyncio.sleep(2.0)

    return candidates


async def fetch_senate_candidates(
    election_year: int = FEC_ELECTION_YEAR,
) -> list[Candidate]:
    """Fetch all Senate candidates for the given election year."""
    return await fetch_candidates(office="S", election_year=election_year)


async def fetch_house_candidates(
    election_year: int = FEC_ELECTION_YEAR,
    state: str | None = None,
) -> list[Candidate]:
    """Fetch House candidates, optionally filtered by state."""
    return await fetch_candidates(office="H", election_year=election_year, state=state)
