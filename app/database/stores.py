import toml
from typing import Optional, List, Dict, Any
from app.database.db import get_db
from app.database.crypto import encrypt_token, decrypt_token


async def get_store(store_id: str) -> Optional[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM stores WHERE store_id = ?",
            (store_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        store = dict(row)
        store["access_token"] = decrypt_token(store.pop("access_token_encrypted"))
        return store
    finally:
        await conn.close()


async def get_all_stores() -> List[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT store_id, store_name, title, api_version, is_active, created_at, updated_at FROM stores ORDER BY store_id"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_store_credentials(store_id: str) -> Optional[Dict[str, str]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT store_name, api_version, access_token_encrypted FROM stores WHERE store_id = ? AND is_active = 1",
            (store_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "STORE_NAME": row["store_name"],
            "API_VERSION": row["api_version"],
            "ACCESS_TOKEN": decrypt_token(row["access_token_encrypted"]),
        }
    finally:
        await conn.close()


async def create_store(
    store_id: str,
    store_name: str,
    access_token: str,
    api_version: str = "2025-10",
    title: str = "",
    is_active: bool = True,
) -> int:
    encrypted_token = encrypt_token(access_token)
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """INSERT INTO stores (store_id, store_name, title, api_version, access_token_encrypted, is_active)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (store_id, store_name, title, api_version, encrypted_token, is_active),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def update_store(
    store_id: str,
    store_name: Optional[str] = None,
    title: Optional[str] = None,
    access_token: Optional[str] = None,
    api_version: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> bool:
    updates = []
    params = []

    if store_name is not None:
        updates.append("store_name = ?")
        params.append(store_name)

    if title is not None:
        updates.append("title = ?")
        params.append(title)

    if access_token is not None:
        updates.append("access_token_encrypted = ?")
        params.append(encrypt_token(access_token))

    if api_version is not None:
        updates.append("api_version = ?")
        params.append(api_version)

    if is_active is not None:
        updates.append("is_active = ?")
        params.append(is_active)

    if not updates:
        return False

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(store_id)

    query = f"UPDATE stores SET {', '.join(updates)} WHERE store_id = ?"
    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def delete_store(store_id: str) -> bool:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "DELETE FROM stores WHERE store_id = ?",
            (store_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def import_from_toml() -> Dict[str, int]:
    toml_path = "config_stores.toml"

    try:
        config = toml.load(toml_path)
    except FileNotFoundError:
        return {"imported": 0, "skipped": 0, "error": "config_stores.toml not found"}
    except Exception as e:
        return {"imported": 0, "skipped": 0, "error": str(e)}

    stores_config = config.get("stores", {})
    if not stores_config:
        return {"imported": 0, "skipped": 0, "error": "No stores found in config"}

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
            api_version = store_data.get("API_VERSION", "2025-10")
            access_token = store_data.get("ACCESS_TOKEN", "")

            if not store_name or not access_token:
                skipped += 1
                continue

            encrypted_token = encrypt_token(access_token)

            await conn.execute(
                """INSERT INTO stores (store_id, store_name, api_version, access_token_encrypted, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (store_id, store_name, api_version, encrypted_token),
            )
            imported += 1

        await conn.commit()
    finally:
        await conn.close()

    return {"imported": imported, "skipped": skipped, "error": None}


async def get_stores_count() -> int:
    conn = await get_db()
    try:
        cursor = await conn.execute("SELECT COUNT(*) FROM stores")
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await conn.close()