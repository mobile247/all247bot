"""
MentionService — builds and delivers mention messages.
Enforces hard limits: MAX_MENTIONABLE_MEMBERS, MAX_BATCHES, retry logic.
Uses HTML parse mode exclusively. All display names are HTML-escaped.
"""

import asyncio
import logging

from telegram import Bot
from telegram.error import RetryAfter, TelegramError

from bot.utils.telegram_helpers import html_mention, username_mention

logger = logging.getLogger(__name__)

# Hard limits — not operator-configurable
MAX_MESSAGE_LENGTH = 4000
BATCH_DELAY_SECONDS = 0.5
MAX_BATCHES = 10
MAX_RETRY_ATTEMPTS = 3
MIN_INTER_INVOCATION_SECONDS = 3
MAX_MENTIONABLE_MEMBERS = 1000  # overridable via env in config


class MentionService:
    def __init__(self, max_mentionable_members: int = MAX_MENTIONABLE_MEMBERS) -> None:
        self._max_members = max_mentionable_members

    def build_mention_strings(
        self, members: list[dict], mention_mode: str
    ) -> list[str]:
        """
        Build a list of individual mention strings for each member.
        mention_mode: 'display_name' -> HTML anchor
                      'username'     -> @username (fallback to HTML anchor)
        All display names are HTML-escaped via html.escape().
        """
        result = []
        for m in members:
            if mention_mode == "username":
                result.append(username_mention(m["username"], m["user_id"], m["display_name"]))
            else:
                result.append(html_mention(m["user_id"], m["display_name"]))
        return result

    def batch_mentions(self, mention_strings: list[str]) -> list[str]:
        """
        Greedily pack mention strings into messages up to MAX_MESSAGE_LENGTH.
        Returns list of message strings ready to send.
        Raises ValueError if member count exceeds self._max_members.
        """
        if len(mention_strings) > self._max_members:
            raise ValueError(
                f"Member count {len(mention_strings)} exceeds maximum {self._max_members}"
            )

        batches = []
        current_parts: list[str] = []
        current_len = 0

        for mention in mention_strings:
            separator_len = 1 if current_parts else 0
            if current_parts and current_len + separator_len + len(mention) > MAX_MESSAGE_LENGTH:
                batches.append(" ".join(current_parts))
                current_parts = [mention]
                current_len = len(mention)
            else:
                current_parts.append(mention)
                current_len += separator_len + len(mention)

        if current_parts:
            batches.append(" ".join(current_parts))

        return batches

    async def send_mentions(
        self,
        bot: Bot,
        chat_id: int,
        batches: list[str],
        reply_to_message_id: int | None = None,
    ) -> None:
        """
        Send batched mention messages. Enforces MAX_BATCHES limit.
        Adds BATCH_DELAY_SECONDS between sends.
        First batch is sent as reply if reply_to_message_id is provided.
        """
        capped = batches[:MAX_BATCHES]
        if len(batches) > MAX_BATCHES:
            logger.warning(
                "Batch count %d exceeds MAX_BATCHES=%d — truncating: chat_id=%d",
                len(batches),
                MAX_BATCHES,
                chat_id,
            )

        for i, batch in enumerate(capped):
            kwargs: dict = {"parse_mode": "HTML"}
            if i == 0 and reply_to_message_id is not None:
                kwargs["reply_to_message_id"] = reply_to_message_id
            await self.send_with_retry(bot, chat_id, batch, **kwargs)
            if i < len(capped) - 1:
                await asyncio.sleep(BATCH_DELAY_SECONDS)

    async def send_with_retry(
        self, bot: Bot, chat_id: int, text: str, max_retries: int = MAX_RETRY_ATTEMPTS, **kwargs
    ) -> None:
        """
        Send a message with RetryAfter handling.
        Logs error type only — no message content in logs.
        """
        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                await bot.send_message(chat_id=chat_id, text=text, **kwargs)
                return
            except RetryAfter as e:
                logger.warning(
                    "RetryAfter: chat_id=%d retry_after=%s attempt=%d",
                    chat_id,
                    e.retry_after,
                    attempt + 1,
                )
                await asyncio.sleep(e.retry_after)
                last_error = e
            except TelegramError as e:
                logger.error(
                    "TelegramError type=%s chat_id=%d attempt=%d",
                    type(e).__name__,
                    chat_id,
                    attempt + 1,
                )
                raise
        raise last_error  # type: ignore[misc]
