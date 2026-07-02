CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    normalized_title VARCHAR(500) NOT NULL,
    summary TEXT,
    event_type VARCHAR(100) NOT NULL DEFAULT 'development',
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    primary_language VARCHAR(50),
    country_or_region VARCHAR(255),
    first_seen_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_events_normalized_title ON events (normalized_title);
CREATE INDEX IF NOT EXISTS ix_events_first_seen_at ON events (first_seen_at);
CREATE INDEX IF NOT EXISTS ix_events_last_seen_at ON events (last_seen_at);

CREATE TABLE IF NOT EXISTS event_documents (
    id SERIAL PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id),
    document_id INTEGER NOT NULL REFERENCES documents(id),
    relationship_type VARCHAR(50) NOT NULL DEFAULT 'primary',
    similarity_score DOUBLE PRECISION,
    clustering_method VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_event_documents_event_document UNIQUE (event_id, document_id)
);

CREATE INDEX IF NOT EXISTS ix_event_documents_event_id ON event_documents (event_id);
CREATE INDEX IF NOT EXISTS ix_event_documents_document_id ON event_documents (document_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_event_documents_primary_document
ON event_documents (document_id)
WHERE relationship_type = 'primary';
