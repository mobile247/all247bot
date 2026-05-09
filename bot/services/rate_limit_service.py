"""
RateLimitService — cooldown enforcement and rate limit log management.
Hard floor: 3 seconds minimum between /all invocations per group regardless of config.
"""

import logging

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
        raise NotImplementedError

    async def record_invocation(self, group_id: int, user_id: int) -> None:
        """
        Write a rate_limit_log entry: group_id + timestamp only.
        user_id is accepted for stdout logging purposes but NOT persisted to DB.
        Cooldown is per-group; per-user tracking would be over-collection.
        """
        raise NotImplementedError

    async def purge_old_entries(self) -> int:
        """
        Delete rate_limit_log entries older than purge_days.
        Returns number of rows deleted. Called on bot startup.
        """
        raise NotImplementedError
