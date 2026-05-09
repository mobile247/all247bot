"""
MemberService — manages the member registry.
Handles passive discovery, admin sync, and lifecycle transitions.
Bots are ALWAYS excluded from the registry.
"""

import logging

from telegram import Bot, User

logger = logging.getLogger(__name__)


class MemberService:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def discover_member(self, group_id: int, user: User) -> None:
        """
        Upsert a member discovered from a message event.
        MUST skip any user where user.is_bot is True.
        Logs at DEBUG level only (group_id, user_id, timestamp).
        Message content is never passed to or stored by this method.
        """
        raise NotImplementedError

    async def mark_left(self, group_id: int, user_id: int) -> None:
        """Set member is_active=0 when they leave or are kicked."""
        raise NotImplementedError

    async def mark_rejoined(self, group_id: int, user_id: int) -> None:
        """Set member is_active=1 and update last_seen_at when they rejoin."""
        raise NotImplementedError

    async def sync_admins(self, group_id: int, bot: Bot) -> int:
        """
        Call getChatAdministrators and upsert all non-bot admins into the registry.
        Returns count of admins synced.
        """
        raise NotImplementedError

    async def get_mentionable_members(self, group_id: int) -> list[dict]:
        """
        Return active members eligible for /all mention.
        Ordered alphabetically by display_name (COLLATE NOCASE).
        Returns list of dicts with keys: user_id, display_name, username.
        """
        raise NotImplementedError

    async def prune_stale_if_configured(self, group_id: int, days: int) -> int:
        """
        If days > 0, set is_active=0 for members with no last_seen_at activity
        beyond the threshold. No-op when days=0 (default/disabled).
        Returns count of members marked inactive.
        Called on bot startup for each active group.
        """
        raise NotImplementedError
