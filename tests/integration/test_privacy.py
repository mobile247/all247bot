"""
Privacy verification tests.

1. Log output must never contain display names or usernames at INFO+ level.
2. DB schema (migration SQL) must not define any message-content columns.
3. rate_limit_log must not have a triggered_by column (ADR-009).
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from telegram import User

from bot.services.group_service import GroupService
from bot.services.member_service import MemberService

GROUP_ID = -100777888

# Column names that would indicate stored message content — forbidden in schema.
# Intentionally specific: generic SQLite type keywords like "text" are excluded.
_FORBIDDEN_CONTENT_COLUMNS = {
    "message_text",
    "message_content",
    "message_body",
    "msg_text",
    "payload",
}

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


def _make_user(user_id: int, full_name: str, username: str | None = None) -> MagicMock:
    user = MagicMock(spec=User)
    user.id = user_id
    user.full_name = full_name
    user.username = username
    user.is_bot = False
    return user


# ---------------------------------------------------------------------------
# Log output checks
# ---------------------------------------------------------------------------


async def test_discover_member_logs_nothing_at_info_level(db_path, caplog):
    """discover_member must not emit any INFO+ log lines."""
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Super Secret Name", "secretuser")

    with caplog.at_level(logging.INFO, logger="bot.services.member_service"):
        await member_svc.discover_member(GROUP_ID, user)

    info_records = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert info_records == [], (
        f"Unexpected INFO+ log from discover_member: {[r.getMessage() for r in info_records]}"
    )


async def test_discover_member_debug_log_contains_no_names(db_path, caplog):
    """DEBUG log for discover_member must contain only IDs, never display names or usernames."""
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Hidden Name", "hiddenuser")

    with caplog.at_level(logging.DEBUG, logger="bot.services.member_service"):
        await member_svc.discover_member(GROUP_ID, user)

    for record in caplog.records:
        msg = record.getMessage()
        assert "Hidden Name" not in msg, f"Display name leaked into log: {msg}"
        assert "hiddenuser" not in msg, f"Username leaked into log: {msg}"


async def test_mark_left_logs_no_names(db_path, caplog):
    """mark_left must log only IDs."""
    group_svc = GroupService(db_path)
    member_svc = MemberService(db_path)
    await group_svc.activate(GROUP_ID, activated_by=1)

    user = _make_user(42, "Sensitive Person", "sensitive")
    await member_svc.discover_member(GROUP_ID, user)

    with caplog.at_level(logging.DEBUG, logger="bot.services.member_service"):
        await member_svc.mark_left(GROUP_ID, 42)

    for record in caplog.records:
        msg = record.getMessage()
        assert "Sensitive Person" not in msg
        assert "sensitive" not in msg


# ---------------------------------------------------------------------------
# DB schema audit
# ---------------------------------------------------------------------------


def _strip_sql_comments(sql: str) -> str:
    """Remove single-line SQL comments (-- ...) to avoid false positives."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return "\n".join(lines)


def test_migration_sql_has_no_message_content_columns():
    """No migration file may define columns that store message content."""
    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    assert sql_files, f"No migration files found in {_MIGRATIONS_DIR}"

    for sql_file in sql_files:
        sql = _strip_sql_comments(sql_file.read_text().lower())
        for col in _FORBIDDEN_CONTENT_COLUMNS:
            assert col not in sql, (
                f"Forbidden column '{col}' found in {sql_file.name}"
            )


def test_rate_limit_log_no_triggered_by():
    """rate_limit_log must not define triggered_by as a column (ADR-009)."""
    sql = _strip_sql_comments((_MIGRATIONS_DIR / "002_rate_limits.sql").read_text().lower())
    assert "triggered_by" not in sql, (
        "ADR-009 violation: triggered_by column defined in rate_limit_log schema"
    )


def test_members_table_no_message_columns():
    """members table must not define any message-content columns."""
    sql = _strip_sql_comments((_MIGRATIONS_DIR / "001_initial_schema.sql").read_text().lower())
    for col in _FORBIDDEN_CONTENT_COLUMNS:
        assert col not in sql, f"Forbidden column '{col}' in members schema"
