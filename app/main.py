"""
DockView — Zero-config Docker Database Viewer
Main application entry point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import databases, containers, schema
from app.services.docker_inspector import DockerInspector
from app.services.event_stream import router as sse_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dockview")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("🚀 DockView starting up...")
    inspector = DockerInspector()
    app.state.inspector = inspector
    await inspector.start()
    logger.info("✅ Docker inspector initialized")
    yield
    logger.info("🛑 DockView shutting down...")
    await inspector.stop()


app = FastAPI(
    title="DockView",
    description="Zero-config Docker Database Viewer",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# API Routers
app.include_router(databases.router, prefix="/api")
app.include_router(containers.router, prefix="/api")
app.include_router(schema.router, prefix="/api")
app.include_router(sse_router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main SPA shell."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
