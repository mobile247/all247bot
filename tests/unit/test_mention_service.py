"""
Unit tests for MentionService.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.error import RetryAfter, TelegramError

from bot.services.mention_service import (
    MAX_BATCHES,
    MAX_MESSAGE_LENGTH,
    MentionService,
)


def _members(*args):
    """Build a list of member dicts. Each arg: (user_id, display_name, username)."""
    return [
        {"user_id": uid, "display_name": name, "username": uname}
        for uid, name, uname in args
    ]


# ---------------------------------------------------------------------------
# build_mention_strings
# ---------------------------------------------------------------------------

def test_build_mention_strings_display_name_mode():
    svc = MentionService()
    members = _members((1, "Alice", "alice"), (2, "Bob", None))
    result = svc.build_mention_strings(members, "display_name")
    assert result == [
        '<a href="tg://user?id=1">Alice</a>',
        '<a href="tg://user?id=2">Bob</a>',
    ]


def test_build_mention_strings_username_mode_with_username():
    svc = MentionService()
    members = _members((1, "Alice", "alice"))
    result = svc.build_mention_strings(members, "username")
    assert result == ["@alice"]


def test_build_mention_strings_username_mode_fallback():
    svc = MentionService()
    members = _members((1, "Alice", None))
    result = svc.build_mention_strings(members, "username")
    assert result == ['<a href="tg://user?id=1">Alice</a>']


def test_build_mention_strings_escapes_html():
    svc = MentionService()
    members = _members((1, "A & B <test>", None))
    result = svc.build_mention_strings(members, "display_name")
    assert result == ['<a href="tg://user?id=1">A &amp; B &lt;test&gt;</a>']


def test_build_mention_strings_empty():
    svc = MentionService()
    assert svc.build_mention_strings([], "display_name") == []


# ---------------------------------------------------------------------------
# batch_mentions
# ---------------------------------------------------------------------------

def test_batch_mentions_single_batch():
    svc = MentionService()
    mentions = ['<a href="tg://user?id=1">Alice</a>', '<a href="tg://user?id=2">Bob</a>']
    batches = svc.batch_mentions(mentions)
    assert len(batches) == 1
    assert "Alice" in batches[0]
    assert "Bob" in batches[0]


def test_batch_mentions_splits_on_length():
    svc = MentionService()
    # Each mention ~50 chars; pack enough to force split
    mention = "x" * 100
    mentions = [mention] * 50  # 50 * 100 = 5000 chars > MAX_MESSAGE_LENGTH=4000
    batches = svc.batch_mentions(mentions)
    assert len(batches) >= 2
    for batch in batches:
        assert len(batch) <= MAX_MESSAGE_LENGTH


def test_batch_mentions_raises_on_too_many_members():
    svc = MentionService(max_mentionable_members=5)
    mentions = ["@user"] * 6
    with pytest.raises(ValueError, match="exceeds maximum"):
        svc.batch_mentions(mentions)


def test_batch_mentions_empty():
    svc = MentionService()
    assert svc.batch_mentions([]) == []


def test_batch_mentions_single_oversized_mention():
    """A mention longer than MAX_MESSAGE_LENGTH goes into its own batch."""
    svc = MentionService()
    big = "x" * (MAX_MESSAGE_LENGTH + 10)
    batches = svc.batch_mentions([big])
    assert len(batches) == 1
    assert batches[0] == big


def test_batch_mentions_respects_max_members_boundary():
    svc = MentionService(max_mentionable_members=3)
    mentions = ["@a", "@b", "@c"]
    batches = svc.batch_mentions(mentions)
    assert len(batches) == 1


# ---------------------------------------------------------------------------
# send_mentions
# ---------------------------------------------------------------------------

async def test_send_mentions_sends_all_batches():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    batches = ["batch1", "batch2"]
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.send_mentions(mock_bot, chat_id=-100, batches=batches)

    assert mock_bot.send_message.call_count == 2


async def test_send_mentions_first_batch_as_reply():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.send_mentions(mock_bot, -100, ["hello"], reply_to_message_id=42)

    call_kwargs = mock_bot.send_message.call_args[1]
    assert call_kwargs.get("reply_to_message_id") == 42


async def test_send_mentions_enforces_max_batches():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    batches = [f"batch{i}" for i in range(MAX_BATCHES + 5)]
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.send_mentions(mock_bot, -100, batches)

    assert mock_bot.send_message.call_count == MAX_BATCHES


async def test_send_mentions_no_reply_on_second_batch():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.send_mentions(mock_bot, -100, ["b1", "b2"], reply_to_message_id=99)

    second_call_kwargs = mock_bot.send_message.call_args_list[1][1]
    assert "reply_to_message_id" not in second_call_kwargs


# ---------------------------------------------------------------------------
# send_with_retry
# ---------------------------------------------------------------------------

async def test_send_with_retry_success_first_attempt():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    await svc.send_with_retry(mock_bot, -100, "hello", parse_mode="HTML")
    assert mock_bot.send_message.call_count == 1


async def test_send_with_retry_retries_on_retry_after():
    svc = MentionService()
    mock_bot = MagicMock()
    retry_err = RetryAfter(1)
    mock_bot.send_message = AsyncMock(side_effect=[retry_err, None])

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await svc.send_with_retry(mock_bot, -100, "hello", max_retries=3, parse_mode="HTML")

    assert mock_bot.send_message.call_count == 2


async def test_send_with_retry_raises_after_max_retries():
    svc = MentionService()
    mock_bot = MagicMock()
    retry_err = RetryAfter(1)
    mock_bot.send_message = AsyncMock(side_effect=retry_err)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(RetryAfter):
            await svc.send_with_retry(mock_bot, -100, "hello", max_retries=3, parse_mode="HTML")

    assert mock_bot.send_message.call_count == 3


async def test_send_with_retry_raises_immediately_on_telegram_error():
    svc = MentionService()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(side_effect=TelegramError("forbidden"))

    with pytest.raises(TelegramError):
        await svc.send_with_retry(mock_bot, -100, "hello", max_retries=3, parse_mode="HTML")

    assert mock_bot.send_message.call_count == 1
