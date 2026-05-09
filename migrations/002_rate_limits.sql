-- Migration 002: Rate limit log
-- Retained only for cooldown enforcement, purged on configurable schedule.
-- Stores group_id + timestamp only. triggered_by (user_id) is intentionally NOT stored:
-- cooldown is per-group, not per-user, so user_id is not needed for enforcement.
-- user_id is logged to stdout at invocation time (ephemeral) but not persisted.

CREATE TABLE IF NOT EXISTS rate_limit_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id     INTEGER NOT NULL,
    triggered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_group_time
    ON rate_limit_log(group_id, triggered_at);
