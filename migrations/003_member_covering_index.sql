-- Migration 003: Covering index for get_active_members query
-- Optimises: SELECT user_id, display_name, username
--            FROM members WHERE group_id = ? AND is_active = 1
--            ORDER BY display_name COLLATE NOCASE
-- Without this index, SQLite uses the UNIQUE(group_id, user_id) index to filter
-- by group_id then scans + sorts. With this index, the query is fully covered.

CREATE INDEX IF NOT EXISTS idx_members_group_active_name
    ON members(group_id, is_active, display_name COLLATE NOCASE);
