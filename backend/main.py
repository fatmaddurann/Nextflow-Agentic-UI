"""
main.py — FastAPI application entry point for Nextflow-Agentic-UI.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.routes import containers, logs, workflows
from api.routes.logs import websocket_log_stream
from database.database import init_db
from rag.knowledge_base import knowledge_base
from services.ai_agent import on_pipeline_failure
from services.container_manager import container_manager
from services.log_monitor import log_monitor

# Structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger(__name__)

APP_VERSION = "1.0.0"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown logic.
    - Initialize DB tables
    - Index the RAG knowledge base
    - Register AI failure callbacks
    """
    log.info("nextflow_agentic_ui_starting", version=APP_VERSION)

    # 1. Initialize database
    try:
        await init_db()
        log.info("database_initialized")
    except Exception as exc:
        log.error("database_init_failed", error=str(exc))

    # 2. Initialize RAG knowledge base
    try:
        await knowledge_base.initialize()
        log.info("rag_knowledge_base_initialized")
    except Exception as exc:
        log.warning("rag_init_failed", error=str(exc), detail="AI analysis will be limited")

    # 3. Register AI failure callback with log monitor
    log_monitor.on_failure(on_pipeline_failure)
    log.info("ai_failure_callback_registered")

    log.info("nextflow_agentic_ui_ready", host="0.0.0.0", port=8000)

    yield  # application runs

    log.info("nextflow_agentic_ui_shutting_down")


# FastAPI Application
app = FastAPI(
    title="Nextflow-Agentic-UI API",
    description="""
## Intelligent Pipeline Management Interface for Bioinformatics Workflows

Provides REST and WebSocket endpoints for:
- **Pipeline Management**: Start, stop, resume, and monitor Nextflow workflows
- **Container Management**: Docker container lifecycle via Docker SDK
- **Log Streaming**: Real-time pipeline log streaming via WebSocket
- **AI Troubleshooting**: Automated failure analysis with RAG-powered recommendations
    """,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.utcnow()
    response = await call_next(request)
    elapsed = (datetime.utcnow() - start).total_seconds()
    log.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_s=round(elapsed, 4),
    )
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred", "error": str(exc)},
    )


# Include Routers
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(containers.router, prefix="/api/v1")


@app.websocket("/ws/{workflow_id}")
async def ws_endpoint(websocket: WebSocket, workflow_id: str):
    """Top-level WebSocket route alias for the frontend."""
    await websocket_log_stream(websocket, workflow_id)


# Core Endpoints
@app.get("/health", tags=["System"])
async def health_check():
    """
    Comprehensive health check.
    Returns status of all system components.
    """
    db_status = "ok"
    docker_status = await container_manager.health_check()
    rag_status = await knowledge_base.health_check()

    # Check Nextflow binary
    import shutil

    nf_status = "ok" if shutil.which(os.getenv("NEXTFLOW_BINARY", "nextflow")) else "not_found"

    all_ok = all(s == "ok" for s in [db_status, docker_status, rag_status])

    return {
        "status": "ok" if all_ok else "degraded",
        "version": APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_status,
            "docker": docker_status,
            "nextflow": nf_status,
            "rag": rag_status,
        },
    }


@app.get("/", tags=["System"])
async def root():
    """API root — returns service info."""
    return {
        "service": "Nextflow-Agentic-UI API",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "websocket": "ws://host/ws/{workflow_id}",
    }


# Run directly (development)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
        log_level="info",
    )
