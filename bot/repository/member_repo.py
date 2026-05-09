"""
Member repository — CRUD operations for the members table.
Stores only Telegram-native metadata: user_id, display_name, username.
Message content is NEVER stored here.
"""

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def upsert_member(
    conn: aiosqlite.Connection,
    group_id: int,
    user_id: int,
    display_name: str | None,
    username: str | None,
) -> None:
    """
    Insert or update a member record. Updates display_name, username,
    last_seen_at, and is_active=1 on conflict. Bots must be excluded
    before calling this — this function does not check is_bot.
    """
    raise NotImplementedError


async def get_active_members(
    conn: aiosqlite.Connection, group_id: int
) -> list[aiosqlite.Row]:
    """
    Return all active members for the group, ordered alphabetically
    by display_name (COLLATE NOCASE). Used by MentionService.
    """
    raise NotImplementedError


async def set_member_active(
    conn: aiosqlite.Connection, group_id: int, user_id: int, is_active: int
) -> None:
    """Set is_active flag for a member (0 = inactive, 1 = active)."""
    raise NotImplementedError


async def prune_stale_members(
    conn: aiosqlite.Connection, group_id: int, days: int
) -> int:
    """
    Set is_active=0 for members with no last_seen_at activity beyond `days`.
    Returns number of members marked inactive.
    """
    raise NotImplementedError


async def hard_delete_stale_members(
    conn: aiosqlite.Connection, group_id: int, days: int
) -> int:
    """
    Hard-delete members with no activity beyond `days`. Explicit opt-in only.
    Returns number of rows deleted.
    """
    raise NotImplementedError
