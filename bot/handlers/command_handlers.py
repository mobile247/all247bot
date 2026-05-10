"""
Command handlers — respond to Telegram bot commands.
Commands: /setup, /all, /syncmembers, /config, /deactivate

Privacy guarantee: no message content is logged or stored at any point.
"""

import html
import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService
from bot.services.mention_service import MentionService
from bot.services.rate_limit_service import RateLimitService
from bot.utils.telegram_helpers import get_chat_admins, is_group_admin

logger = logging.getLogger(__name__)

_GROUP_TYPES = ("group", "supergroup")


async def setup_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /setup — activate bot in group.
    Flow: verify sender is admin → check not already active → activate → confirm.
    Admin-only. Logs group_id, activated_by (user_id), timestamp.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/setup can only be used in group chats.")
        return

    # Fetch admin list once — used for both auth check and member sync
    admins = await get_chat_admins(context.bot, chat.id)
    if not any(m.user.id == user.id for m in admins):
        await msg.reply_text("Only group admins can use /setup.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    member_svc: MemberService = context.bot_data["member_service"]

    activated = await group_svc.activate(chat.id, user.id)
    if not activated:
        await msg.reply_text("Bot is already active in this group.")
        return

    count = await member_svc.sync_admins_from_list(chat.id, admins)
    await msg.reply_text(
        f"Bot activated. {count} admin(s) added to member registry.\n"
        "Use /all to mention all group members."
    )


async def all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /all — mention all known group members.
    Flow: check active → restrict_all_to_admins check → check rate limit →
          fetch members → send mentions → record invocation → optional delete trigger.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        return

    group_svc: GroupService = context.bot_data["group_service"]

    if not await group_svc.is_active(chat.id):
        await msg.reply_text("Bot not active in this group. Use /setup first.")
        return

    cfg = await group_svc.get_config(chat.id)

    if cfg["restrict_all_to_admins"] == "on":
        if not await is_group_admin(context.bot, chat.id, user.id):
            await msg.reply_text("Only group admins can use /all in this group.")
            return

    rate_svc: RateLimitService = context.bot_data["rate_limit_service"]
    allowed, seconds_remaining = await rate_svc.check_cooldown(chat.id, cfg["cooldown"])
    if not allowed:
        await msg.reply_text(f"Please wait {seconds_remaining}s before using /all again.")
        return

    member_svc: MemberService = context.bot_data["member_service"]
    members = await member_svc.get_mentionable_members(chat.id)
    # Exclude the sender — no need to tag yourself
    members = [m for m in members if m["user_id"] != user.id]
    if not members:
        await msg.reply_text("No members found yet. Send some messages first.")
        return

    mention_svc: MentionService = context.bot_data["mention_service"]
    try:
        mention_strings = mention_svc.build_mention_strings(members, cfg["mention_mode"])
        batches = mention_svc.batch_mentions(mention_strings)
    except ValueError as exc:
        await msg.reply_text(str(exc))
        return

    await mention_svc.send_mentions(context.bot, chat.id, batches, msg.message_id)
    await rate_svc.record_invocation(chat.id, user.id)

    if cfg["delete_trigger"] == "on":
        try:
            await msg.delete()
        except TelegramError:
            logger.warning(
                "delete_trigger: failed to delete message: chat_id=%d", chat.id
            )
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "Note: Could not delete the /all command message. "
                    "Grant the bot admin rights to enable delete_trigger."
                ),
            )


async def syncmembers_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    /syncmembers — manually sync group admins into member registry.
    Admin-only. Replies with count of members synced.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/syncmembers can only be used in group chats.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /syncmembers.")
        return

    member_svc: MemberService = context.bot_data["member_service"]
    count = await member_svc.sync_admins(chat.id, context.bot)
    await msg.reply_text(
        f"Synced {count} admin(s) into member registry.\n\n"
        "Note: The Telegram API does not allow listing all group members. "
        "Non-admin members are added automatically when they send any message in the group."
    )


async def config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /config [key] [value] — view or update group configuration.
    Admin-only.
    No args: show current config.
    With args: update setting (validates key and value).
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/config can only be used in group chats.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /config.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    args = context.args or []

    if not args:
        cfg = await group_svc.get_config(chat.id)
        lines = ["<b>Group config:</b>"]
        for k, v in cfg.items():
            lines.append(f"  <b>{html.escape(str(k))}</b>: {html.escape(str(v))}")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if len(args) != 2:
        await msg.reply_text(
            "Usage: /config &lt;key&gt; &lt;value&gt;\n"
            "Run /config with no arguments to view current settings.",
            parse_mode="HTML",
        )
        return

    key, value = args[0], args[1]
    try:
        await group_svc.update_config(chat.id, key, value, user.id)
    except ValueError as exc:
        await msg.reply_text(str(exc))
        return

    await msg.reply_text(f"Config updated: {key} = {value}")


async def deactivate_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    /deactivate — deactivate bot in this group.
    Admin-only. Logs group_id, deactivated_by (user_id), timestamp.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/deactivate can only be used in group chats.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /deactivate.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    await group_svc.deactivate(chat.id, user.id)
    await msg.reply_text("Bot deactivated. Use /setup to reactivate.")
