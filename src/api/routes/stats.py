"""
Routes de statistiques d'utilisation
"""
from fastapi import APIRouter, Depends

from ..services.usage_stats_service import get_usage_stats
from ..core.security import verify_api_key

router = APIRouter(prefix="/api/v1/stats", tags=["Statistics"])


@router.get(
    "",
    summary="Statistiques d'utilisation",
    description="Retourne toutes les statistiques d'utilisation persistantes de l'API",
    dependencies=[Depends(verify_api_key)]
)
async def get_usage_stats_endpoint():
    """
    Statistiques d'utilisation complètes

    Retourne les compteurs persistants de conversions, batches, châssis et requêtes
    """
    return get_usage_stats().get_stats()


@router.get(
    "/conversions",
    summary="Statistiques de conversions",
    description="Retourne les statistiques de conversions uniquement",
    dependencies=[Depends(verify_api_key)]
)
async def get_conversion_stats():
    """
    Statistiques de conversions

    Retourne total, succès, échecs, sync/async, avec châssis, avec paiement
    """
    return get_usage_stats().get_conversion_stats()


@router.get(
    "/requests",
    summary="Statistiques de requêtes",
    description="Retourne les statistiques de requêtes HTTP",
    dependencies=[Depends(verify_api_key)]
)
async def get_request_stats():
    """
    Statistiques de requêtes HTTP

    Retourne total, répartition par méthode et par code de status
    """
    return get_usage_stats().get_request_stats()
