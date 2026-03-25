"""Scrape Ballotpedia for candidate campaign website URLs and race data.

Strategy:
1. Fetch the main 2026 Senate elections index page to get links to each state race
2. Fetch each state race page to get candidate names + links to Ballotpedia profiles
3. Fetch each candidate's Ballotpedia profile to extract campaign website URL
"""

import asyncio
import re
from urllib.parse import urljoin, unquote

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.db.init_db import get_connection


BASE_URL = "https://ballotpedia.org"
SENATE_2026_URL = f"{BASE_URL}/United_States_Senate_elections,_2026"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# States with Senate elections in 2026
SENATE_2026_STATES = [
    "Alabama", "Alaska", "Arkansas", "Colorado", "Delaware", "Georgia",
    "Idaho", "Illinois", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Montana", "Nebraska", "New_Hampshire", "New_Jersey", "New_Mexico",
    "North_Carolina", "Oklahoma", "Oregon", "Rhode_Island",
    "South_Carolina", "South_Dakota", "Tennessee", "Texas",
    "Virginia", "West_Virginia", "Wyoming",
]


async def fetch_state_race_candidates(
    client: httpx.AsyncClient,
    state: str,
    delay: float = 2.0,
) -> list[dict]:
    """Fetch candidate info from a state's 2026 Senate race page.

    Parses the structured candidate tables under "Candidates and election results".
    Returns list of dicts with: name, party, ballotpedia_url, state
    """
    url = f"{BASE_URL}/United_States_Senate_election_in_{state},_2026"
    candidates = []

    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            print(f"  Warning: {state} returned {resp.status_code}")
            return candidates

        soup = BeautifulSoup(resp.text, "lxml")

        # Find the "Candidates and election results" section
        target_h2 = None
        for h2 in soup.find_all("h2"):
            if "candidates and election results" in h2.get_text(strip=True).lower():
                target_h2 = h2
                break

        if not target_h2:
            return candidates

        # Parse h4 subsections within this section
        seen_names = set()
        current_party = ""
        sib = target_h2.find_next_sibling()

        while sib and sib.name != "h2":
            # Track which party section we're in via h4 headings
            if sib.name == "h4":
                h4_text = sib.get_text(strip=True).lower()
                if "democrat" in h4_text:
                    current_party = "DEM"
                elif "republican" in h4_text:
                    current_party = "REP"
                elif "libertarian" in h4_text:
                    current_party = "LIB"
                elif "green" in h4_text:
                    current_party = "GRE"
                elif "general election" in h4_text:
                    current_party = ""  # mixed parties in general
                elif "withdrawn" in h4_text or "disqualified" in h4_text:
                    # Skip withdrawn candidates section
                    sib = sib.find_next_sibling()
                    # Skip the ul/div that follows
                    while sib and sib.name not in ["h2", "h4"]:
                        sib = sib.find_next_sibling()
                    continue

            # Look for candidate tables (divs containing votebox tables)
            if sib.name == "div" and sib.find("table"):
                for link in sib.find_all("a", href=True):
                    href = link.get("href", "")
                    text = link.get_text(strip=True)

                    # Must be a Ballotpedia profile link
                    if not (href.startswith("/") or href.startswith(BASE_URL)):
                        continue
                    # Skip meta/category links
                    if any(skip in href for skip in [
                        "United_States_Senate", "election", "primary",
                        "Category:", "File:", "Template:", "Ballotpedia",
                        "Party", "Independent", "Survey", "Ballot_access",
                        "How_do", "Run_for", "campaign_finance",
                    ]):
                        continue
                    # Must look like a person's name
                    if len(text) < 4 or len(text) > 40:
                        continue
                    if " " not in text:
                        continue
                    # Skip if it has numbers (likely not a name)
                    if re.search(r"\d", text):
                        continue

                    if text not in seen_names:
                        seen_names.add(text)
                        full_url = urljoin(BASE_URL, href)

                        # Determine party: use section context, or check
                        # parenthetical next to the name
                        party = current_party
                        # Check parent td/span for party indicator
                        parent = link.find_parent("td")
                        if parent:
                            parent_text = parent.get_text(strip=True)
                            if "(D)" in parent_text:
                                party = "DEM"
                            elif "(R)" in parent_text:
                                party = "REP"
                            elif "(L)" in parent_text:
                                party = "LIB"
                            elif "(G)" in parent_text:
                                party = "GRE"
                            elif "(I)" in parent_text or "Unaffiliated" in parent_text:
                                party = "IND"

                        candidates.append({
                            "name": text,
                            "party": party,
                            "state": state.replace("_", " "),
                            "ballotpedia_url": full_url,
                        })

            sib = sib.find_next_sibling()

    except Exception as e:
        print(f"  Error fetching {state}: {e}")

    await asyncio.sleep(delay)
    return candidates


