"""Orchestrator for building and updating the candidate roster."""

import asyncio
import csv
import sqlite3
from pathlib import Path
from tqdm import tqdm

from src.config import DATABASE_PATH
from src.db.init_db import get_connection, init_db
from src.db.models import Candidate
from src.roster.fec_client import fetch_senate_candidates, fetch_house_candidates
from src.roster.fec_bulk import fetch_bulk_candidates


def upsert_candidate(conn: sqlite3.Connection, candidate: Candidate) -> int:
    """Insert or update a candidate. Returns the candidate id."""
    # Check if already exists by FEC ID
    if candidate.fec_candidate_id:
        row = conn.execute(
            "SELECT id FROM candidates WHERE fec_candidate_id = ?",
            (candidate.fec_candidate_id,),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE candidates SET
                    name=?, first_name=?, last_name=?, party=?, party_full=?,
                    office=?, state=?, district=?, incumbent_status=?,
                    campaign_url=COALESCE(?, campaign_url),
                    updated_at=CURRENT_TIMESTAMP
                WHERE fec_candidate_id=?""",
                (
                    candidate.name, candidate.first_name, candidate.last_name,
                    candidate.party, candidate.party_full,
                    candidate.office, candidate.state, candidate.district,
                    candidate.incumbent_status, candidate.campaign_url,
                    candidate.fec_candidate_id,
                ),
            )
            return row["id"]

    cursor = conn.execute(
        """INSERT INTO candidates
            (fec_candidate_id, name, first_name, last_name, party, party_full,
             office, state, district, incumbent_status, campaign_url,
             election_year, roster_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            candidate.fec_candidate_id, candidate.name, candidate.first_name,
            candidate.last_name, candidate.party, candidate.party_full,
            candidate.office, candidate.state, candidate.district,
            candidate.incumbent_status, candidate.campaign_url,
            candidate.election_year, candidate.roster_source,
        ),
    )
    return cursor.lastrowid


def load_manual_candidates(csv_path: Path) -> list[Candidate]:
    """Load candidates from a manual CSV override file.

    Expected columns: name, party, office, state, district, campaign_url, incumbent_status
    """
    if not csv_path.exists():
        return []

    candidates = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            parts = name.split(" ", 1)
            candidates.append(Candidate(
                name=name,
                first_name=parts[0] if parts else "",
                last_name=parts[1] if len(parts) > 1 else "",
                party=row.get("party", "").strip(),
                office=row.get("office", "").strip(),
                state=row.get("state", "").strip(),
                district=row.get("district", "").strip() or None,
                incumbent_status=row.get("incumbent_status", "").strip() or None,
                campaign_url=row.get("campaign_url", "").strip() or None,
                roster_source="manual",
            ))
    return candidates


async def run_roster_pipeline(
    office: str = "Senate",
    discover_urls: bool = False,
    manual_csv: Path | None = None,
    use_bulk: bool = False,
) -> dict:
    """Run the full roster pipeline.

    Args:
        office: "Senate", "House", or "Governor"
        discover_urls: Whether to attempt URL discovery (slow)
        manual_csv: Path to manual candidates CSV
        use_bulk: Use FEC bulk data download instead of API (no rate limits)

    Returns:
        Summary stats dict
    """
    conn = init_db()
    stats = {"fetched": 0, "inserted": 0, "updated": 0, "manual": 0, "urls_found": 0}

    # Fetch from FEC
    office_code = {"Senate": "S", "House": "H"}.get(office)

    if use_bulk and office_code:
        candidates = fetch_bulk_candidates(office_filter=office_code)
    elif office == "Senate":
        print(f"Fetching {office} candidates from FEC API...")
        candidates = await fetch_senate_candidates()
    elif office == "House":
        print(f"Fetching {office} candidates from FEC API...")
        candidates = await fetch_house_candidates()
    else:
        candidates = []  # Governor races not in FEC — use manual CSV

    stats["fetched"] = len(candidates)
    print(f"  Found {len(candidates)} candidates from FEC")

    # Insert/update candidates
    for c in tqdm(candidates, desc="Saving candidates"):
        existing = conn.execute(
            "SELECT id FROM candidates WHERE fec_candidate_id = ?",
            (c.fec_candidate_id,),
        ).fetchone()
        upsert_candidate(conn, c)
        if existing:
            stats["updated"] += 1
        else:
            stats["inserted"] += 1

    # Load manual candidates
    if manual_csv:
        manual = load_manual_candidates(manual_csv)
        stats["manual"] = len(manual)
        for c in manual:
            upsert_candidate(conn, c)
        print(f"  Loaded {len(manual)} manual candidates")

    # Optionally discover URLs
    if discover_urls:
        from src.roster.url_discovery import discover_urls as discover
        no_url = [
            Candidate(**dict(row))
            for row in conn.execute(
                "SELECT * FROM candidates WHERE campaign_url IS NULL AND office = ?",
                (office,),
            ).fetchall()
        ]
        if no_url:
            print(f"  Discovering URLs for {len(no_url)} candidates...")
            url_map = await discover(no_url)
            for fec_id, url in url_map.items():
                conn.execute(
                    "UPDATE candidates SET campaign_url = ?, updated_at = CURRENT_TIMESTAMP WHERE fec_candidate_id = ?",
                    (url, fec_id),
                )
            stats["urls_found"] = len(url_map)
            print(f"  Found {len(url_map)} campaign URLs")

    conn.commit()

    # Print summary
    total = conn.execute(
        "SELECT COUNT(*) as n FROM candidates WHERE office = ?", (office,)
    ).fetchone()["n"]
    with_url = conn.execute(
        "SELECT COUNT(*) as n FROM candidates WHERE office = ? AND campaign_url IS NOT NULL",
        (office,),
    ).fetchone()["n"]

    print(f"\n  Total {office} candidates in DB: {total}")
    print(f"  With campaign URL: {with_url}")

    conn.close()
    return stats
