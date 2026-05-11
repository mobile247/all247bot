-- Migration 003: Registration tokens
-- Adds invite_expiry_hours to groups and creates registration_tokens table.

ALTER TABLE groups ADD COLUMN invite_expiry_hours INTEGER NOT NULL DEFAULT 24;

CREATE TABLE IF NOT EXISTS registration_tokens (
    token      TEXT    PRIMARY KEY,
    group_id   INTEGER NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reg_tokens_group   ON registration_tokens(group_id);
CREATE INDEX IF NOT EXISTS idx_reg_tokens_expires ON registration_tokens(expires_at);
