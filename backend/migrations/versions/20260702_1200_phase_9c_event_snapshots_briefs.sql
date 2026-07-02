CREATE TABLE IF NOT EXISTS event_snapshots (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    snapshot_type VARCHAR(50) NOT NULL DEFAULT 'event_state',
    event_title VARCHAR(500) NOT NULL,
    event_summary TEXT,
    event_status VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    country_or_region VARCHAR(255),
    primary_language VARCHAR(50),
    document_count INTEGER NOT NULL DEFAULT 0,
    distinct_source_count INTEGER NOT NULL DEFAULT 0,
    distinct_publisher_count INTEGER NOT NULL DEFAULT 0,
    document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    publisher_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    latest_evidence_at TIMESTAMP,
    snapshot_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_event_snapshots_event_id ON event_snapshots (event_id);
CREATE INDEX IF NOT EXISTS ix_event_snapshots_created_at ON event_snapshots (created_at);
CREATE INDEX IF NOT EXISTS ix_event_snapshots_snapshot_hash ON event_snapshots (snapshot_hash);

CREATE TABLE IF NOT EXISTS event_briefs (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    snapshot_id INTEGER NOT NULL REFERENCES event_snapshots(id),
    previous_snapshot_id INTEGER REFERENCES event_snapshots(id),
    brief_status VARCHAR(50) NOT NULL DEFAULT 'draft',
    reviewer_notes TEXT,
    headline VARCHAR(500) NOT NULL,
    what_happened TEXT,
    what_changed TEXT,
    why_it_matters TEXT,
    confirmed_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    uncertainties JSONB NOT NULL DEFAULT '[]'::jsonb,
    watch_next JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    change_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    generation_method VARCHAR(50) NOT NULL DEFAULT 'deterministic',
    model_name VARCHAR(255),
    prompt_version VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_event_briefs_event_id ON event_briefs (event_id);
CREATE INDEX IF NOT EXISTS ix_event_briefs_snapshot_id ON event_briefs (snapshot_id);
CREATE INDEX IF NOT EXISTS ix_event_briefs_created_at ON event_briefs (created_at);
