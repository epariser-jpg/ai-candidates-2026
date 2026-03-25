"""Full-text keyword search using FTS5."""

from src.db.init_db import get_connection


def search_keyword(
    keyword: str,
    office: str | None = None,
    state: str | None = None,
    party: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Search content using FTS5 full-text search.

    Returns matching content with candidate info.
    """
    conn = get_connection()

    query = """
        SELECT
            ca.name, ca.party, ca.party_full, ca.office, ca.state, ca.campaign_url,
            c.id as content_id, c.source_url, c.title, c.source_type,
            snippet(content_fts, 1, '>>>', '<<<', '...', 40) as snippet,
            rank
        FROM content_fts
        JOIN content c ON content_fts.rowid = c.id
        JOIN candidates ca ON c.candidate_id = ca.id
        WHERE content_fts MATCH ?
    """
    params = [keyword]

    if office:
        query += " AND ca.office = ?"
        params.append(office)
    if state:
        query += " AND ca.state = ?"
        params.append(state.upper())
    if party:
        query += " AND ca.party = ?"
        params.append(party.upper())

    query += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]
