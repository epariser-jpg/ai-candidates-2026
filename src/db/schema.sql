-- 2026 Candidates AI Positions Database Schema

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fec_candidate_id TEXT UNIQUE,
    name TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    party TEXT,
    party_full TEXT,
    office TEXT NOT NULL,
    state TEXT NOT NULL,
    district TEXT,
    incumbent_status TEXT,
    campaign_url TEXT,
    election_year INTEGER DEFAULT 2026,
    roster_source TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT,
    raw_text TEXT NOT NULL,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT NOT NULL,
    is_ai_relevant BOOLEAN,
    UNIQUE(source_url, content_hash)
);

CREATE TABLE IF NOT EXISTS excerpts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL REFERENCES content(id),
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    excerpt_text TEXT NOT NULL,
    context_text TEXT,
    position_summary TEXT,
    sentiment TEXT,
    confidence REAL,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS excerpt_tags (
    excerpt_id INTEGER NOT NULL REFERENCES excerpts(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (excerpt_id, tag_id)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    url TEXT NOT NULL,
    status_code INTEGER,
    pages_found INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS content_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER NOT NULL REFERENCES content(id),
    content_hash TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    title, raw_text,
    content='content',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content BEGIN
    INSERT INTO content_fts(rowid, title, raw_text) VALUES (new.id, new.title, new.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content BEGIN
    INSERT INTO content_fts(content_fts, rowid, title, raw_text) VALUES('delete', old.id, old.title, old.raw_text);
END;

CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content BEGIN
    INSERT INTO content_fts(content_fts, rowid, title, raw_text) VALUES('delete', old.id, old.title, old.raw_text);
    INSERT INTO content_fts(rowid, title, raw_text) VALUES (new.id, new.title, new.raw_text);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_candidates_office ON candidates(office);
CREATE INDEX IF NOT EXISTS idx_candidates_state ON candidates(state);
CREATE INDEX IF NOT EXISTS idx_candidates_party ON candidates(party);
CREATE INDEX IF NOT EXISTS idx_content_candidate ON content(candidate_id);
CREATE INDEX IF NOT EXISTS idx_content_ai_relevant ON content(is_ai_relevant);
CREATE INDEX IF NOT EXISTS idx_excerpts_candidate ON excerpts(candidate_id);
CREATE INDEX IF NOT EXISTS idx_excerpts_content ON excerpts(content_id);

-- Seed tags
INSERT OR IGNORE INTO tags (name) VALUES
    ('ai_regulation'), ('ai_education'), ('ai_jobs_workforce'),
    ('ai_military_defense'), ('ai_healthcare'), ('ai_surveillance_privacy'),
    ('ai_bias_fairness'), ('ai_copyright_ip'), ('ai_existential_risk'),
    ('ai_competitiveness_china'), ('ai_open_source'), ('ai_government_use'),
    ('automation_general'), ('tech_regulation_general'), ('algorithmic_accountability'),
    ('deepfakes_misinfo'), ('ai_energy_climate'), ('ai_agriculture');
