"""
Unit tests for MemberService.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService

pytestmark = pytest.mark.asyncio


def _make_user(user_id: int, full_name: str, username: str | None = None, is_bot: bool = False):
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.username = username
    user.is_bot = is_bot
    return user


async def _setup_group(db_path, group_id=-100):
    svc = GroupService(db_path)
    await svc.activate(group_id, activated_by=1)


async def test_discover_member_upserts(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice", "alice")
    await svc.discover_member(-100, user)
    members = await svc.get_mentionable_members(-100)
    assert len(members) == 1
    assert members[0]["user_id"] == 42
    assert members[0]["display_name"] == "Alice"
    assert members[0]["username"] == "alice"


async def test_discover_member_skips_bots(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    bot_user = _make_user(99, "SomeBot", is_bot=True)
    await svc.discover_member(-100, bot_user)
    members = await svc.get_mentionable_members(-100)
    assert members == []


async def test_discover_member_updates_on_second_call(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)
    user2 = _make_user(42, "Alice Renamed", "alice_new")
    await svc.discover_member(-100, user2)
    members = await svc.get_mentionable_members(-100)
    assert len(members) == 1
    assert members[0]["display_name"] == "Alice Renamed"
    assert members[0]["username"] == "alice_new"


async def test_mark_left_sets_inactive(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)
    await svc.mark_left(-100, 42)
    members = await svc.get_mentionable_members(-100)
    assert members == []


async def test_mark_rejoined_reactivates(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)
    await svc.mark_left(-100, 42)
    await svc.mark_rejoined(-100, 42)
    members = await svc.get_mentionable_members(-100)
    assert len(members) == 1
    assert members[0]["user_id"] == 42


async def test_get_mentionable_members_alphabetical(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    for uid, name in [(1, "Zelda"), (2, "alice"), (3, "Bob")]:
        await svc.discover_member(-100, _make_user(uid, name))
    members = await svc.get_mentionable_members(-100)
    names = [m["display_name"] for m in members]
    assert names == ["alice", "Bob", "Zelda"]


async def test_sync_admins_skips_bots(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)

    human_admin = MagicMock()
    human_admin.user = _make_user(10, "AdminHuman", "admin_h")

    bot_admin = MagicMock()
    bot_admin.user = _make_user(99, "BotAdmin", is_bot=True)

    mock_bot = MagicMock()
    mock_bot.get_chat_administrators = AsyncMock(return_value=[human_admin, bot_admin])

    count = await svc.sync_admins(-100, mock_bot)
    assert count == 1
    members = await svc.get_mentionable_members(-100)
    assert len(members) == 1
    assert members[0]["user_id"] == 10


async def test_sync_admins_returns_count(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)

    admins = [MagicMock() for _ in range(3)]
    for i, m in enumerate(admins):
        m.user = _make_user(i + 1, f"Admin{i + 1}")

    mock_bot = MagicMock()
    mock_bot.get_chat_administrators = AsyncMock(return_value=admins)

    count = await svc.sync_admins(-100, mock_bot)
    assert count == 3


async def test_prune_stale_if_configured_noop_when_zero(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)
    pruned = await svc.prune_stale_if_configured(-100, days=0)
    assert pruned == 0
    assert len(await svc.get_mentionable_members(-100)) == 1


async def test_prune_stale_if_configured_prunes_old_members(db_path):
    """Members with last_seen_at far in the past get pruned."""
    import aiosqlite
    from bot.repository.db import get_connection

    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)

    # Backdate last_seen_at to 10 days ago
    async with get_connection(db_path) as conn:
        await conn.execute(
            "UPDATE members SET last_seen_at = datetime('now', '-10 days') WHERE user_id = 42"
        )
        await conn.commit()

    pruned = await svc.prune_stale_if_configured(-100, days=7)
    assert pruned == 1
    assert await svc.get_mentionable_members(-100) == []


async def test_prune_stale_if_configured_keeps_recent_members(db_path):
    await _setup_group(db_path)
    svc = MemberService(db_path)
    user = _make_user(42, "Alice")
    await svc.discover_member(-100, user)
    pruned = await svc.prune_stale_if_configured(-100, days=7)
    assert pruned == 0
    assert len(await svc.get_mentionable_members(-100)) == 1
