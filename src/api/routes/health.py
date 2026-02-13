"""
Routes health et métriques
"""
from fastapi import APIRouter, Depends
from datetime import datetime
import time

from ..models.api_models import HealthResponse, MetricsResponse
from ..services.job_service import job_service
from ..core.config import settings
from ..core.security import verify_api_key

router = APIRouter(tags=["Health"])

# Timestamp de démarrage
_start_time = time.time()


@router.api_route(
    "/api/v1/health",
    methods=["GET", "HEAD"],
    response_model=HealthResponse,
    summary="Health check",
    description="Vérifie l'état de santé de l'API"
)
async def health_check():
    """
    Health check de l'API

    Retourne le status, version et uptime
    """
    uptime = time.time() - _start_time
    total_jobs = len(job_service.get_all_jobs()) + len(job_service.get_all_batches())

    return HealthResponse(
        status="healthy",
        version=settings.version,
        uptime_seconds=uptime,
        total_jobs=total_jobs
    )


@router.get(
    "/api/v1/metrics",
    response_model=MetricsResponse,
    summary="Métriques système",
    description="Récupère les métriques globales de conversion",
    dependencies=[Depends(verify_api_key)]
)
async def get_system_metrics():
    """
    Métriques système

    Retourne les statistiques globales de toutes les conversions
    """
    jobs = job_service.get_all_jobs()
    batches = job_service.get_all_batches()

    # Calculer les statistiques sur les jobs
    total_conversions = len(jobs)
    successful = sum(1 for job in jobs if job.get('result', {}).get('success', False))
    failed = total_conversions - successful

    # Métriques moyennes
    avg_processing_time = 0.0
    avg_fill_rate = 0.0
    total_items = 0
    total_containers = 0

    successful_jobs = [job for job in jobs if job.get('result', {}).get('success', False)]

    if successful_jobs:
        processing_times = []
        fill_rates = []

        for job in successful_jobs:
            result = job.get('result', {})
            metrics = result.get('metrics')

            if metrics:
                processing_times.append(metrics.total_time)
                fill_rates.append(metrics.fields_filled_rate)
                total_items += metrics.items_count
                total_containers += metrics.containers_count

        if processing_times:
            avg_processing_time = sum(processing_times) / len(processing_times)
        if fill_rates:
            avg_fill_rate = sum(fill_rates) / len(fill_rates)

    success_rate = (successful / total_conversions * 100) if total_conversions > 0 else 0.0

    return MetricsResponse(
        total_conversions=total_conversions,
        successful=successful,
        failed=failed,
        success_rate=round(success_rate, 2),
        avg_processing_time=round(avg_processing_time, 2),
        avg_fill_rate=round(avg_fill_rate, 2),
        total_items=total_items,
        total_containers=total_containers
    )


@router.get(
    "/api/v1/metrics/{job_id}",
    summary="Métriques d'un job",
    description="Récupère les métriques détaillées d'un job spécifique",
    dependencies=[Depends(verify_api_key)]
)
async def get_job_metrics(job_id: str):
    """
    Métriques d'un job spécifique

    - **job_id**: ID du job

    Retourne les métriques détaillées de la conversion
    """
    job = job_service.get_job(job_id)

    if not job:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )

    result = job.get('result', {})
    metrics = result.get('metrics')

    if not metrics:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Métriques non disponibles pour le job {job_id}"
        )

    return {
        'job_id': job_id,
        'filename': job['filename'],
        'success': result.get('success', False),
        'processing_time': metrics.total_time,
        'items_count': metrics.items_count,
        'containers_count': metrics.containers_count,
        'fill_rate': metrics.fields_filled_rate,
        'xml_valid': metrics.xml_valid,
        'has_exporter': metrics.has_exporter,
        'has_consignee': metrics.has_consignee,
        'warnings': metrics.warnings
    }
