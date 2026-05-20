"""
Event handlers — respond to non-command Telegram updates.
Handles: passive member discovery, join/leave events, bot-added-to-group, bot-removed-from-group.

Privacy guarantee: message content is discarded immediately after metadata extraction.
Only user_id, display_name, username are retained. Nothing else.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService
from bot.utils.telegram_helpers import invalidate_admin_cache

logger = logging.getLogger(__name__)

_ACTIVE_MEMBER_STATUSES = frozenset({"member", "administrator", "creator", "restricted"})
_INACTIVE_MEMBER_STATUSES = frozenset({"left", "kicked"})


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Passive member discovery on any message in an active group.
    Extracts: user_id, display_name, username from message.from_user.
    Skips bots (is_bot=True). Skips inactive groups.
    Message content is NEVER read, stored, or logged.
    Edited messages are ignored (not registered as a handler).
    """
    user = update.effective_user
    chat = update.effective_chat

    if user is None or user.is_bot:
        return

    group_svc: GroupService = context.bot_data["group_service"]
    if not await group_svc.is_active(chat.id):
        return

    member_svc: MemberService = context.bot_data["member_service"]
    await member_svc.discover_member(chat.id, user)


async def chat_member_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Track member join/leave/kick events via chat_member updates.
    - status -> 'left' or 'kicked': set is_active=0
    - status -> 'member'/'administrator'/'creator'/'restricted': upsert + set is_active=1
    Skips bots.
    """
    member_update = update.chat_member
    if member_update is None:
        return

    chat = member_update.chat
    new_member = member_update.new_chat_member
    user = new_member.user

    if user.is_bot:
        return

    # Membership changed — admin list may have changed, evict cache
    invalidate_admin_cache(chat.id)

    member_svc: MemberService = context.bot_data["member_service"]

    if new_member.status in _ACTIVE_MEMBER_STATUSES:
        # discover_member upserts with latest display name and sets is_active=1
        await member_svc.discover_member(chat.id, user)
    elif new_member.status in _INACTIVE_MEMBER_STATUSES:
        await member_svc.mark_left(chat.id, user.id)


async def bot_added_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Fires when this bot is added to a group.
    Stores the group title for later identification (e.g. /migrate listing).
    The group remains inactive until /setup is run by an admin.
    """
    chat = update.effective_chat
    group_svc: GroupService = context.bot_data["group_service"]
    await group_svc.update_title(chat.id, chat.title)
    logger.info("Bot added to group: group_id=%d", chat.id)


async def bot_removed_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Fires when this bot is removed or kicked from a group.
    Automatically deactivates the group record (set is_active=0).
    Logs group_id, timestamp. No manual /deactivate required.
    """
    chat = update.effective_chat
    group_svc: GroupService = context.bot_data["group_service"]
    # deactivated_by=0: sentinel for bot-initiated deactivation (no human user_id)
    await group_svc.deactivate(chat.id, 0)
    logger.info("Bot removed from group — auto-deactivated: group_id=%d", chat.id)


async def group_migration_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Fires when a regular group is converted to a supergroup.
    Telegram sends a service message in the old chat with migrate_to_chat_id set.
    Migrates all DB records (group config, members, rate limits) to the new chat ID.
    """
    msg = update.message
    if msg is None or not msg.migrate_to_chat_id:
        return

    old_id = msg.chat.id
    new_id = msg.migrate_to_chat_id

    group_svc: GroupService = context.bot_data["group_service"]
    migrated = await group_svc.migrate(old_id, new_id)
    # Refresh title under the new ID (chat.title is available in the migration message)
    await group_svc.update_title(new_id, msg.chat.title)
    if not migrated:
        logger.warning(
            "Group migration skipped (already migrated or unknown group): "
            "old_id=%d new_id=%d",
            old_id,
            new_id,
        )


async def my_chat_member_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Routes MY_CHAT_MEMBER updates (bot's own status changes) to
    bot_added_handler or bot_removed_handler based on new status.
    """
    member_update = update.my_chat_member
    if member_update is None:
        return

    new_status = member_update.new_chat_member.status
    if new_status in _ACTIVE_MEMBER_STATUSES:
        await bot_added_handler(update, context)
    elif new_status in _INACTIVE_MEMBER_STATUSES:
        await bot_removed_handler(update, context)
