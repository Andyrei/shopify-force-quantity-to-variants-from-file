from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.database.db import get_db


async def get_locations(store_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    query = "SELECT * FROM locations WHERE store_id = ?"
    params = [store_id]

    if not include_inactive:
        query += " AND is_active = 1"

    query += " ORDER BY is_primary DESC, location_name ASC"

    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_location_by_id(store_id: str, location_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM locations WHERE store_id = ? AND location_id = ?",
            (store_id, location_id)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_primary_location(store_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM locations WHERE store_id = ? AND is_primary = 1 AND is_active = 1",
            (store_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def cache_locations(
    store_id: str,
    locations: List[Dict[str, Any]],
    is_primary_id: Optional[str] = None,
) -> int:
    cached_count = 0

    conn = await get_db()
    try:
        await conn.execute(
            "UPDATE locations SET is_active = 0 WHERE store_id = ?",
            (store_id,)
        )

        for loc in locations:
            location_id = loc.get("id", "")
            if not location_id:
                continue

            location_name = loc.get("name", "")
            is_primary = 1 if location_id == is_primary_id else 0

            await conn.execute(
                """INSERT INTO locations (store_id, location_id, location_name, is_primary, is_active, cached_at)
                   VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT(store_id, location_id) DO UPDATE SET
                       location_name = excluded.location_name,
                       is_primary = excluded.is_primary,
                       is_active = 1,
                       cached_at = CURRENT_TIMESTAMP""",
                (store_id, location_id, location_name, is_primary),
            )
            cached_count += 1

        await conn.commit()
    finally:
        await conn.close()

    return cached_count


async def invalidate_locations(store_id: str) -> int:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "UPDATE locations SET is_active = 0 WHERE store_id = ?",
            (store_id,)
        )
        await conn.commit()
        return cursor.rowcount
    finally:
        await conn.close()


async def is_cache_valid(store_id: str, max_age_hours: int = 24) -> bool:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """SELECT cached_at FROM locations
               WHERE store_id = ? AND is_active = 1
               ORDER BY cached_at DESC LIMIT 1""",
            (store_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return False

        cached_at = datetime.fromisoformat(row["cached_at"])
        age = datetime.now() - cached_at
        return age < timedelta(hours=max_age_hours)
    finally:
        await conn.close()


async def get_locations_count(store_id: str) -> int:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM locations WHERE store_id = ? AND is_active = 1",
            (store_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await conn.close()