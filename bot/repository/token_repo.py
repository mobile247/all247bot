"""
Token repository — CRUD for registration_tokens table.
All methods accept an existing aiosqlite.Connection.
"""

import aiosqlite


async def create_token(
    conn: aiosqlite.Connection, token: str, group_id: int, expires_at: str
) -> None:
    """Insert (or replace) a registration token."""
    await conn.execute(
        "INSERT OR REPLACE INTO registration_tokens (token, group_id, expires_at)"
        " VALUES (?, ?, ?)",
        (token, group_id, expires_at),
    )
    await conn.commit()


async def get_token(conn: aiosqlite.Connection, token: str) -> aiosqlite.Row | None:
    """Return the token row if it exists and has not expired, else None."""
    async with conn.execute(
        "SELECT * FROM registration_tokens"
        " WHERE token = ? AND expires_at > datetime('now')",
        (token,),
    ) as cur:
        return await cur.fetchone()


async def delete_expired_tokens(conn: aiosqlite.Connection) -> int:
    """Delete all expired tokens. Returns count deleted."""
    async with conn.execute(
        "DELETE FROM registration_tokens WHERE expires_at <= datetime('now')"
    ) as cur:
        count = cur.rowcount
    await conn.commit()
    return count


async def delete_tokens_for_group(conn: aiosqlite.Connection, group_id: int) -> None:
    """Delete all tokens for a group (called on /leave)."""
    await conn.execute(
        "DELETE FROM registration_tokens WHERE group_id = ?", (group_id,)
    )
    await conn.commit()
