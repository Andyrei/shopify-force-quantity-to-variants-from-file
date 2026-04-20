import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes.api import v1
from app.database import ensure_db_initialized, run_migration_if_needed, add_title_column_if_needed, get_all_stores


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_db_initialized()
    await add_title_column_if_needed()
    migration_result = await run_migration_if_needed()
    if migration_result.get("imported", 0) > 0:
        print(f"Migration: Imported {migration_result['imported']} stores from TOML")
    elif migration_result.get("skipped", 0) > 0:
        print(f"Migration: Skipped {migration_result['skipped']} existing stores")
    
    stores_list = await get_all_stores()
    app.state.stores = {s["store_id"]: s for s in stores_list}
    print(f"Loaded {len(app.state.stores)} stores into app state")
    
    yield


app = FastAPI(
    version="0.0.1", 
    title="Custom Quantity by sku", 
    description="",
    docs_url="/docs",
    root_path=os.getenv("ROOT_PATH", ""),
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/views/static"), name="static")
templates = Jinja2Templates(directory="app/views/templates")

app.include_router(
    v1.router,
    prefix="/api",
    tags=["Version 1"],
    responses={404: {"description": "Not found"}}
)


def _build_page_context(req: Request, page: str) -> dict:
    stores = getattr(req.app.state, "stores", {})

    # Check URL query param first, then header, then localStorage fallback handled client-side
    selected_store_id = req.query_params.get("store") or req.headers.get("X-Selected-Store")
    current_store = ""

    if selected_store_id and selected_store_id in stores:
        store = stores[selected_store_id]
        # Use title if available, otherwise use store_name
        current_store = store.get("title", "") or store.get("store_name", "")
    else:
        env_store = os.getenv("STORE_NAME", "")
        if env_store:
            # Try to find title from stores
            for sid, store in stores.items():
                if store.get("store_name") == env_store:
                    current_store = store.get("title", "") or env_store
                    break
            if not current_store:
                current_store = env_store.split("-")[1].title() if "-" in env_store else env_store.title()

    return {
        "request": req,
        "store_name": current_store,
        "stores": stores,
        "current_store": current_store,
        "page": page,
    }


@app.get("/", response_class=HTMLResponse)
def read_root(req: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", _build_page_context(req, page="home"))


@app.get("/logs", response_class=HTMLResponse)
def read_logs(req: Request) -> HTMLResponse:
    return templates.TemplateResponse("logs.html", _build_page_context(req, page="logs"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999, log_level="info")