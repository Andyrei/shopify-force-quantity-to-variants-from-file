import uvicorn
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
)

app.mount("/static", StaticFiles(directory="app/views/static"), name="static")
templates = Jinja2Templates(directory="app/views/templates")

app.include_router(
    v1.router,
    prefix="/api",
    tags=["Version 1"],
    responses={404: {"description": "Not found"}}
)


@app.get("/", response_class=HTMLResponse)
def read_root(req: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {
        "request": req,
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")