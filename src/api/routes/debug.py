"""
Route de debug temporaire pour diagnostiquer la configuration
À SUPPRIMER après diagnostic!
"""
import os
from fastapi import APIRouter
from ..core.config import settings

router = APIRouter(tags=["Debug"])


@router.get(
    "/api/v1/debug/config",
    summary="[DEBUG] Vérifier la configuration",
    description="⚠️ ENDPOINT DE DEBUG TEMPORAIRE - À supprimer après diagnostic"
)
async def debug_config():
    """
    Endpoint de debug pour vérifier la configuration
    NE PAS UTILISER EN PRODUCTION
    """
    # Vérifier les variables d'environnement
    env_vars = {
        "API_KEYS_exists": "API_KEYS" in os.environ,
        "API_KEYS_length": len(os.environ.get("API_KEYS", "")) if "API_KEYS" in os.environ else 0,
        "KEYS_exists": "KEYS" in os.environ,
        "settings_api_keys_length": len(settings.api_keys) if settings.api_keys else 0,
        "settings_require_authentication": settings.require_authentication,
        "settings_rate_limit_enabled": settings.rate_limit_enabled,
        "all_API_env_vars": [k for k in os.environ.keys() if k.startswith("API_")]
    }

    return {
        "status": "debug",
        "environment_check": env_vars,
        "message": "⚠️ Cet endpoint doit être supprimé après diagnostic"
    }
