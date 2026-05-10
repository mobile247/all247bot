"""
Integration tests: /setup → /all full pipeline.

Tests GroupService + MemberService + MentionService together
against a real SQLite DB. Telegram Bot API calls are mocked.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import User

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService
from bot.services.mention_service import MentionService

pytestmark = pytest.mark.asyncio

GROUP_ID = -100123456
ADMIN_USER_ID = 1001


def _make_user(user_id: int, full_name: str, username: str | None = None, is_bot: bool = False) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.full_name = full_name
    user.username = username
    user.is_bot = is_bot
    return user


async def test_group_inactive_before_setup(db_path):
    group_svc = GroupService(db_path)
    assert await group_svc.is_active(GROUP_ID) is False


async def test_setup_activates_group(db_path):
    group_svc = GroupService(db_path)
    result = await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)
    assert result is True
    assert await group_svc.is_active(GROUP_ID) is True


async def test_setup_twice_returns_false(db_path):
    group_svc = GroupService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)
    result = await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)
    assert result is False


async def test_all_flow_mentions_members(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    mention_svc = MentionService()

    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)

    alice = _make_user(1002, "Alice", "alice")
    bob = _make_user(1003, "Bob", None)
    await member_svc.discover_member(GROUP_ID, alice)
    await member_svc.discover_member(GROUP_ID, bob)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    cfg = await group_svc.get_config(GROUP_ID)
    mention_strings = mention_svc.build_mention_strings(members, cfg["mention_mode"])
    batches = mention_svc.batch_mentions(mention_strings)

    assert len(batches) == 1
    assert "Alice" in batches[0]
    assert "Bob" in batches[0]


async def test_sender_excluded_from_mention_output(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    mention_svc = MentionService()

    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)

    sender = _make_user(ADMIN_USER_ID, "Admin", "admin")
    alice = _make_user(1002, "Alice", "alice")
    await member_svc.discover_member(GROUP_ID, sender)
    await member_svc.discover_member(GROUP_ID, alice)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    members = [m for m in members if m["user_id"] != ADMIN_USER_ID]

    assert len(members) == 1
    assert members[0]["user_id"] == 1002
    assert all(m["user_id"] != ADMIN_USER_ID for m in members)


async def test_bot_user_never_in_registry(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)

    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)

    bot_user = _make_user(9999, "SomeBot", "somebot", is_bot=True)
    human = _make_user(1002, "Alice", "alice")
    await member_svc.discover_member(GROUP_ID, bot_user)
    await member_svc.discover_member(GROUP_ID, human)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert all(m["user_id"] != 9999 for m in members)
    assert len(members) == 1


async def test_deactivate_stops_group(db_path):
    group_svc = GroupService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)
    await group_svc.deactivate(GROUP_ID, deactivated_by=ADMIN_USER_ID)
    assert await group_svc.is_active(GROUP_ID) is False


async def test_sync_admins_skips_bots(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)

    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)

    human_admin = _make_user(1001, "AdminHuman", "adminhuman")
    bot_admin = _make_user(9000, "BotAdmin", "botadmin", is_bot=True)

    mock_cm_human = MagicMock()
    mock_cm_human.user = human_admin
    mock_cm_bot = MagicMock()
    mock_cm_bot.user = bot_admin

    mock_bot = MagicMock()
    mock_bot.get_chat_administrators = AsyncMock(return_value=[mock_cm_human, mock_cm_bot])

    count = await member_svc.sync_admins(GROUP_ID, mock_bot)

    assert count == 1
    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert len(members) == 1
    assert members[0]["user_id"] == 1001


async def test_no_members_when_only_sender_known(db_path):
    """After filtering sender, empty list is returned if they're the only member."""
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)

    await group_svc.activate(GROUP_ID, activated_by=ADMIN_USER_ID)

    sender = _make_user(ADMIN_USER_ID, "Admin", "admin")
    await member_svc.discover_member(GROUP_ID, sender)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    members = [m for m in members if m["user_id"] != ADMIN_USER_ID]

    assert members == []
