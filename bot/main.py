"""
all247 — entry point.
Initializes config, DB, services, and starts the bot.
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from bot.config import load_config
from bot.handlers.command_handlers import (
    all_handler,
    config_handler,
    deactivate_handler,
    invite_handler,
    leave_handler,
    register_members_handler,
    setup_handler,
    start_handler,
    syncmembers_handler,
)
from bot.handlers.event_handlers import (
    chat_member_handler,
    message_handler,
    my_chat_member_handler,
)
from bot.repository.db import run_migrations
from bot.services.group_service import GroupService
from bot.services.invite_service import InviteService
from bot.services.member_service import MemberService
from bot.services.mention_service import MentionService
from bot.services.rate_limit_service import RateLimitService

_HEARTBEAT_PATH = Path("/tmp/all247_heartbeat")


def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )
    # Suppress noisy library loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


async def _heartbeat_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Touch heartbeat file on every processed update for Docker HEALTHCHECK."""
    try:
        _HEARTBEAT_PATH.touch()
    except OSError:
        pass


async def post_init(application: Application) -> None:
    """Runs after bot starts. Runs migrations, purges stale rate limit entries, prunes stale members."""
    logger = logging.getLogger(__name__)

    config = application.bot_data["config"]
    await run_migrations(config.db_path)

    rate_limit_svc: RateLimitService = application.bot_data["rate_limit_service"]
    purged = await rate_limit_svc.purge_old_entries()
    logger.info("Purged %d stale rate limit entries on startup", purged)

    invite_svc: InviteService = application.bot_data["invite_service"]
    await invite_svc.purge_expired_tokens()

    config = application.bot_data["config"]
    if config.stale_member_prune_days > 0:
        group_svc: GroupService = application.bot_data["group_service"]
        member_svc: MemberService = application.bot_data["member_service"]
        group_ids = await group_svc.get_all_active_group_ids()
        total_pruned = 0
        for gid in group_ids:
            count = await member_svc.prune_stale_if_configured(gid, config.stale_member_prune_days)
            total_pruned += count
        if total_pruned:
            logger.info("Stale members pruned on startup: total=%d", total_pruned)


def build_application(config) -> Application:
    """Wire up services, handlers, and return the configured Application."""
    # Services — injected into handler context via bot_data
    group_svc = GroupService(config.db_path)
    invite_svc = InviteService(config.db_path)
    member_svc = MemberService(config.db_path)
    mention_svc = MentionService(config.max_mentionable_members)
    rate_limit_svc = RateLimitService(config.db_path, config.rate_limit_purge_days)

    app = (
        Application.builder()
        .token(config.bot_token)
        .post_init(post_init)
        .build()
    )

    app.bot_data.update({
        "config": config,
        "group_service": group_svc,
        "invite_service": invite_svc,
        "member_service": member_svc,
        "mention_service": mention_svc,
        "rate_limit_service": rate_limit_svc,
    })

    # Heartbeat: runs for every update, before other handlers (group=-1)
    app.add_handler(TypeHandler(Update, _heartbeat_handler), group=-1)

    # Command handlers
    app.add_handler(CommandHandler("start", start_handler, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("setup", setup_handler))
    app.add_handler(CommandHandler("all", all_handler))
    app.add_handler(CommandHandler("syncmembers", syncmembers_handler))
    app.add_handler(CommandHandler("registermembers", register_members_handler))
    app.add_handler(CommandHandler("invite", invite_handler))
    app.add_handler(CommandHandler("config", config_handler))
    app.add_handler(CommandHandler("leave", leave_handler))
    app.add_handler(CommandHandler("deactivate", deactivate_handler))

    # /all via caption (e.g. photo sent with /all as caption text)
    app.add_handler(
        MessageHandler(
            filters.CAPTION & filters.CaptionRegex(r"^/all(@\w+)?(\s|$)"),
            all_handler,
        )
    )

    # Event handlers
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )
    app.add_handler(
        ChatMemberHandler(chat_member_handler, chat_member_types=ChatMemberHandler.CHAT_MEMBER)
    )
    app.add_handler(
        ChatMemberHandler(my_chat_member_handler, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER)
    )

    return app


def main() -> None:
    load_dotenv()
    config = load_config()
    setup_logging(config.log_level)

    logger = logging.getLogger(__name__)
    logger.info("all247 starting up")
    logger.warning(
        "IMPORTANT: Ensure Privacy Mode is DISABLED for this bot in BotFather "
        "(Bot Settings → Group Privacy → Turn off). "
        "Without this, passive member discovery will silently fail."
    )

    app = build_application(config)

    if config.webhook_url:
        logger.info("Starting in webhook mode on port %d", config.webhook_port)
        # The bot token doubles as the URL path secret (standard Telegram pattern).
        # It will appear in web server access logs — restrict log file permissions
        # (chmod 640) or suppress logging for the bot path in nginx/caddy config.
        app.run_webhook(
            listen="0.0.0.0",
            port=config.webhook_port,
            url_path=config.bot_token,
            webhook_url=f"{config.webhook_url}/{config.bot_token}",
        )
    else:
        logger.info("Starting in long polling mode")
        app.run_polling(
            allowed_updates=["message", "chat_member", "my_chat_member"]
        )


if __name__ == "__main__":
    main()
