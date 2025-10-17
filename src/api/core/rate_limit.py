"""
Module de rate limiting pour l'API
Protection contre les abus et DoS
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse


def get_remote_address_with_forwarded(request: Request) -> str:
    """
    Récupère l'adresse IP réelle du client

    Prend en compte les headers de proxy (X-Forwarded-For, X-Real-IP)
    pour les déploiements derrière reverse proxy

    Args:
        request: Request FastAPI

    Returns:
        Adresse IP du client
    """
    # Vérifier les headers de proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Prendre la première IP (client réel)
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback sur l'IP directe
    return get_remote_address(request)


# Créer le limiter
limiter = Limiter(
    key_func=get_remote_address_with_forwarded,
    default_limits=[],  # Pas de limite par défaut, on spécifie par endpoint
    storage_uri="memory://",  # En mémoire pour développement, utiliser Redis en production
    enabled=True  # Toujours activé
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Handler personnalisé pour les erreurs de rate limit

    Args:
        request: Request FastAPI
        exc: Exception RateLimitExceeded

    Returns:
        JSONResponse avec code 429
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "Trop de requêtes",
            "detail": f"Limite de {exc.detail} dépassée. Veuillez réessayer plus tard.",
            "retry_after": "60 seconds"
        },
        headers={
            "Retry-After": "60"
        }
    )


# Définition des limites par type d'endpoint
class RateLimits:
    """Constantes de rate limiting"""
    # Limites générales
    DEFAULT = "60/minute"  # 60 requêtes par minute pour endpoints non critiques

    # Limites strictes pour uploads
    UPLOAD_SINGLE = "10/minute"  # 10 uploads individuels par minute
    UPLOAD_ASYNC = "20/minute"  # 20 uploads async par minute (moins coûteux)

    # Limites très strictes pour batch
    BATCH = "5/hour"  # 5 batch jobs par heure

    # Limites pour téléchargements
    DOWNLOAD = "30/minute"  # 30 téléchargements par minute

    # Endpoints publics (health, metrics)
    PUBLIC = "120/minute"  # Plus permissif pour monitoring
