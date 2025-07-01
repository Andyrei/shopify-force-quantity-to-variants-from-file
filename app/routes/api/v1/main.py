import base64
from datetime import datetime
import os
from fastapi import APIRouter, File, Path, Request, Response, UploadFile, HTTPException
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
        
        # Pass both columns and rows (as records) to the sync function
        sync_result, missing_sync = get_product_variants_and_sync(df.to_dict(orient="records"))
        return {
            "detail": f"File '{filename}' syncing right now!",
            "data": sync_result,
            "missing_sync": missing_sync
            
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing file: {e}")
    

@router.post("/uploadFile")
async def upload_file(file: UploadFile = File(...)):
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    resources_dir = os.path.join(PROJECT_ROOT, "resources")
    
    if file and file.filename:
            # Ensure resources directory exists at project root
            os.makedirs(resources_dir, exist_ok=True)

            # Create new filename with date
            date_str = datetime.now().strftime("%d-%m-%Y_%H:%M:%S")
            filename, ext = os.path.splitext(file.filename)
            new_filename = f"{filename}_{date_str}{ext}".lower()
            file_path = os.path.join(resources_dir, new_filename)

            # Save file
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())

            return {"type": "categories", "filename": new_filename}

    raise HTTPException(status_code=400, detail="No file uploaded")