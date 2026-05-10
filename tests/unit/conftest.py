"""
Shared fixtures for unit tests.
"""

import pytest
import pytest_asyncio

from bot.repository.db import run_migrations


@pytest_asyncio.fixture
async def db_path(tmp_path):
    """Provide a temporary SQLite DB path with migrations applied."""
    path = str(tmp_path / "test.db")
    await run_migrations(path)
    return path
