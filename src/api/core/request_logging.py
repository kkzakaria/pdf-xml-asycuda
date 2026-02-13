"""
Middleware de logging des requêtes HTTP
"""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Chemins à exclure du logging (bruit)
SKIP_PATHS = {"/api/v1/health"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware qui log chaque requête HTTP avec durée, status et IP.
    Enregistre également les statistiques via UsageStatsService.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method

        # Skip les chemins bruyants
        if path in SKIP_PATHS:
            return await call_next(request)

        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        status_code = response.status_code
        client_ip = request.client.host if request.client else "unknown"

        # Log level selon le status code
        if status_code < 400:
            logger.info(
                "%s %s — %d — %.0fms — %s",
                method, path, status_code, duration_ms, client_ip
            )
        else:
            logger.warning(
                "%s %s — %d — %.0fms — %s",
                method, path, status_code, duration_ms, client_ip
            )

        # Tracking stats
        try:
            from ..core.config import settings
            if settings.stats_enabled:
                from ..services.usage_stats_service import get_usage_stats
                get_usage_stats().track_request(method, status_code)
        except Exception as e:
            logger.debug("Erreur tracking stats requête: %s", e)

        return response
