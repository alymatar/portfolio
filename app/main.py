"""FastAPI app: server-rendered portfolio pages plus a small JSON API."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .content import Project, load_content

APP_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Aly Tamer Matar · Portfolio",
    version=__version__,
    description="Portfolio site with a small JSON API.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"c": load_content(), "year": date.today().year, "version": __version__},
    )


@app.get("/api/health", tags=["api"])
def health() -> dict:
    """Liveness check used by Docker and CI."""
    return {"status": "ok", "version": __version__}


@app.get("/api/projects", response_model=list[Project], tags=["api"])
def list_projects() -> list[Project]:
    """All projects shown on the site."""
    return load_content().projects


@app.get("/api/projects/{slug}", response_model=Project, tags=["api"])
def get_project(slug: str) -> Project:
    """One project by its slug."""
    for project in load_content().projects:
        if project.slug == slug:
            return project
    raise HTTPException(status_code=404, detail="Project not found")


@app.exception_handler(StarletteHTTPException)
async def not_found_page(request: Request, exc: StarletteHTTPException):
    """HTML 404 page for browsers; JSON errors for the API."""
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        return templates.TemplateResponse(
            request,
            "404.html",
            {"c": load_content(), "year": date.today().year},
            status_code=404,
        )
    from fastapi.exception_handlers import http_exception_handler

    return await http_exception_handler(request, exc)
