"""
Routes de conversion
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse
from pathlib import Path

from ..models.api_models import (
    ConvertResponse,
    ConvertAsyncResponse,
    JobStatusResponse,
    JobStatus,
    ConversionMetrics
)
from ..services.conversion_service import conversion_service
from ..services.storage_service import storage_service
from ..services.job_service import job_service
from ..core.dependencies import validate_upload_file
from ..core.security import verify_api_key
from ..core.rate_limit import limiter, RateLimits

router = APIRouter(prefix="/api/v1/convert", tags=["Conversion"])


@router.post(
    "",
    response_model=ConvertResponse,
    summary="Conversion synchrone PDF → XML ASYCUDA",
    description="Upload un PDF RFCV et retourne le XML ASYCUDA immédiatement. **Taux douanier obligatoire** pour le calcul de l'assurance. Rapport de paiement optionnel.",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def convert_pdf(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: Optional[str] = Form(None, description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J). Optionnel - généré après paiement des taxes.")
):
    """
    Conversion synchrone PDF → XML

    - **file**: Fichier PDF à convertir (max 50MB)
    - **taux_douane**: Taux de change douanier pour calcul assurance (format: 573.1390)
      - **Obligatoire** : Communiqué par la douane avant chaque conversion
      - **Format** : Point (`.`) comme séparateur décimal (ex: 573.1390)
    - **rapport_paiement**: Numéro de rapport de paiement/quittance Trésor Public (optionnel)
      - **Format** : 8 caractères alphanumériques (ex: 25P2003J)
      - **Quand fournir** : Si vous avez déjà le numéro de quittance du Trésor
      - **Workflow** : Généré APRÈS paiement des taxes, donc rarement disponible lors de la conversion initiale
      - **Champ XML** : Remplit `Deffered_payment_reference` dans la section `<Financial>`

    Retourne le résultat immédiatement avec les métriques
    """
    # Valider le fichier (fonction async maintenant)
    file = await validate_upload_file(file)

    # Générer un job ID
    job_id = storage_service.generate_job_id()

    try:
        # Sauvegarder le fichier uploadé
        pdf_path = await storage_service.save_upload(file, job_id)

        # Générer le chemin de sortie
        output_path = storage_service.get_output_path(pdf_path)

        # Convertir
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement
        )

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error_message'] or "Erreur de conversion"
            )

        # Construire la réponse avec métriques
        metrics_obj = result['metrics']
        metrics = None
        if metrics_obj:
            metrics = ConversionMetrics(
                items_count=metrics_obj.items_count,
                containers_count=metrics_obj.containers_count,
                fill_rate=metrics_obj.fields_filled_rate,
                warnings_count=len(metrics_obj.warnings),
                warnings=metrics_obj.warnings,
                xml_valid=metrics_obj.xml_valid,
                has_exporter=metrics_obj.has_exporter,
                has_consignee=metrics_obj.has_consignee,
                processing_time=metrics_obj.total_time
            )

        return ConvertResponse(
            success=True,
            job_id=job_id,
            filename=file.filename,
            output_file=Path(output_path).name,
            message="Conversion réussie",
            metrics=metrics,
            processing_time=result['processing_time']
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la conversion: {str(e)}"
        )


async def _async_convert_task(job_id: str, pdf_path: str, output_path: str, taux_douane: float, rapport_paiement: Optional[str] = None):
    """Tâche de conversion asynchrone (background)"""

    # Mettre à jour le status à PROCESSING
    job_service.update_job(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        progress=10,
        message="Conversion en cours..."
    )

    # Convertir
    result = conversion_service.convert_pdf_to_xml(
        pdf_path=pdf_path,
        output_path=output_path,
        verbose=False,
        taux_douane=taux_douane,
        rapport_paiement=rapport_paiement
    )

    # Mettre à jour le job avec le résultat
    if result['success']:
        job_service.update_job(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Conversion terminée",
            result=result
        )
    else:
        job_service.update_job(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=0,
            message="Conversion échouée",
            error=result['error_message']
        )


@router.post(
    "/async",
    response_model=ConvertAsyncResponse,
    summary="Conversion asynchrone PDF → XML ASYCUDA",
    description="Upload un PDF RFCV et retourne un job_id pour récupérer le résultat plus tard. **Taux douanier obligatoire** pour le calcul de l'assurance. Rapport de paiement optionnel.",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.UPLOAD_ASYNC)
async def convert_pdf_async(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: Optional[str] = Form(None, description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J). Optionnel - généré après paiement des taxes.")
):
    """
    Conversion asynchrone PDF → XML

    - **file**: Fichier PDF à convertir
    - **taux_douane**: Taux de change douanier pour calcul assurance (format: 573.1390)
      - **Obligatoire** : Communiqué par la douane avant chaque conversion
      - **Format** : Point (`.`) comme séparateur décimal (ex: 573.1390)
    - **rapport_paiement**: Numéro de rapport de paiement/quittance Trésor Public (optionnel)
      - **Format** : 8 caractères alphanumériques (ex: 25P2003J)
      - **Quand fournir** : Si vous avez déjà le numéro de quittance du Trésor
      - **Workflow** : Généré APRÈS paiement des taxes, donc rarement disponible lors de la conversion initiale
      - **Champ XML** : Remplit `Deffered_payment_reference` dans la section `<Financial>`

    Retourne un job_id pour suivre la progression avec GET /convert/{job_id}
    """
    # Valider le fichier (fonction async maintenant)
    file = await validate_upload_file(file)

    # Générer un job ID
    job_id = storage_service.generate_job_id()

    try:
        # Sauvegarder le fichier uploadé
        pdf_path = await storage_service.save_upload(file, job_id)

        # Générer le chemin de sortie
        output_path = storage_service.get_output_path(pdf_path)

        # Créer le job
        job = job_service.create_job(
            job_id=job_id,
            filename=file.filename,
            pdf_path=pdf_path,
            output_path=output_path
        )

        # Lancer la conversion en background
        background_tasks.add_task(
            _async_convert_task,
            job_id=job_id,
            pdf_path=pdf_path,
            output_path=output_path,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement
        )

        return ConvertAsyncResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Conversion en cours",
            created_at=job['created_at']
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'initialisation: {str(e)}"
        )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Status d'un job",
    description="Récupère le status et la progression d'un job de conversion",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DEFAULT)
async def get_job_status(request: Request, job_id: str):
    """
    Récupère le status d'un job de conversion

    - **job_id**: ID du job de conversion

    Retourne le status, la progression et les résultats si disponibles
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )

    return JobStatusResponse(
        job_id=job['job_id'],
        status=job['status'],
        filename=job['filename'],
        created_at=job['created_at'],
        completed_at=job['completed_at'],
        progress=job['progress'],
        message=job['message'],
        error=job['error']
    )


@router.get(
    "/{job_id}/result",
    summary="Résultat d'un job",
    description="Récupère le résultat complet d'un job de conversion avec métriques",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DEFAULT)
async def get_job_result(request: Request, job_id: str):
    """
    Récupère le résultat complet d'un job

    - **job_id**: ID du job de conversion

    Retourne les métriques et détails de la conversion
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )

    if job['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} n'est pas terminé (status: {job['status']})"
        )

    return {
        'job_id': job['job_id'],
        'filename': job['filename'],
        'status': job['status'],
        'result': job['result']
    }


@router.get(
    "/{job_id}/download",
    response_class=FileResponse,
    summary="Télécharger le XML",
    description="Télécharge le fichier XML généré pour un job",
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.DOWNLOAD)
async def download_xml(request: Request, job_id: str):
    """
    Télécharge le fichier XML généré

    - **job_id**: ID du job de conversion

    Retourne le fichier XML en téléchargement
    """
    job = job_service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} introuvable"
        )

    if job['status'] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} n'est pas terminé"
        )

    output_path = job['output_path']

    if not storage_service.file_exists(output_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier XML introuvable"
        )

    return FileResponse(
        path=output_path,
        media_type="application/xml",
        filename=Path(output_path).name
    )
