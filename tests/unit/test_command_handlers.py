"""
Unit tests for command handlers — admin-only command behavior.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers import command_handlers
from bot.services.group_service import GroupService
from bot.services.member_service import MemberService

pytestmark = pytest.mark.asyncio

GROUP_ID = -100


def _make_update(user_id: int):
    update = MagicMock()
    update.effective_chat.id = GROUP_ID
    update.effective_chat.type = "supergroup"
    update.effective_user.id = user_id
    update.effective_message.reply_text = AsyncMock()
    return update


async def _make_context(db_path):
    await GroupService(db_path).activate(GROUP_ID, activated_by=1)
    context = MagicMock()
    context.bot_data = {
        "group_service": GroupService(db_path),
        "member_service": MemberService(db_path),
    }
    return context


@pytest.mark.parametrize(
    "handler",
    [
        command_handlers.prunemembers_handler,
        command_handlers.syncmembers_handler,
        command_handlers.members_handler,
        command_handlers.deactivate_handler,
    ],
)
async def test_admin_command_from_non_admin_is_silent(db_path, monkeypatch, handler):
    monkeypatch.setattr(command_handlers, "is_group_admin", AsyncMock(return_value=False))
    update = _make_update(user_id=42)
    context = await _make_context(db_path)

    await handler(update, context)

    update.effective_message.reply_text.assert_not_awaited()


async def test_prunemembers_from_admin_replies_with_result(db_path, monkeypatch):
    monkeypatch.setattr(command_handlers, "is_group_admin", AsyncMock(return_value=True))
    update = _make_update(user_id=1)
    context = await _make_context(db_path)
    context.bot_data["member_service"].prune_departed = AsyncMock(return_value=(3, 0))

    await command_handlers.prunemembers_handler(update, context)

    update.effective_message.reply_text.assert_awaited_once()
    assert "Removed 3" in update.effective_message.reply_text.await_args.args[0]
