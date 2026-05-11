"""
Command handlers — respond to Telegram bot commands.
Commands: /setup, /all, /syncmembers, /registermembers, /invite, /config, /deactivate, /leave
Private DM: /start [token] (deep-link registration from /invite)

Privacy guarantee: no message content is logged or stored at any point.
"""

import html
import logging

from telegram import MessageEntity, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.services.group_service import GroupService
from bot.services.invite_service import InviteService
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


async def register_members_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    /registermembers — bulk-register mentioned users into the member registry.
    Admin-only. Designed for existing groups where the bot missed join events.

    Only TEXT_MENTION entities are registered (Telegram provides a full User object).
    Plain @username MENTION entities are skipped — no user_id is available from them.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/registermembers can only be used in group chats.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    if not await group_svc.is_active(chat.id):
        await msg.reply_text("Bot not active in this group. Use /setup first.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /registermembers.")
        return

    entities = msg.entities or []
    text_mentions = [
        e for e in entities if e.type == MessageEntity.TEXT_MENTION and e.user
    ]
    username_mention_count = sum(
        1 for e in entities if e.type == MessageEntity.MENTION
    )

    if not text_mentions and not username_mention_count:
        await msg.reply_text(
            "No mentions found. Use the @ picker to mention members.\n"
            "Example: /registermembers @Alice @Bob"
        )
        return

    member_svc: MemberService = context.bot_data["member_service"]
    count = 0
    for entity in text_mentions:
        mentioned_user = entity.user
        if not mentioned_user.is_bot:
            await member_svc.discover_member(chat.id, mentioned_user)
            count += 1

    lines = [f"Registered {count} member(s)."]
    if username_mention_count:
        lines.append(
            f"{username_mention_count} @username mention(s) skipped — "
            "Telegram does not provide user IDs for plain @username text. "
            "Ask those users to send any message so the bot can register them automatically."
        )
    await msg.reply_text("\n\n".join(lines))


async def invite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /invite — generate a deep-link registration URL for the group.
    Admin-only. Posts a link members can click to DM the bot and self-register.
    Token is multi-use for its lifetime (default: invite_expiry hours).
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/invite can only be used in group chats.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    if not await group_svc.is_active(chat.id):
        await msg.reply_text("Bot not active in this group. Use /setup first.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /invite.")
        return

    cfg = await group_svc.get_config(chat.id)
    expiry_hours = cfg["invite_expiry"]

    invite_svc: InviteService = context.bot_data["invite_service"]
    token = await invite_svc.create_invite(chat.id, expiry_hours)

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start={token}"

    await msg.reply_text(
        f"<b>Member registration link</b>\n\n"
        f"Share this with group members so they can register for /all mentions:\n"
        f'<a href="{deep_link}">Tap here to register</a>\n\n'
        f"Or open a chat with @{html.escape(bot_username)} and send:\n"
        f"<code>/start {html.escape(token)}</code>\n\n"
        f"Expires in {expiry_hours} hour(s).",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start [token] — deep-link registration handler (private DM only).
    Without token: show welcome message.
    With valid token: register the user in the associated group.
    """
    msg = update.effective_message
    user = update.effective_user

    args = context.args or []
    if not args:
        await msg.reply_text(
            "Hi! I'm all247 — I help mention all members in a Telegram group.\n\n"
            "To register for group mentions, use the /invite link shared in your group."
        )
        return

    token = args[0]
    invite_svc: InviteService = context.bot_data["invite_service"]
    group_id = await invite_svc.validate_token(token)

    if group_id is None:
        await msg.reply_text(
            "This registration link is invalid or has expired.\n"
            "Ask a group admin to run /invite again."
        )
        return

    group_svc: GroupService = context.bot_data["group_service"]
    if not await group_svc.is_active(group_id):
        await msg.reply_text("This registration link is no longer valid.")
        return

    member_svc: MemberService = context.bot_data["member_service"]
    await member_svc.discover_member(group_id, user)

    try:
        group_chat = await context.bot.get_chat(group_id)
        group_name = html.escape(group_chat.title or str(group_id))
    except TelegramError:
        group_name = "the group"

    await msg.reply_text(
        f"You've been registered in <b>{group_name}</b> "
        f"and will be included in /all mentions.",
        parse_mode="HTML",
    )
    logger.info("Member registered via invite: group_id=%d user_id=%d", group_id, user.id)


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


async def leave_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    /leave — purge all member data for this group, deactivate, and bot leaves.
    Admin-only. Irreversible: member registry is hard-deleted.
    Reply is sent BEFORE leaving so the confirmation is visible.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in _GROUP_TYPES:
        await msg.reply_text("/leave can only be used in group chats.")
        return

    if not await is_group_admin(context.bot, chat.id, user.id):
        await msg.reply_text("Only group admins can use /leave.")
        return

    group_svc: GroupService = context.bot_data["group_service"]
    member_svc: MemberService = context.bot_data["member_service"]
    invite_svc: InviteService = context.bot_data["invite_service"]

    await member_svc.purge_members(chat.id)
    await invite_svc.delete_tokens_for_group(chat.id)
    await group_svc.deactivate(chat.id, user.id)

    await msg.reply_text(
        "Member registry cleared. Bot is leaving the group.\n"
        "Add the bot again and run /setup to start fresh."
    )
    await context.bot.leave_chat(chat.id)
    logger.info("Bot left group after /leave: group_id=%d", chat.id)


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
