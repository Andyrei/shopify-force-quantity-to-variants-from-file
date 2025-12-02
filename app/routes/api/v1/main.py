from datetime import datetime
import os
import toml
from fastapi import APIRouter, File, Path, Request, UploadFile, HTTPException, Form, Cookie
from fastapi.responses import JSONResponse
import pandas as pd

from app.routes.api.v1.add_locations.main import get_product_variants_and_sync

# Load config once at module level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
config = toml.load(os.path.join(PROJECT_ROOT, "config_stores.toml"))

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
    except FileNotFoundError:
        files = []
    return JSONResponse(files)


@router.delete("/resources/{filename}")
async def delete_resource(
    request: Request,
    filename: str = Path(..., description="The name of the file to delete")
):
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


@router.get("/check/{filename}")
async def check_file_structure(
    request: Request,
    filename: str = Path(..., description="The name of the file to check")
):
    """Check if the file has required columns and return missing fields"""
    store_name = get_current_store_name(request)
    if not store_name:
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
        
        missing_fields = []
        if not has_location_in_file:
            missing_fields.append("location_id")
        if not has_sale_channel_in_file:
            missing_fields.append("sale_channel")
        
        return {
            "filename": filename,
            "columns": df.columns.tolist(),
            "has_location": has_location_in_file,
            "has_sale_channel": has_sale_channel_in_file,
            "missing_fields": missing_fields,
            "ready_to_sync": len(missing_fields) == 0
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
        
        # Transform all column headers to lowercase
        df.columns = df.columns.str.lower()
        
        print(f"DEBUG: DataFrame columns: {df.columns.tolist()}")
        print(f"DEBUG: DataFrame shape: {df.shape}")
        print(f"DEBUG: First row: {df.iloc[0].to_dict() if len(df) > 0 else 'Empty DataFrame'}")
        print(f"DEBUG: Sync mode: {sync_mode}")
        
        # Pass data to the sync function with store_id and sync_mode
        data_records = df.to_dict(orient="records")
        print(f"DEBUG: Calling get_product_variants_and_sync with {len(data_records)} records, store_id: {store_id}, mode: {sync_mode}")
        
        sync_result, missing_rows, duplicate_rows, found_refs = get_product_variants_and_sync(data_records, store_id=store_id, sync_mode=sync_mode)
        
        print(f"DEBUG: Sync completed. Result: {type(sync_result)}, Missing: {len(missing_rows)}, Found: {len(found_refs)}")
        
        return {
            "detail": f"File '{filename}' syncing right now!" if sync_result and not missing_rows else f"Matching variants found missing in '{filename}'",
            "total_records": len(data_records),
            "sync_mode": sync_mode,
            "data": sync_result,
            "missing_rows": missing_rows,
            "duplicate_rows": duplicate_rows,
            "found_refs": found_refs
        }
    except Exception as e:
        print(f"ERROR: Exception in sync_file: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error syncing file: {e}")
    

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