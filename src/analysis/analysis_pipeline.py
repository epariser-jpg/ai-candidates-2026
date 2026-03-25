"""Orchestrator for AI content analysis pipeline."""

import sqlite3
from datetime import datetime

from tqdm import tqdm

from src.config import ANALYSIS_MODEL, ANALYSIS_BATCH_SIZE
from src.db.init_db import get_connection
from src.analysis.claude_client import analyze_content
from src.analysis.parser import validate_and_clean


def get_or_create_tag(conn: sqlite3.Connection, tag_name: str) -> int:
    """Get tag ID, creating if needed."""
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,))
    return cursor.lastrowid


def store_analysis(conn: sqlite3.Connection, content_id: int, candidate_id: int, result: dict, model: str):
    """Store analysis results in the database."""
    cleaned = validate_and_clean(result)

    # Update content AI relevance flag
    conn.execute(
        "UPDATE content SET is_ai_relevant = ? WHERE id = ?",
        (cleaned["is_ai_relevant"], content_id),
    )

    # Store each excerpt
    for excerpt in cleaned["excerpts"]:
        cursor = conn.execute(
            """INSERT INTO excerpts
                (content_id, candidate_id, excerpt_text, context_text,
                 position_summary, sentiment, confidence, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                content_id, candidate_id,
                excerpt["excerpt_text"], excerpt["context_text"],
                excerpt["position_summary"], excerpt["sentiment"],
                excerpt["confidence"], model,
            ),
        )
        excerpt_id = cursor.lastrowid

        # Link tags
        for tag_name in excerpt["tags"]:
            tag_id = get_or_create_tag(conn, tag_name)
            conn.execute(
                "INSERT OR IGNORE INTO excerpt_tags (excerpt_id, tag_id) VALUES (?, ?)",
                (excerpt_id, tag_id),
            )


async def run_analysis_pipeline(
    office: str | None = None,
    state: str | None = None,
    limit: int | None = None,
    candidate_id: int | None = None,
    reanalyze: bool = False,
    model: str = ANALYSIS_MODEL,
) -> dict:
    """Run the AI analysis pipeline on scraped content.

    Args:
        office: Filter by office type
        state: Filter by state
        limit: Max content items to analyze
        candidate_id: Analyze content for a specific candidate
        reanalyze: Re-analyze content that was already analyzed
        model: Claude model to use
    """
    conn = get_connection()
    stats = {"analyzed": 0, "ai_relevant": 0, "excerpts": 0, "errors": 0}

    # Build query for unanalyzed content
    query = """
        SELECT c.id as content_id, c.raw_text, c.source_url, c.title,
               ca.id as candidate_id, ca.name, ca.party_full, ca.office, ca.state
        FROM content c
        JOIN candidates ca ON c.candidate_id = ca.id
        WHERE 1=1
    """
    params = []

    if not reanalyze:
        query += " AND c.is_ai_relevant IS NULL"
    if candidate_id:
        query += " AND ca.id = ?"
        params.append(candidate_id)
    if office:
        query += " AND ca.office = ?"
        params.append(office)
    if state:
        query += " AND ca.state = ?"
        params.append(state.upper())

    query += " ORDER BY ca.name, c.id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        print("No unanalyzed content found.")
        conn.close()
        return stats

    print(f"Analyzing {len(rows)} content items with {model}...")

    for row in tqdm(rows, desc="Analyzing"):
        try:
            result = await analyze_content(
                candidate_name=row["name"],
                party=row["party_full"],
                office=row["office"],
                state=row["state"],
                source_url=row["source_url"],
                raw_text=row["raw_text"],
                model=model,
            )

            store_analysis(conn, row["content_id"], row["candidate_id"], result, model)
            conn.commit()

            stats["analyzed"] += 1
            cleaned = validate_and_clean(result)
            if cleaned["is_ai_relevant"]:
                stats["ai_relevant"] += 1
                stats["excerpts"] += len(cleaned["excerpts"])

        except Exception as e:
            stats["errors"] += 1
            # Mark as analyzed but not relevant on error
            conn.execute(
                "UPDATE content SET is_ai_relevant = 0 WHERE id = ?",
                (row["content_id"],),
            )
            conn.commit()
            print(f"\n  Error analyzing content {row['content_id']}: {e}")

    # Summary
    total_excerpts = conn.execute("SELECT COUNT(*) as n FROM excerpts").fetchone()["n"]
    print(f"\nAnalysis complete:")
    print(f"  Content analyzed: {stats['analyzed']}")
    print(f"  AI-relevant: {stats['ai_relevant']}")
    print(f"  Excerpts extracted: {stats['excerpts']}")
    print(f"  Errors: {stats['errors']}")
    print(f"  Total excerpts in DB: {total_excerpts}")

    conn.close()
    return stats
