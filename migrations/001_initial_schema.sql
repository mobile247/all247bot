-- Migration 001: Initial schema
-- Creates groups and members tables.
-- No message content is ever stored in this schema.

CREATE TABLE IF NOT EXISTS groups (
    group_id         INTEGER PRIMARY KEY,   -- Telegram chat ID
    is_active        INTEGER NOT NULL DEFAULT 0,
    activated_by     INTEGER,               -- Telegram user ID of activating admin
    activated_at     TEXT,                  -- ISO 8601 datetime
    mention_mode     TEXT NOT NULL DEFAULT 'display_name',
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    delete_trigger         INTEGER NOT NULL DEFAULT 0,
    restrict_all_to_admins INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS members (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id     INTEGER NOT NULL REFERENCES groups(group_id),
    user_id      INTEGER NOT NULL,
    display_name TEXT,
    username     TEXT,
    last_seen_at TEXT,
    is_active    INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(group_id, user_id)
);
