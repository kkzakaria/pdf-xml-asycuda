"""
Application FastAPI principale
API REST pour la conversion PDF RFCV → XML ASYCUDA
"""
import uuid
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import asyncio

from .core.config import settings
from .core.dependencies import startup_tasks
from .core.background import task_manager
from .core.rate_limit import limiter, rate_limit_exceeded_handler
from .core.logging_config import configure_logging
from slowapi.errors import RateLimitExceeded
from .routes import convert, batch, files, health, chassis

# Configuration centralisée du logging
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle events pour l'application

    Gère le startup et shutdown de l'API
    """
    # Startup
    logger.info("=" * 70)
    logger.info("Démarrage de l'API %s", settings.api_title)
    logger.info("=" * 70)

    # Exécuter les tâches de démarrage
    startup_tasks()

    # Lancer le nettoyage périodique en background
    cleanup_task = asyncio.create_task(task_manager.periodic_cleanup())

    logger.info("API prête sur http://%s:%s", settings.host, settings.port)
    logger.info("Documentation: http://%s:%s/docs", settings.host, settings.port)
    logger.info("Health check: http://%s:%s/api/v1/health", settings.host, settings.port)
    logger.info("=" * 70)

    yield

    # Shutdown
    logger.info("Arrêt de l'API...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# Créer l'application FastAPI
app = FastAPI(
    title=settings.api_title,
    version=settings.version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    # Configuration Swagger UI pour l'authentification
    swagger_ui_parameters={
        "persistAuthorization": True,  # Persiste la clé API entre les rechargements
    }
)

# Ajouter le rate limiter à l'app
app.state.limiter = limiter


# Customiser le schéma OpenAPI pour ajouter la sécurité API Key
def custom_openapi():
    """
    Customise le schéma OpenAPI pour supporter l'authentification API Key
    dans Swagger UI
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Ajouter le security scheme pour API Key
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "Clé API pour l'authentification. "
                "Pour obtenir une clé API, veuillez contacter l'administrateur du service. "
                "Consultez la documentation pour plus d'informations sur l'utilisation de l'API."
            )
        }
    }

    # Marquer tous les endpoints protégés dans la documentation
    # (FastAPI le fait automatiquement via Depends(verify_api_key))

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins else ["http://localhost:3000"],
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# Exception handlers sécurisés

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handler pour les erreurs de rate limit"""
    return rate_limit_exceeded_handler(request, exc)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handler pour les exceptions HTTP

    Logs les erreurs sans exposer les détails sensibles
    """
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail} - "
        f"path={request.url.path}, method={request.method}, "
        f"ip={request.client.host if request.client else 'unknown'}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler pour les erreurs de validation Pydantic

    Logs les erreurs de validation sans exposer les détails internes
    """
    logger.warning(
        f"Validation error: {exc.errors()} - "
        f"path={request.url.path}, ip={request.client.host if request.client else 'unknown'}"
    )

    return JSONResponse(
        status_code=422,
        content={
            "error": "Erreur de validation",
            "detail": "Les données fournies sont invalides",
            "errors": exc.errors() if settings.debug else None
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handler global pour les exceptions non gérées

    En production: retourne un message générique avec error_id pour tracking
    En développement: inclut les détails de l'exception
    """
    # Générer un ID unique pour tracking
    error_id = str(uuid.uuid4())

    # Logger l'exception complète avec stacktrace
    logger.error(
        f"Unhandled exception [{error_id}]: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={
            'error_id': error_id,
            'path': request.url.path,
            'method': request.method,
            'client_host': request.client.host if request.client else 'unknown'
        }
    )

    # Réponse selon le mode debug
    if settings.debug:
        # Mode développement: inclure les détails
        return JSONResponse(
            status_code=500,
            content={
                "error": "Erreur interne du serveur",
                "error_id": error_id,
                "type": type(exc).__name__,
                "detail": str(exc)
            }
        )
    else:
        # Mode production: message générique seulement
        return JSONResponse(
            status_code=500,
            content={
                "error": "Erreur interne du serveur",
                "error_id": error_id,
                "message": "Une erreur inattendue s'est produite. Veuillez contacter le support avec cet ID d'erreur."
            }
        )


# Inclure les routers
app.include_router(convert.router)
app.include_router(batch.router)
app.include_router(files.router)
app.include_router(health.router)
app.include_router(chassis.router)


# Route racine
@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint racine

    Retourne les informations de base sur l'API
    """
    return {
        "name": settings.api_title,
        "version": settings.version,
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
            },
            "chassis": {
                "generate": "POST /api/v1/chassis/generate",
                "generate_json": "POST /api/v1/chassis/generate/json",
                "sequences": "GET /api/v1/chassis/sequences"
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
