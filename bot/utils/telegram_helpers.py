"""
Telegram helper utilities — thin wrappers around Telegram API calls.
"""

import html
import logging
import time

from telegram import Bot

logger = logging.getLogger(__name__)

# Admin list cache: chat_id -> (expiry_monotonic, admin_list)
# Avoids repeated getChatAdministrators calls within the TTL window.
_ADMIN_CACHE_TTL = 60  # seconds
_admin_cache: dict[int, tuple[float, list]] = {}


async def get_chat_admins(bot: Bot, chat_id: int) -> list:
    """
    Return the admin ChatMember list for chat_id, cached for _ADMIN_CACHE_TTL seconds.
    On cache miss or expiry, fetches from Telegram API.
    """
    now = time.monotonic()
    cached = _admin_cache.get(chat_id)
    if cached is not None and now < cached[0]:
        return cached[1]
    admins = await bot.get_chat_administrators(chat_id)
    _admin_cache[chat_id] = (now + _ADMIN_CACHE_TTL, admins)
    return admins


def invalidate_admin_cache(chat_id: int) -> None:
    """Evict cached admin list for a group. Call on any membership status change."""
    _admin_cache.pop(chat_id, None)


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Return True if user_id is an administrator or creator of chat_id.
    Uses cached getChatAdministrators result where possible.
    """
    admins = await get_chat_admins(bot, chat_id)
    return any(member.user.id == user_id for member in admins)


def html_mention(user_id: int, display_name: str) -> str:
    """
    Build an HTML inline mention: <a href="tg://user?id=USER_ID">Display Name</a>
    display_name is HTML-escaped via html.escape().
    """
    return f'<a href="tg://user?id={user_id}">{html.escape(display_name)}</a>'


def username_mention(username: str | None, user_id: int, display_name: str) -> str:
    """
    Return @username if available, otherwise fall back to html_mention().
    """
    if username:
        return f"@{username}"
    return html_mention(user_id, display_name)
