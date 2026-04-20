import os
import aiosqlite
from pathlib import Path
from typing import Optional

DATABASE_DIR = Path("data")
DATABASE_PATH = DATABASE_DIR / "sync_app.db"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)


async def get_db():
    """Get async DB connection."""
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db() -> bool:
    """Initialize database with schema."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    conn = await get_db()
    await conn.executescript(schema_path.read_text())
    await conn.commit()
    await conn.close()

    return True


async def check_db_exists() -> bool:
    return DATABASE_PATH.exists()


async def get_db_stats() -> dict:
    conn = await get_db()
    try:
        stats = {}
        tables = ["stores", "locations", "sync_runs", "sync_items", "files"]
        for table in tables:
            cursor = await conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            row = await cursor.fetchone()
            stats[table] = row[0] if row else 0
        return stats
    finally:
        await conn.close()


_db_initialized = False


async def ensure_db_initialized(force: bool = False) -> bool:
    global _db_initialized

    if _db_initialized and not force:
        return False

    exists = await check_db_exists()
    if not exists or force:
        await init_db()
        _db_initialized = True

        schema_path = Path(__file__).parent / "schema.sql"
        conn = await get_db()
        try:
            await conn.executescript(schema_path.read_text())
            await conn.commit()
        finally:
            await conn.close()

    _db_initialized = True
    return True