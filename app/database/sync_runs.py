from typing import List, Optional, Dict, Any
from datetime import datetime
from app.database.db import get_db


async def create_sync_run(
    store_id: str,
    file_path: str,
    sync_mode: str,
    file_original_name: Optional[str] = None,
    identifier_type: Optional[str] = None,
    total_rows: int = 0,
) -> int:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """INSERT INTO sync_runs 
               (store_id, file_path, sync_mode, file_original_name, identifier_type, status, total_rows, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', ?, CURRENT_TIMESTAMP)""",
            (store_id, file_path, sync_mode, file_original_name, identifier_type, total_rows),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def update_sync_run(
    run_id: int,
    status: Optional[str] = None,
    processed_rows: Optional[int] = None,
    missing_rows: Optional[int] = None,
    duplicate_rows: Optional[int] = None,
    error_message: Optional[str] = None,
) -> bool:
    updates = []
    params = []

    if status is not None:
        updates.append("status = ?")
        params.append(status)

        if status in ("completed", "failed"):
            updates.append("completed_at = CURRENT_TIMESTAMP")

    if processed_rows is not None:
        updates.append("processed_rows = ?")
        params.append(processed_rows)

    if missing_rows is not None:
        updates.append("missing_rows = ?")
        params.append(missing_rows)

    if duplicate_rows is not None:
        updates.append("duplicate_rows = ?")
        params.append(duplicate_rows)

    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)

    if not updates:
        return False

    params.append(run_id)
    query = f"UPDATE sync_runs SET {', '.join(updates)} WHERE id = ?"

    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        await conn.commit()
        return cursor.rowcount > 0
    finally:
        await conn.close()


async def get_sync_run(run_id: int) -> Optional[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM sync_runs WHERE id = ?",
            (run_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def get_sync_runs(
    store_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM sync_runs WHERE 1=1"
    params = []

    if store_id is not None:
        query += " AND store_id = ?"
        params.append(store_id)

    if status is not None:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_sync_run_items(run_id: int) -> List[Dict[str, Any]]:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            "SELECT * FROM sync_items WHERE run_id = ? ORDER BY id",
            (run_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def add_sync_item(
    run_id: int,
    reference: str,
    status: str,
    location_id: Optional[str] = None,
    quantity: Optional[int] = None,
    error_message: Optional[str] = None,
    shopify_product_id: Optional[str] = None,
    shopify_variant_id: Optional[str] = None,
    applied_delta: Optional[int] = None,
    final_quantity: Optional[int] = None,
) -> int:
    conn = await get_db()
    try:
        cursor = await conn.execute(
            """INSERT INTO sync_items 
               (run_id, reference, status, location_id, quantity, error_message, 
                shopify_product_id, shopify_variant_id, applied_delta, final_quantity)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, reference, status, location_id, quantity, error_message,
                shopify_product_id, shopify_variant_id, applied_delta, final_quantity,
            ),
        )
        await conn.commit()
        return cursor.lastrowid
    finally:
        await conn.close()


async def add_sync_items_batch(run_id: int, items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0

    conn = await get_db()
    try:
        for item in items:
            await conn.execute(
                """INSERT INTO sync_items 
                   (run_id, reference, status, location_id, quantity, error_message, 
                    shopify_product_id, shopify_variant_id, applied_delta, final_quantity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    item.get("reference"),
                    item.get("status"),
                    item.get("location_id"),
                    item.get("quantity"),
                    item.get("error_message"),
                    item.get("shopify_product_id"),
                    item.get("shopify_variant_id"),
                    item.get("applied_delta"),
                    item.get("final_quantity"),
                ),
            )
        await conn.commit()
        return len(items)
    finally:
        await conn.close()


async def get_sync_stats(store_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
    query = """SELECT 
                COUNT(*) as total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(total_rows) as total_rows,
                SUM(processed_rows) as processed_rows
             FROM sync_runs
             WHERE started_at >= datetime('now', '-' || ? || ' days')"""
    
    params = [days]
    
    if store_id:
        query += " AND store_id = ?"
        params.append(store_id)

    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        row = await cursor.fetchone()
        
        if row:
            return {
                "total_runs": row[0] or 0,
                "completed": row[1] or 0,
                "failed": row[2] or 0,
                "total_rows": row[3] or 0,
                "processed_rows": row[4] or 0,
            }
        
        return {
            "total_runs": 0,
            "completed": 0,
            "failed": 0,
            "total_rows": 0,
            "processed_rows": 0,
        }
    finally:
        await conn.close()


async def get_recent_runs(store_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    query = "SELECT * FROM sync_runs"
    params = []
    
    if store_id:
        query += " WHERE store_id = ?"
        params.append(store_id)
    
    query += f" ORDER BY started_at DESC LIMIT {limit}"
    
    conn = await get_db()
    try:
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await conn.close()