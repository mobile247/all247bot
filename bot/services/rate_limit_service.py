"""
RateLimitService — cooldown enforcement and rate limit log management.
Hard floor: 3 seconds minimum between /all invocations per group regardless of config.
"""

import logging
import math

from bot.repository import db

logger = logging.getLogger(__name__)

# Hard floor — not operator-configurable
MIN_INTER_INVOCATION_SECONDS = 3


class RateLimitService:
    def __init__(self, db_path: str, purge_days: int = 7) -> None:
        self._db_path = db_path
        self._purge_days = purge_days

    async def check_cooldown(
        self, group_id: int, cooldown_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if /all is allowed for this group.
        Returns (allowed: bool, seconds_remaining: int).
        Applies the hard 3-second floor regardless of configured cooldown.
        """
        effective = max(MIN_INTER_INVOCATION_SECONDS, cooldown_seconds)
        async with db.get_connection(self._db_path) as conn:
            async with conn.execute(
                """
                SELECT CAST(
                    (julianday('now') - julianday(triggered_at)) * 86400
                AS INTEGER) AS elapsed_secs
                FROM rate_limit_log
                WHERE group_id = ?
                ORDER BY triggered_at DESC
                LIMIT 1
                """,
                (group_id,),
            ) as cur:
                row = await cur.fetchone()

        if row is None:
            return True, 0

        elapsed = row[0]
        if elapsed >= effective:
            return True, 0

        remaining = math.ceil(effective - elapsed)
        return False, remaining

    async def record_invocation(self, group_id: int, user_id: int) -> None:
        """
        Write a rate_limit_log entry: group_id + timestamp only.
        user_id is accepted for stdout logging purposes but NOT persisted to DB.
        Cooldown is per-group; per-user tracking would be over-collection.
        """
        async with db.get_connection(self._db_path) as conn:
            await conn.execute(
                "INSERT INTO rate_limit_log (group_id) VALUES (?)",
                (group_id,),
            )
            await conn.commit()
        logger.debug("Invocation recorded: group_id=%d user_id=%d", group_id, user_id)

    async def purge_old_entries(self) -> int:
        """
        Delete rate_limit_log entries older than purge_days.
        Returns number of rows deleted. Called on bot startup.
        """
        async with db.get_connection(self._db_path) as conn:
            cur = await conn.execute(
                "DELETE FROM rate_limit_log WHERE triggered_at < datetime('now', ?)",
                (f"-{self._purge_days} days",),
            )
            await conn.commit()
        deleted = cur.rowcount
        logger.info("Rate limit log purged: deleted=%d", deleted)
        return deleted
