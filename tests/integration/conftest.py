"""
Shared fixtures for integration tests.
"""

import pytest
import pytest_asyncio

from bot.repository.db import run_migrations


@pytest_asyncio.fixture
async def db_path(tmp_path):
    """Temporary SQLite DB with all migrations applied."""
    path = str(tmp_path / "test.db")
    await run_migrations(path)
    return path
