"""
Module de sécurité - Authentification API
"""
import secrets
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from .config import settings

# Schéma d'authentification par API Key
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """
    Vérifie la validité de l'API key

    Args:
        api_key: Clé API fournie dans le header X-API-Key

    Returns:
        Clé API validée

    Raises:
        HTTPException: Si la clé est invalide ou manquante
    """
    # Si l'authentification n'est pas requise, on passe
    if not settings.require_authentication:
        return "bypass"

    # Vérifier que la clé est fournie
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key manquante. Fournir X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Récupérer les clés valides depuis la config
    valid_keys = []
    if settings.api_keys:
        # Support multi-clés séparées par virgules
        valid_keys = [key.strip() for key in settings.api_keys.split(',') if key.strip()]

    if not valid_keys:
        # Si aucune clé configurée mais auth requise = erreur config
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration serveur incorrecte: aucune API key configurée"
        )

    # Comparer avec protection contre timing attacks
    # secrets.compare_digest() pour éviter les attaques par timing
    is_valid = any(
        secrets.compare_digest(api_key, valid_key)
        for valid_key in valid_keys
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalide",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


def generate_api_key() -> str:
    """
    Génère une nouvelle API key sécurisée

    Returns:
        Clé API aléatoire (URL-safe, 32 bytes = 256 bits de sécurité)

    Usage:
        python -c "from src.api.core.security import generate_api_key; print(generate_api_key())"
    """
    return secrets.token_urlsafe(32)
