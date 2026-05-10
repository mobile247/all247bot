"""
MemberService — manages the member registry.
Handles passive discovery, admin sync, and lifecycle transitions.
Bots are ALWAYS excluded from the registry.
"""

import logging

from telegram import Bot, User

from bot.repository import db, member_repo

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
        if user.is_bot:
            return
        async with db.get_connection(self._db_path) as conn:
            await member_repo.upsert_member(
                conn,
                group_id,
                user.id,
                user.full_name,
                user.username,
            )
        logger.debug("Member discovered: group_id=%d user_id=%d", group_id, user.id)

    async def mark_left(self, group_id: int, user_id: int) -> None:
        """Set member is_active=0 when they leave or are kicked."""
        async with db.get_connection(self._db_path) as conn:
            await member_repo.set_member_active(conn, group_id, user_id, 0)
        logger.debug("Member left: group_id=%d user_id=%d", group_id, user_id)

    async def mark_rejoined(self, group_id: int, user_id: int) -> None:
        """Set member is_active=1 and update last_seen_at when they rejoin."""
        async with db.get_connection(self._db_path) as conn:
            await member_repo.set_member_active(conn, group_id, user_id, 1)
        logger.debug("Member rejoined: group_id=%d user_id=%d", group_id, user_id)

    async def sync_admins_from_list(self, group_id: int, admins: list) -> int:
        """
        Upsert all non-bot admins from a pre-fetched admin list into the registry.
        Use this when the admin list was already fetched (avoids duplicate API call).
        Returns count of admins synced.
        """
        count = 0
        async with db.get_connection(self._db_path) as conn:
            for member in admins:
                user = member.user
                if user.is_bot:
                    continue
                await member_repo.upsert_member(
                    conn,
                    group_id,
                    user.id,
                    user.full_name,
                    user.username,
                )
                count += 1
        logger.info("Admins synced: group_id=%d count=%d", group_id, count)
        return count

    async def sync_admins(self, group_id: int, bot: Bot) -> int:
        """
        Fetch current admins from Telegram and upsert all non-bot admins into the registry.
        Returns count of admins synced.
        """
        admins = await bot.get_chat_administrators(group_id)
        return await self.sync_admins_from_list(group_id, admins)

    async def get_mentionable_members(self, group_id: int) -> list[dict]:
        """
        Return active members eligible for /all mention.
        Ordered alphabetically by display_name (COLLATE NOCASE).
        Returns list of dicts with keys: user_id, display_name, username.
        """
        async with db.get_connection(self._db_path) as conn:
            rows = await member_repo.get_active_members(conn, group_id)
        return [
            {
                "user_id": row["user_id"],
                "display_name": row["display_name"],
                "username": row["username"],
            }
            for row in rows
        ]

    async def purge_members(self, group_id: int) -> int:
        """
        Hard-delete ALL member records for a group.
        Called when the bot leaves a group via /leave.
        Returns count of deleted rows.
        """
        async with db.get_connection(self._db_path) as conn:
            count = await member_repo.delete_group_members(conn, group_id)
        logger.info("Members purged: group_id=%d count=%d", group_id, count)
        return count

    async def prune_stale_if_configured(self, group_id: int, days: int) -> int:
        """
        If days > 0, set is_active=0 for members with no last_seen_at activity
        beyond the threshold. No-op when days=0 (default/disabled).
        Returns count of members marked inactive.
        Called on bot startup for each active group.
        """
        if days <= 0:
            return 0
        async with db.get_connection(self._db_path) as conn:
            count = await member_repo.prune_stale_members(conn, group_id, days)
        if count:
            logger.info(
                "Stale members pruned: group_id=%d count=%d days=%d",
                group_id,
                count,
                days,
            )
        return count
