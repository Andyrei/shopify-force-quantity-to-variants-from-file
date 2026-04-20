import toml
from pathlib import Path
from app.database.db import get_db, check_db_exists
from app.database.stores import get_stores_count
from app.database.crypto import encrypt_token


async def needs_migration() -> bool:
    if not await check_db_exists():
        return True

    count = await get_stores_count()
    return count == 0


async def migrate_from_toml() -> dict:
    toml_path = Path("config_stores.toml")

    if not toml_path.exists():
        return {
            "imported": 0,
            "skipped": 0,
            "error": "config_stores.toml not found",
        }

    try:
        config = toml.load(toml_path)
    except Exception as e:
        return {
            "imported": 0,
            "skipped": 0,
            "error": f"Failed to parse config_stores.toml: {e}",
        }

    stores_config = config.get("stores", {})
    if not stores_config:
        return {
            "imported": 0,
            "skipped": 0,
            "error": "No stores found in config_stores.toml",
        }

    imported = 0
    skipped = 0

    conn = await get_db()
    try:
        for store_id, store_data in stores_config.items():
            cursor = await conn.execute(
                "SELECT store_id FROM stores WHERE store_id = ?",
                (store_id,)
            )
            existing = await cursor.fetchone()

            if existing:
                skipped += 1
                continue

            store_name = store_data.get("STORE_NAME", "")
            title = store_data.get("TITLE", "")
            api_version = store_data.get("API_VERSION", "2025-10")
            access_token = store_data.get("ACCESS_TOKEN", "")

            if not store_name or not access_token:
                skipped += 1
                continue

            encrypted_token = encrypt_token(access_token)

            await conn.execute(
                """INSERT INTO stores (store_id, store_name, title, api_version, access_token_encrypted, is_active)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (store_id, store_name, title, api_version, encrypted_token),
            )
            imported += 1

        await conn.commit()
    finally:
        await conn.close()

    return {
        "imported": imported,
        "skipped": skipped,
        "error": None,
    }


async def add_title_column_if_needed() -> dict:
    conn = await get_db()
    try:
        cursor = await conn.execute("PRAGMA table_info(stores)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if "title" not in columns:
            await conn.execute("ALTER TABLE stores ADD COLUMN title TEXT")
            await conn.commit()
            return {"added": True}
        return {"added": False}
    finally:
        await conn.close()


async def run_migration_if_needed() -> dict:
    if not await needs_migration():
        return {
            "imported": 0,
            "skipped": 0,
            "error": "No migration needed",
        }

    result = await migrate_from_toml()
    return result


async def get_migration_status() -> dict:
    has_db = await check_db_exists()
    stores_count = await get_stores_count() if has_db else 0

    toml_exists = Path("config_stores.toml").exists()

    return {
        "database_exists": has_db,
        "stores_in_db": stores_count,
        "toml_exists": toml_exists,
        "needs_migration": toml_exists and stores_count == 0,
    }