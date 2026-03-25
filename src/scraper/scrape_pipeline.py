"""Orchestrator for scraping campaign websites."""

import asyncio
import sqlite3
from datetime import datetime

from tqdm import tqdm

from src.config import DATABASE_PATH
from src.db.init_db import get_connection
from src.scraper.crawler import crawl_site


async def scrape_candidate(
    conn: sqlite3.Connection,
    candidate_id: int,
    campaign_url: str,
    candidate_name: str,
) -> dict:
    """Scrape a single candidate's website and store results.

    Returns stats dict.
    """
    stats = {"pages": 0, "new": 0, "unchanged": 0, "errors": 0}

    started_at = datetime.now().isoformat()

    try:
        pages = await crawl_site(campaign_url)
        stats["pages"] = len(pages)

        for page in pages:
            # Check if we already have this exact content
            existing = conn.execute(
                "SELECT id FROM content WHERE source_url = ? AND content_hash = ?",
                (page["url"], page["content_hash"]),
            ).fetchone()

            if existing:
                stats["unchanged"] += 1
                continue

            # Check if URL exists with different hash (content changed)
            old = conn.execute(
                "SELECT id, content_hash, raw_text FROM content WHERE source_url = ?",
                (page["url"],),
            ).fetchone()

            if old:
                # Archive old version
                conn.execute(
                    "INSERT INTO content_versions (content_id, content_hash, raw_text) VALUES (?, ?, ?)",
                    (old["id"], old["content_hash"], old["raw_text"]),
                )
                # Update with new content
                conn.execute(
                    """UPDATE content SET raw_text = ?, content_hash = ?, title = ?,
                       scraped_at = CURRENT_TIMESTAMP, is_ai_relevant = NULL
                    WHERE id = ?""",
                    (page["text"], page["content_hash"], page["title"], old["id"]),
                )
            else:
                # New page
                conn.execute(
                    """INSERT INTO content
                        (candidate_id, source_url, source_type, title, raw_text, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        candidate_id, page["url"], page["source_type"],
                        page["title"], page["text"], page["content_hash"],
                    ),
                )
            stats["new"] += 1

        # Log the scrape
        conn.execute(
            """INSERT INTO scrape_log
                (candidate_id, url, status_code, pages_found, started_at, completed_at)
            VALUES (?, ?, 200, ?, ?, ?)""",
            (candidate_id, campaign_url, len(pages), started_at, datetime.now().isoformat()),
        )

    except Exception as e:
        stats["errors"] = 1
        conn.execute(
            """INSERT INTO scrape_log
                (candidate_id, url, status_code, started_at, completed_at, error_message)
            VALUES (?, ?, 0, ?, ?, ?)""",
            (candidate_id, campaign_url, started_at, datetime.now().isoformat(), str(e)),
        )

    return stats


async def run_scrape_pipeline(
    office: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    candidate_id: int | None = None,
) -> dict:
    """Run the scraping pipeline for candidates with campaign URLs.

    Args:
        office: Filter by office type
        state: Filter by state
        limit: Max candidates to scrape
        candidate_id: Scrape a specific candidate
    """
    conn = get_connection()
    total_stats = {"candidates": 0, "pages": 0, "new": 0, "unchanged": 0, "errors": 0}

    # Build query for candidates to scrape
    query = "SELECT id, name, campaign_url FROM candidates WHERE campaign_url IS NOT NULL"
    params = []

    if candidate_id:
        query += " AND id = ?"
        params.append(candidate_id)
    if office:
        query += " AND office = ?"
        params.append(office)
    if state:
        query += " AND state = ?"
        params.append(state.upper())

    query += " ORDER BY name"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No candidates with campaign URLs found. Run URL discovery first.")
        conn.close()
        return total_stats

    print(f"Scraping {len(rows)} candidates...")

    for row in tqdm(rows, desc="Scraping"):
        stats = await scrape_candidate(
            conn, row["id"], row["campaign_url"], row["name"]
        )
        total_stats["candidates"] += 1
        for k in ["pages", "new", "unchanged", "errors"]:
            total_stats[k] += stats[k]
        conn.commit()

    # Summary
    content_count = conn.execute("SELECT COUNT(*) as n FROM content").fetchone()["n"]
    print(f"\nScraping complete:")
    print(f"  Candidates scraped: {total_stats['candidates']}")
    print(f"  Pages found: {total_stats['pages']}")
    print(f"  New/updated: {total_stats['new']}")
    print(f"  Unchanged: {total_stats['unchanged']}")
    print(f"  Errors: {total_stats['errors']}")
    print(f"  Total content in DB: {content_count}")

    conn.close()
    return total_stats
