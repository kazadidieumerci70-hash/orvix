CREATE TABLE IF NOT EXISTS uploaded_documents (
    user_id TEXT NOT NULL,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    content BYTEA,
    object_key TEXT,
    content_hash CHAR(64),
    size INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(user_id, id),
    UNIQUE(user_id, name)
);

ALTER TABLE uploaded_documents ADD COLUMN IF NOT EXISTS object_key TEXT;
ALTER TABLE uploaded_documents ADD COLUMN IF NOT EXISTS content_hash CHAR(64);
ALTER TABLE uploaded_documents ALTER COLUMN content DROP NOT NULL;

CREATE INDEX IF NOT EXISTS uploaded_documents_owner_hash_idx
    ON uploaded_documents(user_id, content_hash)
    WHERE content_hash IS NOT NULL;

