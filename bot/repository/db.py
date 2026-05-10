"""
Database connection and migration runner.
Uses aiosqlite for async SQLite access. Migrations are plain SQL files
in the /migrations directory, applied in filename order (idempotent).
"""

import logging
import os
import pathlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent.parent / "migrations"


@asynccontextmanager
async def get_connection(db_path: str) -> AsyncIterator[aiosqlite.Connection]:
    """Open a database connection with foreign keys enabled.
    WAL mode is set once at startup in run_migrations — not repeated here."""
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn


async def run_migrations(db_path: str) -> None:
    """Apply all pending SQL migrations in order. Safe to call on every startup."""
    data_dir = os.path.dirname(db_path)
    os.makedirs(data_dir, exist_ok=True)
    # Restrict to owner-only — DB contains member display names and usernames
    os.chmod(data_dir, 0o700)

    # Enable WAL mode once — it persists on disk, no need to re-apply per connection.
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute("PRAGMA journal_mode = WAL") as cur:
            row = await cur.fetchone()
        if not row or row[0] != "wal":
            logger.warning(
                "SQLite WAL mode could not be enabled (got %r). "
                "Concurrent write performance may be degraded.",
                row[0] if row else "unknown",
            )
        else:
            logger.debug("SQLite WAL mode confirmed")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    async with get_connection(db_path) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        await conn.commit()

        for migration_file in migration_files:
            filename = migration_file.name
            async with conn.execute(
                "SELECT filename FROM _migrations WHERE filename = ?", (filename,)
            ) as cursor:
                already_applied = await cursor.fetchone()

            if already_applied:
                logger.debug("Migration already applied: %s", filename)
                continue

            sql = migration_file.read_text()
            await conn.executescript(sql)
            await conn.execute(
                "INSERT INTO _migrations (filename) VALUES (?)", (filename,)
            )
            await conn.commit()
            logger.info("Applied migration: %s", filename)
