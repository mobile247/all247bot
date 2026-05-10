"""
GroupService — business logic for group activation and configuration.
Wraps group_repo with validation and logging. Config changes are logged
(setting name, old value, new value, changed_by) but never include message content.
"""

import logging

import aiosqlite

from bot.repository import db, group_repo

logger = logging.getLogger(__name__)

VALID_CONFIG_KEYS = {"cooldown", "delete_trigger", "mention_mode", "restrict_all_to_admins"}

VALID_CONFIG_VALUES = {
    "mention_mode": {"display_name", "username"},
    "delete_trigger": {"on", "off"},
    "restrict_all_to_admins": {"on", "off"},
}

# Maps user-facing config key → DB column name
_KEY_TO_COLUMN = {
    "cooldown": "cooldown_seconds",
    "delete_trigger": "delete_trigger",
    "restrict_all_to_admins": "restrict_all_to_admins",
    "mention_mode": "mention_mode",
}

_CONFIG_DEFAULTS = {
    "cooldown": 0,
    "delete_trigger": "off",
    "restrict_all_to_admins": "off",
    "mention_mode": "display_name",
}


def _row_to_config(row: aiosqlite.Row) -> dict:
    return {
        "cooldown": row["cooldown_seconds"],
        "delete_trigger": "on" if row["delete_trigger"] else "off",
        "restrict_all_to_admins": "on" if row["restrict_all_to_admins"] else "off",
        "mention_mode": row["mention_mode"],
    }


def _coerce_value(key: str, value: str):
    """Convert user-facing string value to DB-ready value."""
    if key == "cooldown":
        try:
            int_val = int(value)
        except ValueError:
            raise ValueError(f"'cooldown' must be an integer >= 0, got {value!r}")
        if int_val < 0:
            raise ValueError(f"'cooldown' must be >= 0, got {int_val}")
        return int_val
    if key in ("delete_trigger", "restrict_all_to_admins"):
        return 1 if value == "on" else 0
    return value  # mention_mode: stored as-is


class GroupService:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        # In-memory set of active group IDs. None = not yet loaded from DB.
        # Eliminates per-message DB round-trip for is_active() check.
        self._active_groups: set[int] | None = None

    async def _ensure_active_cache(self) -> None:
        """Lazy-load active group IDs from DB on first call."""
        if self._active_groups is None:
            async with db.get_connection(self._db_path) as conn:
                ids = await group_repo.get_all_active_group_ids(conn)
            self._active_groups = set(ids)

    async def activate(self, group_id: int, activated_by: int) -> bool:
        """
        Activate the bot for a group. Returns False if already active.
        Logs group_id, activated_by, timestamp.
        """
        async with db.get_connection(self._db_path) as conn:
            await group_repo.upsert_group(conn, group_id)
            row = await group_repo.get_group(conn, group_id)
            if row and row["is_active"]:
                return False
            await group_repo.activate_group(conn, group_id, activated_by)
        if self._active_groups is not None:
            self._active_groups.add(group_id)
        logger.info("Group activated: group_id=%d activated_by=%d", group_id, activated_by)
        return True

    async def deactivate(self, group_id: int, deactivated_by: int) -> None:
        """Deactivate the bot for a group. Logs group_id, deactivated_by, timestamp."""
        async with db.get_connection(self._db_path) as conn:
            await group_repo.deactivate_group(conn, group_id)
        if self._active_groups is not None:
            self._active_groups.discard(group_id)
        logger.info("Group deactivated: group_id=%d deactivated_by=%d", group_id, deactivated_by)

    async def is_active(self, group_id: int) -> bool:
        """Return True if the group has been activated. Uses in-memory cache after first call."""
        await self._ensure_active_cache()
        return group_id in self._active_groups  # type: ignore[operator]

    async def get_config(self, group_id: int) -> dict:
        """Return current group configuration as a dict."""
        async with db.get_connection(self._db_path) as conn:
            row = await group_repo.get_group(conn, group_id)
        if row is None:
            return dict(_CONFIG_DEFAULTS)
        return _row_to_config(row)

    async def update_config(
        self, group_id: int, key: str, value: str, changed_by: int
    ) -> None:
        """
        Validate and update a config key. Raises ValueError on invalid key/value.
        Logs setting name, new value, changed_by — no message content.
        """
        if key not in VALID_CONFIG_KEYS:
            valid = ", ".join(sorted(VALID_CONFIG_KEYS))
            raise ValueError(f"Invalid config key {key!r}. Valid keys: {valid}")

        if key in VALID_CONFIG_VALUES and value not in VALID_CONFIG_VALUES[key]:
            valid = ", ".join(sorted(VALID_CONFIG_VALUES[key]))
            raise ValueError(
                f"Invalid value {value!r} for {key!r}. Valid values: {valid}"
            )

        db_value = _coerce_value(key, value)
        db_column = _KEY_TO_COLUMN[key]

        async with db.get_connection(self._db_path) as conn:
            await group_repo.upsert_group(conn, group_id)
            await group_repo.update_group_config(conn, group_id, db_column, db_value)

        logger.info(
            "Config updated: group_id=%d key=%s new=%r changed_by=%d",
            group_id,
            key,
            db_value,
            changed_by,
        )

    async def get_all_active_group_ids(self) -> list[int]:
        """Return group_ids for all currently active groups."""
        async with db.get_connection(self._db_path) as conn:
            return await group_repo.get_all_active_group_ids(conn)
