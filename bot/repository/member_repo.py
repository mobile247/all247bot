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
    await conn.execute(
        """
        INSERT INTO members (group_id, user_id, display_name, username, last_seen_at, is_active)
        VALUES (?, ?, ?, ?, datetime('now'), 1)
        ON CONFLICT(group_id, user_id) DO UPDATE SET
            display_name = excluded.display_name,
            username = excluded.username,
            last_seen_at = datetime('now'),
            is_active = 1,
            updated_at = datetime('now')
        """,
        (group_id, user_id, display_name, username),
    )
    await conn.commit()


async def get_active_members(
    conn: aiosqlite.Connection, group_id: int
) -> list[aiosqlite.Row]:
    """
    Return all active members for the group, ordered alphabetically
    by display_name (COLLATE NOCASE). Used by MentionService.
    """
    async with conn.execute(
        """
        SELECT user_id, display_name, username
        FROM members
        WHERE group_id = ? AND is_active = 1
        ORDER BY display_name COLLATE NOCASE
        """,
        (group_id,),
    ) as cur:
        return await cur.fetchall()


async def set_member_active(
    conn: aiosqlite.Connection, group_id: int, user_id: int, is_active: int
) -> None:
    """Set is_active flag for a member (0 = inactive, 1 = active).
    Also updates last_seen_at when activating (is_active=1)."""
    if is_active:
        await conn.execute(
            """
            UPDATE members
            SET is_active = 1,
                last_seen_at = datetime('now'),
                updated_at = datetime('now')
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id),
        )
    else:
        await conn.execute(
            """
            UPDATE members
            SET is_active = 0, updated_at = datetime('now')
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id),
        )
    await conn.commit()


async def prune_stale_members(
    conn: aiosqlite.Connection, group_id: int, days: int
) -> int:
    """
    Set is_active=0 for members with no last_seen_at activity beyond `days`.
    Returns number of members marked inactive.
    """
    cur = await conn.execute(
        """
        UPDATE members
        SET is_active = 0, updated_at = datetime('now')
        WHERE group_id = ?
          AND is_active = 1
          AND (last_seen_at IS NULL OR last_seen_at < datetime('now', ?))
        """,
        (group_id, f"-{days} days"),
    )
    await conn.commit()
    return cur.rowcount


async def hard_delete_stale_members(
    conn: aiosqlite.Connection, group_id: int, days: int
) -> int:
    """
    Hard-delete members with no activity beyond `days`. Explicit opt-in only.
    Returns number of rows deleted.
    """
    cur = await conn.execute(
        """
        DELETE FROM members
        WHERE group_id = ?
          AND (last_seen_at IS NULL OR last_seen_at < datetime('now', ?))
        """,
        (group_id, f"-{days} days"),
    )
    await conn.commit()
    return cur.rowcount


async def copy_members_to_group(
    conn: aiosqlite.Connection, from_id: int, to_id: int
) -> int:
    """
    Copy all active members from from_id into to_id.
    Uses INSERT OR IGNORE — existing members in to_id are not overwritten.
    Returns number of rows inserted.
    """
    cur = await conn.execute(
        """
        INSERT OR IGNORE INTO members (group_id, user_id, display_name, username, last_seen_at, is_active)
        SELECT ?, user_id, display_name, username, last_seen_at, 1
        FROM members
        WHERE group_id = ? AND is_active = 1
        """,
        (to_id, from_id),
    )
    await conn.commit()
    return cur.rowcount


async def delete_group_members(
    conn: aiosqlite.Connection, group_id: int
) -> int:
    """
    Hard-delete ALL member records for a group. Used when the bot leaves a group.
    Returns number of rows deleted.
    """
    cur = await conn.execute(
        "DELETE FROM members WHERE group_id = ?",
        (group_id,),
    )
    await conn.commit()
    return cur.rowcount
