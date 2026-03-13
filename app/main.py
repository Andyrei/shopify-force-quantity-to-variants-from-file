import os
import uvicorn
import toml
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routes.api import v1


app = FastAPI(
    version="0.0.1", 
    title="Custom Quantity by sku", 
    description="",
    docs_url="/docs",
    root_path=os.getenv("ROOT_PATH", ""),
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
    # Load stores from config
    config = toml.load("config_stores.toml")
    stores = config.get("stores", {})

    # Try to get selected store from header (from localStorage-driven fetch)
    selected_store_id = req.headers.get("X-Selected-Store")
    current_store_name = ""
    current_store_display = ""

    if selected_store_id and selected_store_id in stores:
        current_store_name = stores[selected_store_id].get("STORE_NAME", "")
        current_store_display = current_store_name.split("-")[1].upper() if "-" in current_store_name else current_store_name.upper()
    else:
        # Fallback to environment variable
        env_store = os.getenv("STORE_NAME", "")
        if env_store:
            current_store_name = env_store
            current_store_display = env_store.split("-")[1].upper() if "-" in env_store else env_store.upper()

    return {
        "request": req,
        "store_name": current_store_display,
        "stores": stores,
        "current_store": current_store_name,
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