"""
Wedding Seat Arrangement System - FastAPI Backend
Main application entry point
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from app.core.config import settings
from app.core.db import engine, Base
from app.api import routes_admin, routes_guest, routes_public, ws

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    yield
    logger.info("Application shutdown")

# Create FastAPI application
app = FastAPI(
    title="Wedding Seat Arrangement System",
    description="Production-ready backend for wedding seating management",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Include routers
app.include_router(routes_public.router, tags=["public"])
app.include_router(routes_guest.router, prefix="/guest", tags=["guest"])
app.include_router(routes_admin.router, prefix="/admin", tags=["admin"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint with basic info"""
    return templates.TemplateResponse("guest_portal.html", {
        "request": request,
        "title": "Wedding Seating System"
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin panel for creating events and uploading Excel files"""
    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "title": "Wedding Admin Panel"
    })

# Note: Run this ASGI app directly with Uvicorn or Hypercorn. For Gunicorn,
# use `uvicorn.workers.UvicornWorker` instead of wrapping the app.

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
