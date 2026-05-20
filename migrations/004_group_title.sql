-- Migration 004: Store group title
-- Adds title column to groups table for display in /migrate and future commands.

ALTER TABLE groups ADD COLUMN title TEXT;
