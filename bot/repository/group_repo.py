"""
Group repository — CRUD operations for the groups table.
All methods accept an existing aiosqlite.Connection for transaction participation.
"""

import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_ALLOWED_CONFIG_COLUMNS = frozenset(
    {"cooldown_seconds", "delete_trigger", "restrict_all_to_admins", "mention_mode",
     "invite_expiry_hours"}
)


async def get_group(conn: aiosqlite.Connection, group_id: int) -> aiosqlite.Row | None:
    """Return the group row or None if not found."""
    async with conn.execute(
        "SELECT * FROM groups WHERE group_id = ?", (group_id,)
    ) as cur:
        return await cur.fetchone()


async def upsert_group(conn: aiosqlite.Connection, group_id: int) -> None:
    """Insert group record if it doesn't exist yet (does not overwrite existing)."""
    await conn.execute(
        "INSERT OR IGNORE INTO groups (group_id) VALUES (?)",
        (group_id,),
    )
    await conn.commit()


async def activate_group(
    conn: aiosqlite.Connection, group_id: int, activated_by: int
) -> None:
    """Set group as active, record who activated and when."""
    await conn.execute(
        """
        UPDATE groups
        SET is_active = 1,
            activated_by = ?,
            activated_at = datetime('now'),
            updated_at = datetime('now')
        WHERE group_id = ?
        """,
        (activated_by, group_id),
    )
    await conn.commit()


async def deactivate_group(conn: aiosqlite.Connection, group_id: int) -> None:
    """Set group as inactive."""
    await conn.execute(
        """
        UPDATE groups
        SET is_active = 0, updated_at = datetime('now')
        WHERE group_id = ?
        """,
        (group_id,),
    )
    await conn.commit()


async def get_all_active_group_ids(conn: aiosqlite.Connection) -> list[int]:
    """Return group_ids for all currently active groups."""
    async with conn.execute(
        "SELECT group_id FROM groups WHERE is_active = 1"
    ) as cur:
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def update_group_title(
    conn: aiosqlite.Connection, group_id: int, title: str | None
) -> None:
    """Store or refresh the group's display title."""
    await conn.execute(
        "UPDATE groups SET title = ?, updated_at = datetime('now') WHERE group_id = ?",
        (title, group_id),
    )
    await conn.commit()


async def migrate_group_id(
    conn: aiosqlite.Connection, old_id: int, new_id: int
) -> bool:
    """
    Migrate all data from old_id to new_id (group → supergroup conversion).
    Copies the group row, migrates members and rate_limit_log, deletes old row.
    Registration tokens cascade-delete with the old row (they're short-lived).
    Returns False if old_id not found or new_id already exists.
    """
    async with conn.execute(
        "SELECT COUNT(*) FROM groups WHERE group_id = ?", (new_id,)
    ) as cur:
        row = await cur.fetchone()
    if row and row[0] > 0:
        return False  # new_id already has a record — skip

    async with conn.execute(
        "SELECT COUNT(*) FROM groups WHERE group_id = ?", (old_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row or row[0] == 0:
        return False  # old_id not found — nothing to migrate

    # Copy group row with new PK
    await conn.execute(
        """
        INSERT INTO groups (
            group_id, is_active, activated_by, activated_at,
            mention_mode, cooldown_seconds, delete_trigger,
            restrict_all_to_admins, invite_expiry_hours,
            created_at, updated_at
        )
        SELECT
            ?, is_active, activated_by, activated_at,
            mention_mode, cooldown_seconds, delete_trigger,
            restrict_all_to_admins, invite_expiry_hours,
            created_at, datetime('now')
        FROM groups WHERE group_id = ?
        """,
        (new_id, old_id),
    )
    # Migrate members (FK now satisfied — new_id exists)
    await conn.execute(
        "UPDATE members SET group_id = ? WHERE group_id = ?",
        (new_id, old_id),
    )
    # Migrate rate limit log (no FK, just update)
    await conn.execute(
        "UPDATE rate_limit_log SET group_id = ? WHERE group_id = ?",
        (new_id, old_id),
    )
    # Delete old row — registration_tokens CASCADE DELETE automatically
    await conn.execute(
        "DELETE FROM groups WHERE group_id = ?",
        (old_id,),
    )
    await conn.commit()
    return True


async def update_group_config(
    conn: aiosqlite.Connection, group_id: int, key: str, value: Any
) -> None:
    """Update a single configuration field on the group record."""
    if key not in _ALLOWED_CONFIG_COLUMNS:
        raise ValueError(f"Invalid config column: {key!r}")
    await conn.execute(
        f"UPDATE groups SET {key} = ?, updated_at = datetime('now') WHERE group_id = ?",
        (value, group_id),
    )
    await conn.commit()
