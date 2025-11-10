"""
Routes batch
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Body, Depends, Request
from typing import List
from pathlib import Path

from ..models.api_models import (
    BatchJobResponse,
    BatchResultsResponse,
    JobStatus,
    BatchFileResult,
    ConversionMetrics
)
from ..services.batch_service import batch_service
from ..services.storage_service import storage_service
from ..services.job_service import job_service
from ..core.security import verify_api_key
from ..core.rate_limit import limiter, RateLimits

router = APIRouter(prefix="/api/v1/batch", tags=["Batch"])


async def _async_batch_task(batch_id: str, pdf_paths: List[str], taux_douanes: List[float], output_dir: str, workers: int, chassis_configs: List[dict] = None):
    """Tâche de traitement batch asynchrone"""

    # Mettre à jour le status à PROCESSING
    job_service.update_batch(
        batch_id=batch_id,
        status=JobStatus.PROCESSING,
        message=f"Traitement en cours: 0/{len(pdf_paths)} fichiers"
    )

    # Traiter le batch
    results = batch_service.process_files(
        pdf_files=pdf_paths,
        taux_douanes=taux_douanes,
        chassis_configs=chassis_configs or [],
        output_dir=output_dir,
        workers=workers,
        verbose=False
    )

    # Mettre à jour le batch avec les résultats
    job_service.update_batch(
        batch_id=batch_id,
        status=JobStatus.COMPLETED if results['success'] else JobStatus.FAILED,
        processed=results['processed'],
        successful=results['successful'],
        failed=results['failed'],
        message=f"Batch terminé: {results['successful']}/{results['total_files']} réussis",
        results=results
    )


@router.post(
    "",
    response_model=BatchJobResponse,
    summary="Conversion batch de PDFs RFCV",
    description="Upload plusieurs PDFs RFCV et les convertit en parallèle. **Liste de taux douaniers obligatoire** (un par fichier) pour le calcul de l'assurance.",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.BATCH)
async def batch_convert(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Fichiers PDF à convertir"),
    taux_douanes: str = Form(..., description="Liste JSON de taux douaniers (ex: [573.1390, 580.2500])"),
    chassis_configs: str = Form(None, description="Liste JSON de configurations chassis (ex: [{\"generate_chassis\": true, \"quantity\": 180, \"wmi\": \"LZS\", \"year\": 2025}, null]). Optionnel - un par fichier ou null."),
    workers: int = Body(default=4, ge=1, le=8, description="Nombre de workers parallèles")
):
    """
    Conversion batch de plusieurs PDFs

    - **files**: Liste de fichiers PDF à convertir
    - **taux_douanes**: Liste de taux douaniers (un par fichier, format JSON)
    - **chassis_configs**: Liste de configurations chassis (optionnel, un par fichier ou null)
    - **workers**: Nombre de workers pour traitement parallèle (1-8)

    Retourne un batch_id pour suivre la progression
    """
    if not files or len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni"
        )

    # Parser les taux douaniers
    try:
        import json
        taux_list = json.loads(taux_douanes)
        if not isinstance(taux_list, list):
            raise ValueError("taux_douanes doit être une liste JSON")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format taux_douanes invalide: {str(e)}"
        )

    # Valider la cohérence des taux
    if len(taux_list) != len(files):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le nombre de taux ({len(taux_list)}) doit correspondre au nombre de fichiers ({len(files)})"
        )

    # Valider que tous les taux sont positifs
    for i, taux in enumerate(taux_list):
        if not isinstance(taux, (int, float)) or taux <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Taux invalide pour le fichier {i+1}: {taux} (doit être > 0)"
            )

    # Parser les configurations chassis (optionnel)
    chassis_configs_list = []
    if chassis_configs:
        try:
            import json
            chassis_configs_list = json.loads(chassis_configs)
            if not isinstance(chassis_configs_list, list):
                raise ValueError("chassis_configs doit être une liste JSON")

            # Valider que le nombre de configs correspond ou est vide
            if len(chassis_configs_list) > 0 and len(chassis_configs_list) != len(files):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Le nombre de configs chassis ({len(chassis_configs_list)}) doit correspondre au nombre de fichiers ({len(files)}) ou être vide"
                )

            # Valider chaque config non-null
            for i, config in enumerate(chassis_configs_list):
                if config is not None and config.get('generate_chassis'):
                    required_fields = ['quantity', 'wmi', 'year']
                    missing = [f for f in required_fields if f not in config]
                    if missing:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Config chassis {i+1}: champs requis manquants: {', '.join(missing)}"
                        )
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format chassis_configs invalide: {str(e)}"
            )

    # Générer un batch ID
    batch_id = storage_service.generate_batch_id()

    try:
        # Sauvegarder tous les fichiers
        pdf_paths = await storage_service.save_multiple_uploads(files, batch_id)

        # Créer le batch job
        batch = job_service.create_batch(
            batch_id=batch_id,
            total_files=len(pdf_paths),
            pdf_paths=pdf_paths
        )

        # Lancer le traitement en background
        background_tasks.add_task(
            _async_batch_task,
            batch_id=batch_id,
            pdf_paths=pdf_paths,
            taux_douanes=taux_list,
            output_dir=f"output/{batch_id}",
            workers=workers,
            chassis_configs=chassis_configs_list
        )

        return BatchJobResponse(
            batch_id=batch_id,
            status=JobStatus.PENDING,
            total_files=len(files),
            processed=0,
            successful=0,
            failed=0,
            created_at=batch['created_at'],
            completed_at=None,
            message="Batch en cours de traitement"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'initialisation du batch: {str(e)}"
        )


@router.get(
    "/{batch_id}/status",
    response_model=BatchJobResponse,
    summary="Status d'un batch",
    description="Récupère le status et la progression d'un traitement batch",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DEFAULT)
async def get_batch_status(request: Request, batch_id: str):
    """
    Récupère le status d'un batch

    - **batch_id**: ID du batch

    Retourne le status, nombre de fichiers traités, etc.
    """
    batch = job_service.get_batch(batch_id)

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} introuvable"
        )

    return BatchJobResponse(
        batch_id=batch['batch_id'],
        status=batch['status'],
        total_files=batch['total_files'],
        processed=batch['processed'],
        successful=batch['successful'],
        failed=batch['failed'],
        created_at=batch['created_at'],
        completed_at=batch['completed_at'],
        message=batch['message']
    )


@router.get(
    "/{batch_id}/results",
    response_model=BatchResultsResponse,
    summary="Résultats d'un batch",
    description="Récupère les résultats détaillés de tous les fichiers d'un batch",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DEFAULT)
async def get_batch_results(request: Request, batch_id: str):
    """
    Récupère les résultats détaillés d'un batch

    - **batch_id**: ID du batch

    Retourne la liste complète des résultats avec métriques par fichier
    """
    batch = job_service.get_batch(batch_id)

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} introuvable"
        )

    if batch['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch {batch_id} n'est pas terminé (status: {batch['status']})"
        )

    # Convertir les résultats au format API
    batch_results = batch['results']
    file_results = []

    for result in batch_results['results']:
        metrics = None
        if result.metrics:
            metrics = ConversionMetrics(
                items_count=result.metrics.items_count,
                containers_count=result.metrics.containers_count,
                fill_rate=result.metrics.fields_filled_rate,
                warnings_count=len(result.metrics.warnings),
                warnings=result.metrics.warnings,
                xml_valid=result.metrics.xml_valid,
                has_exporter=result.metrics.has_exporter,
                has_consignee=result.metrics.has_consignee,
                processing_time=result.processing_time
            )

        file_results.append(BatchFileResult(
            filename=Path(result.pdf_file).name,
            success=result.success,
            output_file=Path(result.output_file).name if result.output_file else None,
            processing_time=result.processing_time,
            error=result.error_message,
            metrics=metrics
        ))

    return BatchResultsResponse(
        batch_id=batch_id,
        status=batch['status'],
        total_files=batch_results['total_files'],
        successful=batch_results['successful'],
        failed=batch_results['failed'],
        total_time=batch_results['total_time'],
        results=file_results
    )


@router.get(
    "/{batch_id}/report",
    summary="Rapport batch",
    description="Génère et retourne un rapport détaillé du batch (JSON)",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DEFAULT)
async def get_batch_report(request: Request, batch_id: str):
    """
    Génère un rapport détaillé du batch

    - **batch_id**: ID du batch

    Retourne un rapport complet avec statistiques et métriques de qualité
    """
    batch = job_service.get_batch(batch_id)

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} introuvable"
        )

    if batch['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch {batch_id} n'est pas terminé"
        )

    batch_results = batch['results']

    # Construire le rapport
    report = {
        'batch_id': batch_id,
        'generated_at': batch['completed_at'].isoformat() if batch['completed_at'] else None,
        'summary': {
            'total_files': batch_results['total_files'],
            'processed': batch_results['processed'],
            'successful': batch_results['successful'],
            'failed': batch_results['failed'],
            'success_rate': round(
                batch_results['successful'] / batch_results['total_files'] * 100, 2
            ) if batch_results['total_files'] > 0 else 0,
            'total_time': round(batch_results['total_time'], 2),
            'avg_time_per_file': round(batch_results['avg_time_per_file'], 2)
        },
        'quality_metrics': batch_results.get('metrics_summary'),
        'files': []
    }

    # Ajouter les détails de chaque fichier
    for result in batch_results['results']:
        file_info = {
            'file': Path(result.pdf_file).name,
            'success': result.success,
            'output_file': Path(result.output_file).name if result.output_file else None,
            'processing_time': round(result.processing_time, 3),
            'error': result.error_message if not result.success else None
        }

        if result.metrics:
            file_info['metrics'] = {
                'items_count': result.metrics.items_count,
                'containers_count': result.metrics.containers_count,
                'fill_rate': round(result.metrics.fields_filled_rate, 2),
                'warnings_count': len(result.metrics.warnings),
                'warnings': result.metrics.warnings,
                'xml_valid': result.metrics.xml_valid,
                'has_exporter': result.metrics.has_exporter,
                'has_consignee': result.metrics.has_consignee
            }

        report['files'].append(file_info)

    return report
