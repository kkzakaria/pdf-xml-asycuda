"""
Routes batch
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, BackgroundTasks, Body
from typing import List
from pathlib import Path

from ..models.api_models import (
    BatchJobResponse,
    BatchResultsResponse,
    JobStatus,
    BatchFileResult,
    ConversionMetrics,
    BatchConvertRequest
)
from ..services.batch_service import batch_service
from ..services.storage_service import storage_service
from ..services.job_service import job_service

router = APIRouter(prefix="/api/v1/batch", tags=["Batch"])


async def _async_batch_task(batch_id: str, pdf_paths: List[str], output_dir: str, workers: int):
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
    summary="Conversion batch",
    description="Upload plusieurs PDFs RFCV et les convertit en parallèle"
)
async def batch_convert(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Fichiers PDF à convertir"),
    workers: int = Body(default=4, ge=1, le=8, description="Nombre de workers parallèles")
):
    """
    Conversion batch de plusieurs PDFs

    - **files**: Liste de fichiers PDF à convertir
    - **workers**: Nombre de workers pour traitement parallèle (1-8)

    Retourne un batch_id pour suivre la progression
    """
    if not files or len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni"
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
            output_dir=f"output/{batch_id}",
            workers=workers
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
    description="Récupère le status et la progression d'un traitement batch"
)
async def get_batch_status(batch_id: str):
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
    description="Récupère les résultats détaillés de tous les fichiers d'un batch"
)
async def get_batch_results(batch_id: str):
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
    description="Génère et retourne un rapport détaillé du batch (JSON)"
)
async def get_batch_report(batch_id: str):
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
