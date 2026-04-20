from datetime import datetime
import os
import toml
import json
import asyncio
from fastapi import APIRouter, File, Path, Request, UploadFile, HTTPException, Form, Query
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse, FileResponse
import pandas as pd

from app.routes.api.v1.add_locations.main import get_product_variants_and_sync
from app.utilities.shopify import detect_identifier_type, get_product_variants_by_identifier

# Load config once at module level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
config = toml.load(os.path.join(PROJECT_ROOT, "config_stores.toml"))
DONE_SUFFIX = "__DONE__"


def _is_done_file(filename: str) -> bool:
    return DONE_SUFFIX.lower() in filename.lower()


def _build_done_filename(filename: str, counter: int | None = None) -> str:
    stem, ext = os.path.splitext(filename)
    if counter is None:
        return f"{stem}{DONE_SUFFIX}{ext}"
    return f"{stem}{DONE_SUFFIX}{counter}{ext}"


def _mark_file_as_done(resources_dir: str, filename: str) -> str:
    """Rename a resource file by adding a DONE suffix to prevent re-sync."""
    if _is_done_file(filename):
        return filename

    source_path = os.path.join(resources_dir, filename)
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source file not found: {filename}")

    done_filename = _build_done_filename(filename)
    done_path = os.path.join(resources_dir, done_filename)

    counter = 1
    while os.path.exists(done_path):
        done_filename = _build_done_filename(filename, counter=counter)
        done_path = os.path.join(resources_dir, done_filename)
        counter += 1

    os.rename(source_path, done_path)
    return done_filename


def _safe_store_file_path(base_dir: str, filename: str) -> tuple[str, str]:
    """Return a safe filename and absolute file path within the given base directory."""
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    abs_base_dir = os.path.abspath(base_dir)
    abs_file_path = os.path.abspath(os.path.join(abs_base_dir, safe_filename))

    if not abs_file_path.startswith(abs_base_dir + os.sep):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return safe_filename, abs_file_path

def get_current_store_name(request: Request = None):
    """Get current store name from cookie, header, or environment variable"""
    store_id = None
    
    # Try to get from custom header (sent by JavaScript)
    if request:
        store_id = request.headers.get("X-Selected-Store")
    
    # Fallback to environment variable
    if not store_id:
        env_store = os.getenv("STORE_NAME")
        if env_store:
            return env_store.split("-")[1] if "-" in env_store else env_store
    
    # Get store name from config using store_id
    if store_id:
        stores = config.get("stores", {})
        if store_id in stores:
            store_name = stores[store_id].get("STORE_NAME", "")
            return store_name.split("-")[1] if "-" in store_name else store_name
    
    return None


def get_current_store_id(request: Request = None):
    """Get current store id from header or environment mapping."""
    store_id = None

    if request:
        store_id = request.headers.get("X-Selected-Store")

    if store_id:
        return store_id

    env_store = os.getenv("STORE_NAME")
    if env_store:
        stores = config.get("stores", {})
        for sid, sconfig in stores.items():
            if sconfig.get("STORE_NAME") == env_store:
                return sid

    return None

def get_store_config(request: Request = None):
    """Get the full store configuration"""
    store_id = None
    
    # Try to get from custom header
    if request:
        store_id = request.headers.get("X-Selected-Store")
    
    # Fallback to environment variable
    if not store_id:
        env_store = os.getenv("STORE_NAME")
        if env_store:
            # Find store_id by STORE_NAME
            stores = config.get("stores", {})
            for sid, sconfig in stores.items():
                if sconfig.get("STORE_NAME") == env_store:
                    return sconfig
    
    # Get store config using store_id
    if store_id:
        stores = config.get("stores", {})
        return stores.get(store_id)
    
    return None


def _get_store_log_dirs(request: Request) -> list[str]:
    """Build candidate log directories for a store (name and id folders)."""
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")

    store_id = get_current_store_id(request)

    candidates = [
        os.path.join(PROJECT_ROOT, "logs", store_name),
    ]
    if store_id:
        candidates.append(os.path.join(PROJECT_ROOT, "logs", store_id))

    unique_dirs = []
    seen = set()
    for candidate in candidates:
        abs_candidate = os.path.abspath(candidate)
        if abs_candidate in seen:
            continue
        seen.add(abs_candidate)
        unique_dirs.append(abs_candidate)

    return unique_dirs


