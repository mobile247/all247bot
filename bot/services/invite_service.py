"""
InviteService — create and validate group registration tokens.
Tokens are used by the /invite deep-link flow so members can DM
the bot to register their user_id without sending a group message.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from bot.repository import db, token_repo

logger = logging.getLogger(__name__)


class InviteService:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def create_invite(self, group_id: int, expiry_hours: int) -> str:
        """
        Generate a URL-safe token for group_id and persist it.
        Returns the token string.
        Logs group_id and expiry; no user data logged.
        """
        token = secrets.token_urlsafe(8)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")
        async with db.get_connection(self._db_path) as conn:
            await token_repo.create_token(conn, token, group_id, expires_at_str)
        logger.info(
            "Invite token created: group_id=%d expiry_hours=%d", group_id, expiry_hours
        )
        return token

    async def validate_token(self, token: str) -> int | None:
        """
        Return group_id if token exists and has not expired, else None.
        Expiry check is done in SQL (datetime comparison).
        """
        async with db.get_connection(self._db_path) as conn:
            row = await token_repo.get_token(conn, token)
        if row is None:
            return None
        return row["group_id"]

    async def purge_expired_tokens(self) -> int:
        """Delete expired tokens. Returns count deleted. Called on startup."""
        async with db.get_connection(self._db_path) as conn:
            count = await token_repo.delete_expired_tokens(conn)
        if count:
            logger.info("Purged %d expired registration token(s)", count)
        return count

    async def delete_tokens_for_group(self, group_id: int) -> None:
        """Delete all tokens for a group. Called on /leave."""
        async with db.get_connection(self._db_path) as conn:
            await token_repo.delete_tokens_for_group(conn, group_id)
