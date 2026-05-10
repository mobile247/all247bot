"""
Unit tests for RateLimitService.
"""

import pytest

from bot.repository.db import get_connection
from bot.services.rate_limit_service import MIN_INTER_INVOCATION_SECONDS, RateLimitService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# check_cooldown
# ---------------------------------------------------------------------------

async def test_check_cooldown_allows_when_no_prior_entry(db_path):
    svc = RateLimitService(db_path)
    allowed, remaining = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed is True
    assert remaining == 0


async def test_check_cooldown_allows_after_cooldown_elapsed(db_path):
    svc = RateLimitService(db_path)
    # Insert an old entry (well beyond any cooldown)
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-120 seconds'))",
            (-100,),
        )
        await conn.commit()

    allowed, remaining = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed is True
    assert remaining == 0


async def test_check_cooldown_denies_within_cooldown(db_path):
    svc = RateLimitService(db_path)
    # Insert entry 5 seconds ago; cooldown=60
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-5 seconds'))",
            (-100,),
        )
        await conn.commit()

    allowed, remaining = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed is False
    assert remaining > 0
    assert remaining <= 60


async def test_check_cooldown_enforces_minimum_floor(db_path):
    """Even with cooldown_seconds=0, the 3s floor applies."""
    svc = RateLimitService(db_path)
    # Entry just now (0 seconds ago)
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now'))",
            (-100,),
        )
        await conn.commit()

    allowed, remaining = await svc.check_cooldown(-100, cooldown_seconds=0)
    # Should be denied — 0s elapsed < 3s floor
    assert allowed is False
    assert remaining <= MIN_INTER_INVOCATION_SECONDS


async def test_check_cooldown_uses_most_recent_entry(db_path):
    """Cooldown measured from the most recent entry, not the oldest."""
    svc = RateLimitService(db_path)
    async with get_connection(db_path) as conn:
        # Old entry: 200s ago (would allow)
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-200 seconds'))",
            (-100,),
        )
        # Recent entry: 5s ago (should deny with 60s cooldown)
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-5 seconds'))",
            (-100,),
        )
        await conn.commit()

    allowed, _ = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed is False


async def test_check_cooldown_isolated_per_group(db_path):
    """Cooldown for group A does not affect group B."""
    svc = RateLimitService(db_path)
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now'))",
            (-100,),
        )
        await conn.commit()

    allowed, _ = await svc.check_cooldown(-200, cooldown_seconds=60)
    assert allowed is True


# ---------------------------------------------------------------------------
# record_invocation
# ---------------------------------------------------------------------------

async def test_record_invocation_writes_group_id(db_path):
    svc = RateLimitService(db_path)
    await svc.record_invocation(-100, user_id=42)

    async with get_connection(db_path) as conn:
        async with conn.execute(
            "SELECT group_id FROM rate_limit_log WHERE group_id = ?", (-100,)
        ) as cur:
            row = await cur.fetchone()

    assert row is not None
    assert row["group_id"] == -100


async def test_record_invocation_does_not_store_user_id(db_path):
    """rate_limit_log has no triggered_by column — user_id must NOT be persisted."""
    svc = RateLimitService(db_path)
    await svc.record_invocation(-100, user_id=99)

    async with get_connection(db_path) as conn:
        async with conn.execute("PRAGMA table_info(rate_limit_log)") as cur:
            columns = [row["name"] for row in await cur.fetchall()]

    assert "triggered_by" not in columns
    assert "user_id" not in columns


async def test_record_invocation_affects_subsequent_cooldown_check(db_path):
    svc = RateLimitService(db_path)
    allowed_before, _ = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed_before is True

    await svc.record_invocation(-100, user_id=1)

    allowed_after, _ = await svc.check_cooldown(-100, cooldown_seconds=60)
    assert allowed_after is False


# ---------------------------------------------------------------------------
# purge_old_entries
# ---------------------------------------------------------------------------

async def test_purge_old_entries_removes_old_rows(db_path):
    svc = RateLimitService(db_path, purge_days=7)
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-10 days'))",
            (-100,),
        )
        await conn.commit()

    deleted = await svc.purge_old_entries()
    assert deleted == 1

    async with get_connection(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM rate_limit_log") as cur:
            count = (await cur.fetchone())[0]
    assert count == 0


async def test_purge_old_entries_keeps_recent_rows(db_path):
    svc = RateLimitService(db_path, purge_days=7)
    async with get_connection(db_path) as conn:
        await conn.execute(
            "INSERT INTO rate_limit_log (group_id, triggered_at) VALUES (?, datetime('now', '-3 days'))",
            (-100,),
        )
        await conn.commit()

    deleted = await svc.purge_old_entries()
    assert deleted == 0

    async with get_connection(db_path) as conn:
        async with conn.execute("SELECT COUNT(*) FROM rate_limit_log") as cur:
            count = (await cur.fetchone())[0]
    assert count == 1


async def test_purge_old_entries_returns_zero_when_empty(db_path):
    svc = RateLimitService(db_path, purge_days=7)
    deleted = await svc.purge_old_entries()
    assert deleted == 0
