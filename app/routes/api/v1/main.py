from datetime import datetime
import os
from fastapi import APIRouter, File, Path, Request, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import pandas as pd

from app.routes.api.v1.add_locations.main import get_product_variants_and_sync

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
async def list_resources():
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
    try:
        files = os.listdir(resources_dir)
        files = [f for f in files if not f.startswith('.')]
    except FileNotFoundError:
        files = []
    return JSONResponse(files)


@router.delete("/resources/{filename}")
async def delete_resource(
    filename: str = Path(..., description="The name of the file to delete")
):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
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
    filename: str = Path(..., description="The name of the file to check")
):
    """Check if the file has required columns and return missing fields"""
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
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
    filename: str = Path(..., description="The name of the file to update"),
    location_id: str = Form(None, description="The location ID to add to the file"),
    sale_channel: str = Form(None, description="The sale channel to add to the file")
):
    """Add missing location_id and sale_channel columns to the file"""
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
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
    filename: str = Path(..., description="The name of the file to sync")
):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
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
        
        # Pass data to the sync function (no global parameters needed now)
        data_records = df.to_dict(orient="records")
        print(f"DEBUG: Calling get_product_variants_and_sync with {len(data_records)} records")
        
        sync_result, missing_sync, found_refs = get_product_variants_and_sync(data_records)
        
        print(f"DEBUG: Sync completed. Result: {type(sync_result)}, Missing: {len(missing_sync)}, Found: {len(found_refs)}")
        
        return {
            "detail": f"File '{filename}' syncing right now!" if sync_result and not missing_sync else f"Matching variants found missing in '{filename}'",
            "data": sync_result,
            "missing_sync": missing_sync,
            "found_refs": found_refs
        }
    except Exception as e:
        print(f"ERROR: Exception in sync_file: {str(e)}")
        print(f"ERROR: Exception type: {type(e)}")
        import traceback
        print(f"ERROR: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error syncing file: {e}")
    

@router.post("/uploadFile")
async def upload_file(file: UploadFile = File(...)):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
    
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