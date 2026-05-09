"""
all247 — entry point.
Initializes config, DB, services, and starts the bot.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import load_config
from bot.handlers.command_handlers import (
    all_handler,
    config_handler,
    deactivate_handler,
    setup_handler,
    syncmembers_handler,
)
from bot.handlers.event_handlers import (
    bot_added_handler,
    chat_member_handler,
    message_handler,
)
from bot.repository.db import run_migrations
from bot.services.group_service import GroupService
from bot.services.member_service import MemberService
from bot.services.mention_service import MentionService
from bot.services.rate_limit_service import RateLimitService


def setup_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=getattr(logging, log_level, logging.INFO),
    )
    # Suppress noisy library loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


async def post_init(application: Application) -> None:
    """Runs after bot starts. Purges stale rate limit entries."""
    rate_limit_svc: RateLimitService = application.bot_data["rate_limit_service"]
    purged = await rate_limit_svc.purge_old_entries()
    logging.getLogger(__name__).info("Purged %d stale rate limit entries on startup", purged)


def build_application(config) -> Application:
    """Wire up services, handlers, and return the configured Application."""
    # Services — injected into handler context via bot_data
    group_svc = GroupService(config.db_path)
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
        "member_service": member_svc,
        "mention_service": mention_svc,
        "rate_limit_service": rate_limit_svc,
    })

    # Command handlers
    app.add_handler(CommandHandler("setup", setup_handler))
    app.add_handler(CommandHandler("all", all_handler))
    app.add_handler(CommandHandler("syncmembers", syncmembers_handler))
    app.add_handler(CommandHandler("config", config_handler))
    app.add_handler(CommandHandler("deactivate", deactivate_handler))

    # Event handlers
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )
    app.add_handler(ChatMemberHandler(chat_member_handler))

    return app


async def main() -> None:
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

    await run_migrations(config.db_path)

    app = build_application(config)

    if config.webhook_url:
        logger.info("Starting in webhook mode on port %d", config.webhook_port)
        await app.run_webhook(
            listen="0.0.0.0",
            port=config.webhook_port,
            url_path=config.bot_token,
            webhook_url=f"{config.webhook_url}/{config.bot_token}",
        )
    else:
        logger.info("Starting in long polling mode")
        await app.run_polling(allowed_updates=["message", "chat_member"])


if __name__ == "__main__":
    asyncio.run(main())
