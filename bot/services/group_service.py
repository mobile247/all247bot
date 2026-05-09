"""
GroupService — business logic for group activation and configuration.
Wraps group_repo with validation and logging. Config changes are logged
(setting name, old value, new value, changed_by) but never include message content.
"""

import logging

import aiosqlite

logger = logging.getLogger(__name__)

VALID_CONFIG_KEYS = {"cooldown", "delete_trigger", "mention_mode", "restrict_all_to_admins"}

VALID_CONFIG_VALUES = {
    "mention_mode": {"display_name", "username"},
    "delete_trigger": {"on", "off"},
    "restrict_all_to_admins": {"on", "off"},
}


class GroupService:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def activate(self, group_id: int, activated_by: int) -> bool:
        """
        Activate the bot for a group. Returns False if already active.
        Logs group_id, activated_by, timestamp.
        """
        raise NotImplementedError

    async def deactivate(self, group_id: int, deactivated_by: int) -> None:
        """Deactivate the bot for a group. Logs group_id, deactivated_by, timestamp."""
        raise NotImplementedError

    async def is_active(self, group_id: int) -> bool:
        """Return True if the group has been activated."""
        raise NotImplementedError

    async def get_config(self, group_id: int) -> dict:
        """Return current group configuration as a dict."""
        raise NotImplementedError

    async def update_config(
        self, group_id: int, key: str, value: str, changed_by: int
    ) -> None:
        """
        Validate and update a config key. Raises ValueError on invalid key/value.
        Logs setting name, old value, new value, changed_by — no message content.
        """
        raise NotImplementedError
