"""Semantic search using embeddings and sqlite-vec."""

import struct

from src.db.init_db import get_connection, init_vec_table
from src.embeddings.local_embedder import embed_query


def search_semantic(
    query: str,
    office: str | None = None,
    state: str | None = None,
    party: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search excerpts by semantic similarity.

    Args:
        query: Natural language query
        office: Filter by office type
        state: Filter by state
        party: Filter by party

    Returns list of results sorted by similarity.
    """
    conn = get_connection()

    try:
        init_vec_table(conn)
    except Exception:
        print("Vector table not available. Run 'embed' command first.")
        conn.close()
        return []

    # Get query embedding
    query_emb = embed_query(query)
    query_bytes = struct.pack(f"{len(query_emb)}f", *query_emb)

    # Search via sqlite-vec
    # First get candidate IDs from vec search, then join
    vec_query = """
        SELECT excerpt_id, distance
        FROM excerpt_embeddings
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT ?
    """
    vec_rows = conn.execute(vec_query, (query_bytes, limit * 3)).fetchall()

    if not vec_rows:
        conn.close()
        return []

    # Get full excerpt/candidate data for matches
    excerpt_ids = [r["excerpt_id"] for r in vec_rows]
    distances = {r["excerpt_id"]: r["distance"] for r in vec_rows}

    placeholders = ",".join("?" * len(excerpt_ids))
    detail_query = f"""
        SELECT
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
        WHERE e.id IN ({placeholders})
    """
    params = list(excerpt_ids)

    if office:
        detail_query += " AND ca.office = ?"
        params.append(office)
    if state:
        detail_query += " AND ca.state = ?"
        params.append(state.upper())
    if party:
        detail_query += " AND ca.party = ?"
        params.append(party.upper())

    detail_query += " GROUP BY e.id"
    rows = conn.execute(detail_query, params).fetchall()
    conn.close()

    # Sort by distance (lower = more similar)
    results = []
    for row in rows:
        result = dict(row)
        result["similarity"] = 1.0 - distances.get(row["excerpt_id"], 1.0)
        results.append(result)

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
