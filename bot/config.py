"""
Configuration loader — reads all settings from environment variables.
No secrets are hardcoded here. Use .env for local development.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    db_path: str
    log_level: str
    webhook_url: str | None
    webhook_port: int
    default_cooldown_seconds: int
    rate_limit_purge_days: int
    stale_member_prune_days: int  # 0 = disabled
    max_mentionable_members: int


def load_config() -> Config:
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN environment variable is required")

    return Config(
        bot_token=bot_token,
        db_path=os.environ.get("DB_PATH", "./data/all247.db"),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        webhook_url=os.environ.get("WEBHOOK_URL") or None,
        webhook_port=int(os.environ.get("WEBHOOK_PORT", "8443")),
        default_cooldown_seconds=int(os.environ.get("DEFAULT_COOLDOWN_SECONDS", "0")),
        rate_limit_purge_days=int(os.environ.get("RATE_LIMIT_PURGE_DAYS", "7")),
        stale_member_prune_days=int(os.environ.get("STALE_MEMBER_PRUNE_DAYS", "0")),
        max_mentionable_members=int(os.environ.get("MAX_MENTIONABLE_MEMBERS", "1000")),
    )
