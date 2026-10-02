# app/main.py
"""
ClauseGuard - AI-Powered Contract Risk Analysis & Guardian.

Main FastAPI application entrypoint.
Configures CORS, registers API routers, and serves the frontend dashboard.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.routes.documents import router as documents_router
from app.routes.chat import router as chat_router

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered legal contract risk analysis tool for Pakistan.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST API Routers
app.include_router(documents_router)
app.include_router(chat_router)

# Mount frontend directory for static assets if needed
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health probe endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get("/", tags=["UI / Root"])
async def root():
    """
    Serves the web dashboard UI if available, else returns API info.
    """
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)

    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }