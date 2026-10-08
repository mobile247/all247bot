"""
Unit tests for event handlers — member leave/join tracking.
"""

from unittest.mock import MagicMock

import pytest

from bot.handlers.event_handlers import (
    chat_member_handler,
    left_chat_member_handler,
    new_chat_members_handler,
)
from bot.services.group_service import GroupService
from bot.services.member_service import MemberService

pytestmark = pytest.mark.asyncio

GROUP_ID = -100


def _make_user(user_id: int, full_name: str, is_bot: bool = False):
    user = MagicMock()
    user.id = user_id
    user.full_name = full_name
    user.username = None
    user.is_bot = is_bot
    return user


def _make_context(db_path):
    context = MagicMock()
    context.bot_data = {
        "group_service": GroupService(db_path),
        "member_service": MemberService(db_path),
    }
    return context


def _service_message_update(left=None, new=None):
    update = MagicMock()
    update.message.chat.id = GROUP_ID
    update.message.left_chat_member = left
    update.message.new_chat_members = new or []
    return update


def _chat_member_update(user, status, is_member=True):
    update = MagicMock()
    update.chat_member.chat.id = GROUP_ID
    update.chat_member.new_chat_member.user = user
    update.chat_member.new_chat_member.status = status
    update.chat_member.new_chat_member.is_member = is_member
    return update


async def _setup(db_path, *users):
    await GroupService(db_path).activate(GROUP_ID, activated_by=1)
    svc = MemberService(db_path)
    for u in users:
        await svc.discover_member(GROUP_ID, u)
    return svc


async def _mentionable_ids(svc):
    return [m["user_id"] for m in await svc.get_mentionable_members(GROUP_ID)]


async def test_left_chat_member_marks_inactive(db_path):
    alice, bob = _make_user(1, "Alice"), _make_user(2, "Bob")
    svc = await _setup(db_path, alice, bob)

    await left_chat_member_handler(_service_message_update(left=bob), _make_context(db_path))

    assert await _mentionable_ids(svc) == [1]


async def test_new_chat_members_reactivates_removed_member(db_path):
    alice = _make_user(1, "Alice")
    svc = await _setup(db_path, alice)
    await svc.mark_left(GROUP_ID, 1)

    await new_chat_members_handler(_service_message_update(new=[alice]), _make_context(db_path))

    assert await _mentionable_ids(svc) == [1]


async def test_new_chat_members_skips_bots(db_path):
    svc = await _setup(db_path)
    bot_user = _make_user(9, "SomeBot", is_bot=True)

    await new_chat_members_handler(_service_message_update(new=[bot_user]), _make_context(db_path))

    assert await _mentionable_ids(svc) == []


async def test_new_chat_members_ignored_in_inactive_group(db_path):
    svc = MemberService(db_path)

    await new_chat_members_handler(
        _service_message_update(new=[_make_user(1, "Alice")]), _make_context(db_path)
    )

    assert await _mentionable_ids(svc) == []


@pytest.mark.parametrize("status", ["left", "kicked"])
async def test_chat_member_leave_statuses_mark_inactive(db_path, status):
    alice = _make_user(1, "Alice")
    svc = await _setup(db_path, alice)

    await chat_member_handler(_chat_member_update(alice, status), _make_context(db_path))

    assert await _mentionable_ids(svc) == []


async def test_chat_member_restricted_not_member_marks_inactive(db_path):
    alice = _make_user(1, "Alice")
    svc = await _setup(db_path, alice)

    await chat_member_handler(
        _chat_member_update(alice, "restricted", is_member=False), _make_context(db_path)
    )

    assert await _mentionable_ids(svc) == []


async def test_chat_member_restricted_still_member_stays_active(db_path):
    alice = _make_user(1, "Alice")
    svc = await _setup(db_path, alice)

    await chat_member_handler(
        _chat_member_update(alice, "restricted", is_member=True), _make_context(db_path)
    )

    assert await _mentionable_ids(svc) == [1]
