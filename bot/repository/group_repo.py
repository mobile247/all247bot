"""
Group repository — CRUD operations for the groups table.
All methods accept a db_path string and open their own connection,
or accept an existing aiosqlite.Connection for transaction participation.
"""

import logging
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


async def get_group(conn: aiosqlite.Connection, group_id: int) -> aiosqlite.Row | None:
    """Return the group row or None if not found."""
    raise NotImplementedError


async def upsert_group(conn: aiosqlite.Connection, group_id: int) -> None:
    """Insert group record if it doesn't exist yet (does not overwrite existing)."""
    raise NotImplementedError


async def activate_group(
    conn: aiosqlite.Connection, group_id: int, activated_by: int
) -> None:
    """Set group as active, record who activated and when."""
    raise NotImplementedError


async def deactivate_group(conn: aiosqlite.Connection, group_id: int) -> None:
    """Set group as inactive."""
    raise NotImplementedError


async def update_group_config(
    conn: aiosqlite.Connection, group_id: int, key: str, value: Any
) -> None:
    """Update a single configuration field on the group record."""
    raise NotImplementedError