def _resolve_store_log_file(request: Request, filename: str) -> tuple[str, str]:
    """Resolve a log filename from candidate store log directories."""
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    log_dirs = _get_store_log_dirs(request)

    for logs_dir in log_dirs:
        _, candidate_path = _safe_store_file_path(logs_dir, safe_filename)
        if os.path.isfile(candidate_path):
            return safe_filename, candidate_path

    _, fallback_path = _safe_store_file_path(log_dirs[0], safe_filename)
    return safe_filename, fallback_path

router = APIRouter(
    prefix="/v1",
)

@router.get("/")
def health_check(request: Request):

    # check all the endpoints and return them in a list
    endpoints = []
    for route in request.app.routes:
        if route.path.startswith("/api/v1"):
            endpoints.append({
                "path": route.path,
                "name": route.name,
                "methods": route.methods,
            })

    return {
        "status": "ok",
        "message": "Service is running",
        "endpoints": endpoints,
    }

@router.get("/resources")
async def list_resources(request: Request):
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    try:
        files = os.listdir(resources_dir)
        files = [f for f in files if not f.startswith('.')]
        files = sorted(files, key=lambda f: (_is_done_file(f), f.lower()))
    except FileNotFoundError:
        files = []
    return JSONResponse(files)


@router.get("/logs")
async def list_store_logs(request: Request):
    log_files = []
    seen_filenames = set()

    for logs_dir in _get_store_log_dirs(request):
        try:
            filenames = [f for f in os.listdir(logs_dir) if not f.startswith('.')]
        except FileNotFoundError:
            continue
        except PermissionError:
            raise HTTPException(
                status_code=500,
                detail="Cannot read logs directory. Check permissions for mounted logs volume.",
            )

        for filename in filenames:
            if filename in seen_filenames:
                continue

            file_path = os.path.join(logs_dir, filename)
            if not os.path.isfile(file_path):
                continue

            stat = os.stat(file_path)
            log_files.append({
                "filename": filename,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "type": os.path.splitext(filename)[1].lstrip(".").lower() or "file",
                "source_store_dir": os.path.basename(logs_dir),
                "_mtime": stat.st_mtime,
            })
            seen_filenames.add(filename)

    log_files.sort(key=lambda item: item["_mtime"], reverse=True)
    for item in log_files:
        item.pop("_mtime", None)

    return JSONResponse(log_files)


