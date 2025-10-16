"""
Application FastAPI principale
API REST pour la conversion PDF RFCV → XML ASYCUDA
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio

from .core.config import settings
from .core.dependencies import startup_tasks
from .core.background import task_manager
from .routes import convert, batch, files, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle events pour l'application

    Gère le startup et shutdown de l'API
    """
    # Startup
    print(f"\n{'='*70}")
    print(f"🚀 Démarrage de l'API {settings.api_title}")
    print(f"{'='*70}")

    # Exécuter les tâches de démarrage
    startup_tasks()

    # Lancer le nettoyage périodique en background
    cleanup_task = asyncio.create_task(task_manager.periodic_cleanup())

    print(f"✓ API prête sur http://{settings.host}:{settings.port}")
    print(f"✓ Documentation: http://{settings.host}:{settings.port}/docs")
    print(f"✓ Health check: http://{settings.host}:{settings.port}/api/v1/health")
    print(f"{'='*70}\n")

    yield

    # Shutdown
    print("\n🛑 Arrêt de l'API...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# Créer l'application FastAPI
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Exception handler global
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handler global pour les exceptions non gérées"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne du serveur",
            "detail": str(exc)
        }
    )


# Inclure les routers
app.include_router(convert.router)
app.include_router(batch.router)
app.include_router(files.router)
app.include_router(health.router)


# Route racine
@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint racine

    Retourne les informations de base sur l'API
    """
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": {
            "conversion": {
                "sync": "POST /api/v1/convert",
                "async": "POST /api/v1/convert/async",
                "status": "GET /api/v1/convert/{job_id}",
                "result": "GET /api/v1/convert/{job_id}/result",
                "download": "GET /api/v1/convert/{job_id}/download"
            },
            "batch": {
                "convert": "POST /api/v1/batch",
                "status": "GET /api/v1/batch/{batch_id}/status",
                "results": "GET /api/v1/batch/{batch_id}/results",
                "report": "GET /api/v1/batch/{batch_id}/report"
            },
            "files": {
                "download": "GET /api/v1/files/{file_id}/xml",
                "metadata": "GET /api/v1/files/{file_id}/metadata"
            },
            "monitoring": {
                "health": "GET /api/v1/health",
                "metrics": "GET /api/v1/metrics",
                "job_metrics": "GET /api/v1/metrics/{job_id}"
            }
        }
    }


# Point d'entrée pour exécution directe
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
