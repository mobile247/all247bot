"""
Integration tests: passive member discovery pipeline.

Verifies that members are correctly upserted, updated, deactivated,
and restored through the MemberService lifecycle methods.
"""

from unittest.mock import MagicMock

import pytest
from telegram import User

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService

pytestmark = pytest.mark.asyncio

GROUP_ID = -100999888


def _make_user(user_id: int, full_name: str, username: str | None = None, is_bot: bool = False) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.full_name = full_name
    user.username = username
    user.is_bot = is_bot
    return user


async def test_discover_adds_member(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Charlie", "charlie")
    await member_svc.discover_member(GROUP_ID, user)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert any(m["user_id"] == 42 for m in members)


async def test_discover_updates_display_name_on_change(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Old Name", "charlie")
    await member_svc.discover_member(GROUP_ID, user)

    user.full_name = "New Name"
    await member_svc.discover_member(GROUP_ID, user)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    member = next(m for m in members if m["user_id"] == 42)
    assert member["display_name"] == "New Name"


async def test_bot_is_silently_skipped(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    bot = _make_user(99, "SpamBot", "spambot", is_bot=True)
    await member_svc.discover_member(GROUP_ID, bot)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert all(m["user_id"] != 99 for m in members)


async def test_mark_left_removes_from_mentionable(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Charlie", "charlie")
    await member_svc.discover_member(GROUP_ID, user)
    await member_svc.mark_left(GROUP_ID, 42)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert all(m["user_id"] != 42 for m in members)


async def test_mark_rejoined_restores_member(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Charlie", "charlie")
    await member_svc.discover_member(GROUP_ID, user)
    await member_svc.mark_left(GROUP_ID, 42)
    await member_svc.mark_rejoined(GROUP_ID, 42)

    members = await member_svc.get_mentionable_members(GROUP_ID)
    assert any(m["user_id"] == 42 for m in members)


async def test_members_ordered_alphabetically_case_insensitive(db_path):
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    for uid, name in [(1, "Zara"), (2, "alice"), (3, "Mike")]:
        await member_svc.discover_member(GROUP_ID, _make_user(uid, name))

    members = await member_svc.get_mentionable_members(GROUP_ID)
    names = [m["display_name"] for m in members]
    assert names == sorted(names, key=str.lower)


async def test_multiple_groups_isolated(db_path):
    """Members discovered in group A must not appear in group B."""
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)

    group_a = -100111
    group_b = -100222
    await group_svc.activate(group_a, activated_by=1)
    await group_svc.activate(group_b, activated_by=1)

    user = _make_user(42, "Charlie", "charlie")
    await member_svc.discover_member(group_a, user)

    members_b = await member_svc.get_mentionable_members(group_b)
    assert all(m["user_id"] != 42 for m in members_b)
