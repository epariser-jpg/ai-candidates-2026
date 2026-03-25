from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candidate:
    id: int | None = None
    fec_candidate_id: str | None = None
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    party: str = ""
    party_full: str = ""
    office: str = ""
    state: str = ""
    district: str | None = None
    incumbent_status: str | None = None
    campaign_url: str | None = None
    election_year: int = 2026
    roster_source: str = ""
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class Content:
    id: int | None = None
    candidate_id: int = 0
    source_url: str = ""
    source_type: str = ""
    title: str | None = None
    raw_text: str = ""
    scraped_at: datetime | None = None
    content_hash: str = ""
    is_ai_relevant: bool | None = None


@dataclass
class Excerpt:
    id: int | None = None
    content_id: int = 0
    candidate_id: int = 0
    excerpt_text: str = ""
    context_text: str | None = None
    position_summary: str | None = None
    sentiment: str | None = None
    confidence: float | None = None
    analyzed_at: datetime | None = None
    model_used: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    candidate: Candidate
    excerpt: Excerpt
    score: float = 0.0
    match_type: str = ""  # "tag", "keyword", "semantic"
