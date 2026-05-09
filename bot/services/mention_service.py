"""
MentionService — builds and delivers mention messages.
Enforces hard limits: MAX_MENTIONABLE_MEMBERS, MAX_BATCHES, retry logic.
Uses HTML parse mode exclusively. All display names are HTML-escaped.
"""

import logging

from telegram import Bot
from telegram.error import RetryAfter, TelegramError

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
        raise NotImplementedError

    def batch_mentions(self, mention_strings: list[str]) -> list[str]:
        """
        Greedily pack mention strings into messages up to MAX_MESSAGE_LENGTH.
        Returns list of message strings ready to send.
        Raises ValueError if member count exceeds self._max_members.
        """
        raise NotImplementedError

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
        raise NotImplementedError

    async def send_with_retry(
        self, bot: Bot, chat_id: int, text: str, max_retries: int = MAX_RETRY_ATTEMPTS, **kwargs
    ) -> None:
        """
        Send a message with RetryAfter handling.
        Logs error type only — no message content in logs.
        """
        raise NotImplementedError
