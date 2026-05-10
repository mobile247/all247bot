"""
Integration tests: batch send simulation with mock Telegram API.

Verifies mention building, batching, delivery, and hard-limit enforcement
using a real MentionService with a mocked bot.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.mention_service import (
    MAX_BATCHES,
    MAX_MESSAGE_LENGTH,
    MentionService,
)

pytestmark = pytest.mark.asyncio


async def test_send_mentions_uses_html_parse_mode():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("asyncio.sleep", new=AsyncMock()):
        await svc.send_mentions(mock_bot, chat_id=-100, batches=["hello"])

    call_kwargs = mock_bot.send_message.call_args[1]
    assert call_kwargs["parse_mode"] == "HTML"


async def test_send_mentions_sends_all_batches():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("asyncio.sleep", new=AsyncMock()):
        await svc.send_mentions(mock_bot, chat_id=-100, batches=["b1", "b2", "b3"])

    assert mock_bot.send_message.call_count == 3


async def test_send_mentions_first_as_reply():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("asyncio.sleep", new=AsyncMock()):
        await svc.send_mentions(mock_bot, -100, ["b1", "b2"], reply_to_message_id=42)

    first_kwargs = mock_bot.send_message.call_args_list[0][1]
    second_kwargs = mock_bot.send_message.call_args_list[1][1]
    assert first_kwargs.get("reply_to_message_id") == 42
    assert "reply_to_message_id" not in second_kwargs


async def test_max_batches_cap_enforced():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    batches = [f"batch{i}" for i in range(MAX_BATCHES + 5)]
    with patch("asyncio.sleep", new=AsyncMock()):
        await svc.send_mentions(mock_bot, chat_id=-100, batches=batches)

    assert mock_bot.send_message.call_count == MAX_BATCHES


async def test_large_member_list_splits_correctly():
    svc = MentionService()
    # Each member name is long enough to force batching
    members = [
        {"user_id": i, "display_name": f"User {'A' * 60} {i}", "username": None}
        for i in range(100)
    ]
    mention_strings = svc.build_mention_strings(members, "display_name")
    batches = svc.batch_mentions(mention_strings)

    assert len(batches) > 1
    for batch in batches:
        assert len(batch) <= MAX_MESSAGE_LENGTH


async def test_html_escape_applied_to_display_names():
    svc = MentionService()
    members = [{"user_id": 1, "display_name": "A & B <xss>", "username": None}]
    strings = svc.build_mention_strings(members, "display_name")

    assert "&amp;" in strings[0]
    assert "&lt;xss&gt;" in strings[0]
    assert "<xss>" not in strings[0]


async def test_username_mode_uses_at_handle():
    svc = MentionService()
    members = [{"user_id": 1, "display_name": "Alice", "username": "alice"}]
    strings = svc.build_mention_strings(members, "username")
    assert strings[0] == "@alice"


async def test_username_mode_falls_back_to_html_when_no_username():
    svc = MentionService()
    members = [{"user_id": 1, "display_name": "Alice", "username": None}]
    strings = svc.build_mention_strings(members, "username")
    assert 'tg://user?id=1' in strings[0]
    assert "Alice" in strings[0]


async def test_member_cap_raises_value_error():
    svc = MentionService(max_mentionable_members=5)
    mentions = ["@user"] * 6
    with pytest.raises(ValueError, match="exceeds maximum"):
        svc.batch_mentions(mentions)