@router.get("/logs/content/{filename}")
async def get_store_log_content(
    request: Request,
    filename: str = Path(..., description="The name of the log file"),
    lines: int = Query(300, ge=20, le=2000, description="Number of lines to return from the end of the file"),
):
    _, file_path = _resolve_store_log_file(request, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    with open(file_path, "r", encoding="utf-8", errors="replace") as file_obj:
        content_lines = file_obj.readlines()

    preview = "".join(content_lines[-lines:])
    return PlainTextResponse(preview)


@router.get("/logs/download/{filename}")
async def download_store_log(
    request: Request,
    filename: str = Path(..., description="The name of the log file to download"),
):
    safe_filename, file_path = _resolve_store_log_file(request, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    media_type = "text/csv" if safe_filename.lower().endswith(".csv") else "text/plain"
    return FileResponse(file_path, media_type=media_type, filename=safe_filename)


@router.delete("/logs/{filename}")
async def delete_store_log(
    request: Request,
    filename: str = Path(..., description="The name of the log file to delete"),
):
    safe_filename, file_path = _resolve_store_log_file(request, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Log file not found")

    try:
        os.remove(file_path)
        return {"detail": f"Log file '{safe_filename}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting log file: {e}")


@router.delete("/resources/{filename}")
async def delete_resource(
    request: Request,
    filename: str = Path(..., description="The name of the file to delete")
):
    """
    Delete a resource file from the store's resources directory. This is a permanent action and cannot be undone.
    """
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    file_path = os.path.join(resources_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        os.remove(file_path)
        return {"detail": f"File '{filename}' deleted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")

@router.get("/resources/{filename}")
async def download_resource(
    request: Request,
    filename: str = Path(..., description="The name of the file to download"),
    download: bool = Query(False, description="If true, force download")
):
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    file_path = os.path.join(resources_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    media_type = "application/octet-stream"
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename if download else None
    )

@router.get("/check/{filename}")
async def check_file_structure(
    request: Request,
    filename: str = Path(..., description="The name of the file to check")
):
    """Check if the file has required columns and return missing fields"""
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    
    # Get store_id from header
    store_id = request.headers.get("X-Selected-Store")
    if not store_id:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    file_path = os.path.join(resources_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Use pandas to read the file based on extension
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif filename.lower().endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Convert all column names to lowercase
        df.columns = df.columns.str.lower()
        
        # Check if required columns exist in the file (now all lowercase)
        has_location_in_file = any(col in ['id sede', 'location_id', 'location'] for col in df.columns)
        has_sale_channel_in_file = any(col in ['canali di vendita', 'canale di vendita', 'sale_channel'] for col in df.columns)
        has_quantity_in_file = any(col in ['qta', 'quantity', 'qty', 'qtá'] for col in df.columns)
        has_product_ref_in_file = any(col in ['sku', 'barcode'] for col in df.columns)
        
        missing_fields = []
        if not has_location_in_file:
            missing_fields.append("location_id")
        if not has_sale_channel_in_file:
            missing_fields.append("sale_channel")
        if not has_quantity_in_file:
            missing_fields.append("quantity")
        if not has_product_ref_in_file:
            missing_fields.append("sku/barcode")
        
        if missing_fields:
            print(f"DEBUG: File '{filename}' is missing fields: {missing_fields}")
            return {
                "filename": filename,
                "columns": df.columns.tolist(),
                "has_location": has_location_in_file,
                "has_sale_channel": has_sale_channel_in_file,
                "missing_fields": missing_fields,
                "ready_to_sync": False,
                "detail": f"File is missing required fields: {', '.join(missing_fields)}"
            }
        
        # File Fields not missing then proceed to check products in file
        print(f"DEBUG: File '{filename}' has all required fields.")
        # check products in shopify
        prod_reference = []
        data_records = df.to_dict(orient="records")
        for row in data_records:
            # Use 'barcode' if it exists, otherwise use 'sku'
            # Convert to string and handle NaN/None values properly
            if "barcode" in row:
                val = row["barcode"]
            else:
                val = row["sku"]
            
            # Convert to string and handle NaN, None, and float values
            if pd.isna(val) or val is None:
                prod_reference.append("EMPTY_SKU")
            elif isinstance(val, float):
                # Remove decimal point for float numbers that are actually integers
                prod_reference.append(str(int(val)) if val == int(val) else str(val))
            else:
                prod_reference.append(str(val))
        # Auto-detect based on content if SKU field is present
        identifier_type = detect_identifier_type(prod_reference)
        
        product_variants = get_product_variants_by_identifier(prod_reference, identifier_type, store_id=store_id)
        if not product_variants:
            print("DEBUG: No variants found, returning early")
            return {
                "filename": filename,
                "columns": df.columns.tolist(),
                "has_location": has_location_in_file,
                "has_sale_channel": has_sale_channel_in_file,
                "missing_rows": prod_reference,
                "duplicate_rows": [],
                "ready_to_sync": False,
                "detail": "No matching product variants found in Shopify."
            }
        
            
        # Find missing rows and duplicate rows separately
        missing_rows = []
        duplicate_rows = []
        seen_refs = {}
        found_refs = set()
        
        # Build found_refs set with proper string conversion
        for variant in product_variants:
            val = variant.get(identifier_type)
            if val:
                if pd.isna(val) or val is None:
                    continue
                elif isinstance(val, float):
                    found_refs.add(str(int(val)) if val == int(val) else str(val))
                else:
                    found_refs.add(str(val))
        
        for i, row in enumerate(data_records):
            if identifier_type == "barcode":
                val = row.get("barcode")
            else:
                val = row.get("sku")
            
            # Convert to string with proper handling
            if pd.isna(val) or val is None:
                row_ref = "EMPTY_SKU"
            elif isinstance(val, float):
                row_ref = str(int(val)) if val == int(val) else str(val)
            else:
                row_ref = str(val)
            
            if row_ref not in found_refs and row_ref not in missing_rows:
                # This SKU doesn't exist in Shopify - add to missing list only once
                missing_rows.append(row_ref)
                
            if row_ref in seen_refs and row_ref not in duplicate_rows:
                # This SKU was already processed - it's a duplicate in the file
                duplicate_rows.append(row_ref)
            
            if row_ref not in seen_refs:
                # First occurrence of this SKU
                seen_refs[row_ref] = i
        
        # Return the final result with all information
        ready_to_sync = len(missing_rows) == 0 and len(duplicate_rows) == 0
        return {
            "filename": filename,
            "columns": df.columns.tolist(),
            "total_skus": len(data_records),
            "has_location": has_location_in_file,
            "has_sale_channel": has_sale_channel_in_file,
            "missing_rows": missing_rows,
            "duplicate_rows": duplicate_rows,
            "ready_to_sync": ready_to_sync,
            "detail": "File is ready to sync!" if ready_to_sync else f"File has {len(missing_rows)} missing SKUs and {len(duplicate_rows)} duplicate SKUs."
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking file: {e}")


@router.post("/update-file/{filename}")
async def update_file_with_data(
    request: Request,
    filename: str = Path(..., description="The name of the file to update"),
    location_id: str = Form(None, description="The location ID to add to the file"),
    sale_channel: str = Form(None, description="The sale channel to add to the file")
):
    """Add missing location_id and sale_channel columns to the file"""
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    file_path = os.path.join(resources_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Read the file
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(file_path)
        elif filename.lower().endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Convert all column names to lowercase
        df.columns = df.columns.str.lower()
        
        # Add missing columns
        if location_id and not any(col in ['id sede', 'location_id', 'location'] for col in df.columns):
            df['id sede'] = location_id
            
        if sale_channel and not any(col in ['canali di vendita', 'canale di vendita', 'sale_channel'] for col in df.columns):
            df['canale di vendita'] = sale_channel
        
        # Save the updated file
        if filename.lower().endswith('.csv'):
            df.to_csv(file_path, index=False)
        elif filename.lower().endswith(('.xls', '.xlsx')):
            df.to_excel(file_path, index=False, engine='openpyxl')
        
        return {
            "detail": f"File '{filename}' updated successfully",
            "added_columns": {
                "location_id": location_id if location_id else None,
                "sale_channel": sale_channel if sale_channel else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating file: {e}")


@router.post("/sync/{filename}")
async def sync_file(
    request: Request,
    filename: str = Path(..., description="The name of the file to sync"),
    sync_mode: str = Form("adjust", description="Sync mode: tabula_rasa, adjust, or replace")
):
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    
    # Get store_id from header
    store_id = request.headers.get("X-Selected-Store")
    if not store_id:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)

    if _is_done_file(filename):
        raise HTTPException(
            status_code=400,
            detail="This file is already marked as DONE and cannot be synced again.",
        )

    file_path = os.path.join(resources_dir, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    async def event_generator():
        try:
            # Use pandas to read the file based on extension
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            elif filename.lower().endswith(('.xls', '.xlsx')):
                df = pd.read_excel(file_path)
            else:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Unsupported file type'})}\n\n"
                return
            
            # Transform all column headers to lowercase
            df.columns = df.columns.str.lower()
            
            print(f"DEBUG: DataFrame columns: {df.columns.tolist()}")
            print(f"DEBUG: DataFrame shape: {df.shape}")
            print(f"DEBUG: First row: {df.iloc[0].to_dict() if len(df) > 0 else 'Empty DataFrame'}")
            print(f"DEBUG: Sync mode: {sync_mode}")
            
            # Pass data to the sync function with store_id and sync_mode
            data_records = df.to_dict(orient="records")
            total_records = len(data_records)
            
            yield f"data: {json.dumps({'type': 'start', 'total': total_records, 'mode': sync_mode})}\n\n"
            await asyncio.sleep(0.01)
            
            print(f"DEBUG: Calling get_product_variants_and_sync with {len(data_records)} records, store_id: {store_id}, mode: {sync_mode}")
            
            # Yield progress messages
            yield f"data: {json.dumps({'type': 'status', 'message': f'📦 Loading {total_records} items from file...'})}\n\n"
            await asyncio.sleep(0.1)
            
            yield f"data: {json.dumps({'type': 'status', 'message': '🔍 Searching Shopify catalog...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Call sync synchronously (in a thread to avoid blocking)
            import concurrent.futures
            import time
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    get_product_variants_and_sync, 
                    data_records, 
                    store_id, 
                    sync_mode,
                    store_name,
                )
                
                # Show progress while waiting
                start_time = time.time()
                while not future.done():
                    elapsed = int(time.time() - start_time)
                    if elapsed > 0 and elapsed % 3 == 0:
                        yield f"data: {json.dumps({'type': 'status', 'message': f'⚙️ Processing products... ({elapsed}s elapsed)'})}\n\n"
                    await asyncio.sleep(0.5)
                
                # Wait for completion
                sync_result, missing_rows, duplicate_rows, found_refs = future.result()
            
            print(f"DEBUG: Sync completed. Result: {type(sync_result)}, Missing: {len(missing_rows)}, Found: {len(found_refs)}")

            completed_filename = None
            has_sync_error = isinstance(sync_result, dict) and bool(sync_result.get("error"))
            sync_success = bool(sync_result) and not missing_rows and not duplicate_rows and not has_sync_error

            if sync_success:
                try:
                    completed_filename = _mark_file_as_done(resources_dir, filename)
                    if completed_filename != filename:
                        yield f"data: {json.dumps({'type': 'status', 'message': f'🏁 File marked as DONE: {completed_filename}'})}\n\n"
                        await asyncio.sleep(0.1)
                except Exception as rename_error:
                    print(f"ERROR: Could not mark file as DONE: {rename_error}")
            
            # Show completion progress
            if sync_result:
                yield f"data: {json.dumps({'type': 'status', 'message': f'✅ Matched {len(found_refs)} products in Shopify'})}\n\n"
                await asyncio.sleep(0.1)
                
                mode_messages = {
                    'adjust': '📊 Adjusting inventory quantities...',
                    'replace': '🔄 Replacing inventory quantities...',
                    'tabula_rasa': '🗑️ Resetting inventory to zero, then applying new quantities...'
                }
                yield f"data: {json.dumps({'type': 'status', 'message': mode_messages.get(sync_mode, '📝 Updating inventory...')})}\n\n"
                await asyncio.sleep(0.1)
                
                yield f"data: {json.dumps({'type': 'status', 'message': '💾 Saving changes to Shopify...'})}\n\n"
                await asyncio.sleep(0.1)
            
            # Send final result
            if sync_success:
                final_detail = f"File '{completed_filename or filename}' syncing completed. Marked as DONE."
            elif missing_rows or duplicate_rows:
                final_detail = f"Matching variants found missing in '{filename}'"
            else:
                final_detail = f"File '{filename}' sync completed with warnings."

            result_data = {
                'type': 'complete',
                'detail': final_detail,
                'total_records': total_records,
                'sync_mode': sync_mode,
                'data': sync_result,
                'missing_rows': missing_rows,
                'duplicate_rows': duplicate_rows,
                'found_refs': list(found_refs) if found_refs else [],
                'completed_filename': completed_filename,
            }
            yield f"data: {json.dumps(result_data)}\n\n"
            
        except Exception as e:
            print(f"ERROR: Exception in sync_file: {str(e)}")
            print(f"ERROR: Exception type: {type(e)}")
            import traceback
            print(f"ERROR: Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def sync_with_progress(data_rows, store_id, sync_mode, event_generator_callback=None):
    """Wrapper around get_product_variants_and_sync that provides progress updates"""
    # This is a temporary solution - ideally we'd refactor get_product_variants_and_sync to be async
    # For now, we'll just call it synchronously
    return get_product_variants_and_sync(data_rows, store_id=store_id, sync_mode=sync_mode)
    

@router.post("/uploadFile")
async def upload_file(request: Request, file: UploadFile = File(...)):
    store_name = get_current_store_name(request)
    if not store_name:
        raise HTTPException(status_code=400, detail="No store selected. Please select a store.")
    resources_dir = os.path.join(PROJECT_ROOT, "resources", store_name)
    
    if file and file.filename:
        # Ensure resources directory exists at project root
        os.makedirs(resources_dir, exist_ok=True)

        # Create new filename with date
        date_str = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filename, ext = os.path.splitext(file.filename)
        new_filename = f"{filename}_{date_str}{ext}".lower()
        file_path = os.path.join(resources_dir, new_filename)

        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        return {"type": "categories", "filename": new_filename}

    raise HTTPException(status_code=400, detail="No file uploaded")