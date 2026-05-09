"""
Event handlers — respond to non-command Telegram updates.
Handles: passive member discovery, join/leave events, bot-added-to-group, bot-removed-from-group.

Privacy guarantee: message content is discarded immediately after metadata extraction.
Only user_id, display_name, username are retained. Nothing else.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Passive member discovery on any message in an active group.
    Extracts: user_id, display_name, username from message.from_user.
    Skips bots (is_bot=True). Skips inactive groups.
    Message content is NEVER read, stored, or logged.
    Edited messages are ignored (not registered as a handler).
    """
    raise NotImplementedError


async def chat_member_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Track member join/leave/kick events via chat_member updates.
    - status -> 'left' or 'kicked': set is_active=0
    - status -> 'member' or 'administrator' (rejoin): set is_active=1
    Skips bots.
    """
    raise NotImplementedError


async def bot_added_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Fires when this bot is added to a group.
    Logs the event (group_id, timestamp). Takes no further action.
    The group remains inactive until /setup is run by an admin.
    """
    raise NotImplementedError


async def bot_removed_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Fires when this bot is removed or kicked from a group.
    Automatically deactivates the group record (set is_active=0).
    Logs group_id, timestamp. No manual /deactivate required.
    """
    raise NotImplementedError
