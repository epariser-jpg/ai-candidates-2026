"""Hybrid search combining structured, keyword, and semantic results."""

from src.search.structured import search_by_tags
from src.search.fulltext import search_keyword
from src.search.semantic import search_semantic


def hybrid_search(
    query: str | None = None,
    tags: list[str] | None = None,
    keyword: str | None = None,
    office: str | None = None,
    state: str | None = None,
    party: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Combine multiple search modes using reciprocal rank fusion.

    Provide any combination of query (semantic), tags (structured), keyword (FTS).
    Results are merged and ranked.
    """
    all_results: list[list[dict]] = []
    result_keys: dict[str, dict] = {}  # keyed by unique identifier

    # Structured search
    if tags:
        tag_results = search_by_tags(tags=tags, office=office, state=state, party=party, limit=limit * 2)
        for i, r in enumerate(tag_results):
            key = f"{r.get('name', '')}:{r.get('excerpt_id', i)}"
            r["_rank_tag"] = i + 1
            result_keys.setdefault(key, {}).update(r)
            result_keys[key]["_rank_tag"] = i + 1

    # Keyword search
    if keyword:
        kw_results = search_keyword(keyword=keyword, office=office, state=state, party=party, limit=limit * 2)
        for i, r in enumerate(kw_results):
            key = f"{r.get('name', '')}:{r.get('content_id', i)}"
            r["_rank_kw"] = i + 1
            result_keys.setdefault(key, {}).update(r)
            result_keys[key]["_rank_kw"] = i + 1

    # Semantic search
    if query:
        sem_results = search_semantic(query=query, office=office, state=state, party=party, limit=limit * 2)
        for i, r in enumerate(sem_results):
            key = f"{r.get('name', '')}:{r.get('excerpt_id', i)}"
            r["_rank_sem"] = i + 1
            result_keys.setdefault(key, {}).update(r)
            result_keys[key]["_rank_sem"] = i + 1

    # Reciprocal Rank Fusion
    k = 60  # RRF constant
    scored = []
    for key, data in result_keys.items():
        score = 0.0
        if "_rank_tag" in data:
            score += 1.0 / (k + data["_rank_tag"])
        if "_rank_kw" in data:
            score += 1.0 / (k + data["_rank_kw"])
        if "_rank_sem" in data:
            score += 1.0 / (k + data["_rank_sem"])

        # Clean up internal fields
        for field in ("_rank_tag", "_rank_kw", "_rank_sem"):
            data.pop(field, None)

        data["rrf_score"] = score
        scored.append(data)

    scored.sort(key=lambda x: x["rrf_score"], reverse=True)
    return scored[:limit]
