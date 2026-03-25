"""Structured tag-based and filter-based search."""

import sqlite3
from src.db.init_db import get_connection


def search_by_tags(
    tags: list[str] | None = None,
    party: str | None = None,
    office: str | None = None,
    state: str | None = None,
    sentiment: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search excerpts by structured filters.

    Returns list of result dicts with candidate and excerpt info.
    """
    conn = get_connection()

    query = """
        SELECT DISTINCT
            ca.name, ca.party, ca.party_full, ca.office, ca.state, ca.campaign_url,
            e.id as excerpt_id, e.excerpt_text, e.position_summary,
            e.sentiment, e.confidence,
            c.source_url, c.title as page_title,
            GROUP_CONCAT(t.name, ', ') as tag_names
        FROM excerpts e
        JOIN candidates ca ON e.candidate_id = ca.id
        JOIN content c ON e.content_id = c.id
        LEFT JOIN excerpt_tags et ON e.id = et.excerpt_id
        LEFT JOIN tags t ON et.tag_id = t.id
        WHERE 1=1
    """
    params = []

    if tags:
        placeholders = ",".join("?" * len(tags))
        query += f"""
            AND e.id IN (
                SELECT et2.excerpt_id FROM excerpt_tags et2
                JOIN tags t2 ON et2.tag_id = t2.id
                WHERE t2.name IN ({placeholders})
            )
        """
        params.extend(tags)

    if party:
        query += " AND ca.party = ?"
        params.append(party.upper())
    if office:
        query += " AND ca.office = ?"
        params.append(office)
    if state:
        query += " AND ca.state = ?"
        params.append(state.upper())
    if sentiment:
        query += " AND e.sentiment = ?"
        params.append(sentiment)

    query += " GROUP BY e.id ORDER BY ca.name, e.confidence DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]


def get_candidate_positions(candidate_id: int) -> list[dict]:
    """Get all AI-related positions for a specific candidate."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            e.excerpt_text, e.position_summary, e.sentiment, e.confidence,
            c.source_url, c.title as page_title,
            GROUP_CONCAT(t.name, ', ') as tag_names
        FROM excerpts e
        JOIN content c ON e.content_id = c.id
        LEFT JOIN excerpt_tags et ON e.id = et.excerpt_id
        LEFT JOIN tags t ON et.tag_id = t.id
        WHERE e.candidate_id = ?
        GROUP BY e.id
        ORDER BY e.confidence DESC
    """, (candidate_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
