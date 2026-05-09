"""
Database connection and migration runner.
Uses aiosqlite for async SQLite access. Migrations are plain SQL files
in the /migrations directory, applied in filename order (idempotent).
"""

import logging
import os
import pathlib

import aiosqlite

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent.parent / "migrations"


async def get_connection(db_path: str) -> aiosqlite.Connection:
    """Open a database connection with foreign keys enabled."""
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = aiosqlite.Row
    return conn


async def run_migrations(db_path: str) -> None:
    """Apply all pending SQL migrations in order. Safe to call on every startup."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    async with await get_connection(db_path) as conn:
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
