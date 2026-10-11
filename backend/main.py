import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.config.settings import settings
from backend.database.init_db import init_db
from backend.routes import (
    auth_router,
    profile_router,
    interviews_router,
    evaluation_router,
    dashboard_router,
    performance_router,
    resume_analysis_router,
    coding_router,
    analytics_router,
    ai_router,
    users_router,
    recommendations_router,
    voice_router
)

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    logger.info("Initializing Database tables (PostgreSQL/SQLAlchemy)...")
    init_db()
    yield
    # Shutdown
    logger.info("Shutting down API server...")

app = FastAPI(
    title="InterviewAI — AI Interview Preparation Assistant API",
    description="Full-stack AI Mock Interview platform with adaptive questions, weighted rubric evaluations, candidate dashboard, and analytics.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(interviews_router)
app.include_router(evaluation_router)
app.include_router(dashboard_router)
app.include_router(performance_router)
app.include_router(resume_analysis_router)
app.include_router(coding_router)
app.include_router(analytics_router)
app.include_router(ai_router)
app.include_router(users_router)
app.include_router(recommendations_router)
app.include_router(voice_router)

# Directory configurations
backend_dir = os.path.dirname(__file__)
static_dir = os.path.abspath(os.path.join(backend_dir, "static"))
frontend_dir = os.path.abspath(os.path.join(backend_dir, "..", "frontend"))

# Mount SPA static assets (/assets) from backend/static/assets
spa_assets_dir = os.path.join(static_dir, "assets")
if os.path.exists(spa_assets_dir):
    app.mount("/assets", StaticFiles(directory=spa_assets_dir), name="spa_assets")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount multi-page HTML frontend assets
if os.path.exists(frontend_dir):
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")
    css_dir = os.path.join(frontend_dir, "css")
    js_dir = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/css", StaticFiles(directory=css_dir), name="css")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="js")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "app": "InterviewAI — AI Interview Preparation Assistant",
        "env": settings.ENV,
        "database": "PostgreSQL / SQLAlchemy",
        "ai_key_configured": bool(settings.GENAI_API_KEY or os.getenv("GENAI_API_KEY") or settings.GROQ_API_KEY)
    }

# Serve React SPA Studio
@app.get("/app")
@app.get("/app/{full_path:path}")
async def serve_react_spa(full_path: str = ""):
    app_html = os.path.join(static_dir, "app.html")
    if os.path.exists(app_html):
        return FileResponse(app_html)
    index_html = os.path.join(static_dir, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    return JSONResponse(status_code=404, content={"detail": "React SPA not built yet. Run 'npm run build' in frontend/."})

# Serve multi-page HTML pages
@app.get("/{page_name}.html")
async def serve_html_page(page_name: str):
    file_path = os.path.join(frontend_dir, f"{page_name}.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"detail": f"Page '{page_name}.html' not found"})

@app.get("/")
async def root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "InterviewAI API",
        "status": "running",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.HOST, port=settings.PORT, reload=True)
