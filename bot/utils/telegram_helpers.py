"""
Telegram helper utilities — thin wrappers around Telegram API calls.
"""

import html
import logging

from telegram import Bot

logger = logging.getLogger(__name__)


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Return True if user_id is an administrator or creator of chat_id.
    Uses getChatAdministrators API call.
    """
    raise NotImplementedError


def html_mention(user_id: int, display_name: str) -> str:
    """
    Build an HTML inline mention: <a href="tg://user?id=USER_ID">Display Name</a>
    display_name is HTML-escaped via html.escape().
    """
    raise NotImplementedError


def username_mention(username: str | None, user_id: int, display_name: str) -> str:
    """
    Return @username if available, otherwise fall back to html_mention().
    """
    raise NotImplementedError