async def fetch_campaign_url_from_profile(
    client: httpx.AsyncClient,
    profile_url: str,
    delay: float = 2.0,
) -> dict:
    """Fetch a candidate's website URLs from their Ballotpedia profile.

    Returns dict with 'campaign_url' and/or 'official_url'.
    Prefers campaign site; falls back to official .gov site.
    """
    result = {}
    try:
        resp = await client.get(profile_url, follow_redirects=True)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Ballotpedia uses clearly labeled links like:
        #   "Campaign website" → campaign site
        #   "Official website" → .senate.gov / .house.gov
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True).lower()
            href = link.get("href", "")

            if not href.startswith("http") or "ballotpedia" in href:
                continue

            if "campaign website" in text or "campaign site" in text:
                result["campaign_url"] = href
            elif "official website" in text or "official site" in text:
                result["official_url"] = href

            # Stop early if we have both
            if "campaign_url" in result and "official_url" in result:
                break

    except Exception:
        pass

    await asyncio.sleep(delay)
    return result


async def discover_all_senate_urls(
    delay: float = 2.5,
    max_concurrent: int = 2,
) -> dict:
    """Discover campaign URLs for all 2026 Senate candidates via Ballotpedia.

    Returns stats dict. Updates the database directly.
    """
    conn = get_connection()
    stats = {
        "states_scraped": 0,
        "candidates_found": 0,
        "urls_discovered": 0,
        "matched_to_fec": 0,
    }

    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        # Step 1: Fetch candidate lists from each state race page
        print(f"Fetching candidates from {len(SENATE_2026_STATES)} state race pages...")
        all_candidates = []

        for state in tqdm(SENATE_2026_STATES, desc="States"):
            async with semaphore:
                candidates = await fetch_state_race_candidates(client, state, delay=delay)
                all_candidates.extend(candidates)
                stats["states_scraped"] += 1

        stats["candidates_found"] = len(all_candidates)
        print(f"\nFound {len(all_candidates)} candidates across {stats['states_scraped']} states")

        # Step 2: For each candidate, fetch their Ballotpedia profile to get campaign URL
        print(f"\nFetching campaign URLs from candidate profiles...")
        for cand in tqdm(all_candidates, desc="Profiles"):
            async with semaphore:
                urls = await fetch_campaign_url_from_profile(
                    client, cand["ballotpedia_url"], delay=delay
                )

                # Prefer campaign URL, fall back to official URL
                best_url = urls.get("campaign_url") or urls.get("official_url")
                if best_url:
                    cand["campaign_url"] = best_url
                    stats["urls_discovered"] += 1

                    # Try to match to FEC data and update
                    matched = _match_and_update(conn, cand)
                    if matched:
                        stats["matched_to_fec"] += 1

        conn.commit()

    # Summary
    total_with_url = conn.execute(
        "SELECT COUNT(*) as n FROM candidates WHERE campaign_url IS NOT NULL AND office = 'Senate'"
    ).fetchone()["n"]
    total = conn.execute(
        "SELECT COUNT(*) as n FROM candidates WHERE office = 'Senate'"
    ).fetchone()["n"]

    print(f"\nURL Discovery complete:")
    print(f"  States scraped: {stats['states_scraped']}")
    print(f"  Candidates found on Ballotpedia: {stats['candidates_found']}")
    print(f"  Campaign URLs discovered: {stats['urls_discovered']}")
    print(f"  Matched to FEC records: {stats['matched_to_fec']}")
    print(f"  Total Senate candidates with URLs: {total_with_url}/{total}")

    conn.close()
    return stats


def _match_and_update(conn, cand: dict) -> bool:
    """Match a Ballotpedia candidate to FEC data and update the campaign URL.

    Uses fuzzy name matching against the candidates table.
    """
    name = cand["name"]
    state = cand.get("state", "")
    campaign_url = cand.get("campaign_url")

    if not campaign_url:
        return False

    # Convert state name to abbreviation
    state_abbr = _state_to_abbr(state)
    if not state_abbr:
        return False

    # Try exact last name match within state
    parts = name.split()
    if not parts:
        return False

    last_name = parts[-1]

    # Query for candidates with matching last name and state
    rows = conn.execute(
        """SELECT id, name, campaign_url FROM candidates
           WHERE state = ? AND last_name LIKE ? AND office = 'Senate'
           ORDER BY
               CASE WHEN campaign_url IS NULL THEN 0 ELSE 1 END,
               name""",
        (state_abbr, f"%{last_name}%"),
    ).fetchall()

    if not rows:
        # Try first name + last name
        if len(parts) >= 2:
            first_name = parts[0]
            rows = conn.execute(
                """SELECT id, name, campaign_url FROM candidates
                   WHERE state = ? AND first_name LIKE ? AND last_name LIKE ?
                   AND office = 'Senate'""",
                (state_abbr, f"%{first_name}%", f"%{last_name}%"),
            ).fetchall()

    if rows:
        # Update all matching rows that don't have a URL yet
        updated = False
        for row in rows:
            if not row["campaign_url"]:
                conn.execute(
                    "UPDATE candidates SET campaign_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (campaign_url, row["id"]),
                )
                updated = True
        return updated

    return False


def _state_to_abbr(state_name: str) -> str | None:
    """Convert state name to two-letter abbreviation."""
    mapping = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
        "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
        "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
        "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    }
    return mapping.get(state_name)
