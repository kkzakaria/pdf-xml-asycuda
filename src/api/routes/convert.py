"""
Routes de conversion
"""
import json
import logging
import time
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Depends, Request
from fastapi.responses import FileResponse
from pathlib import Path

from ..models.api_models import (
    ConvertResponse,
    ConvertAsyncResponse,
    JobStatusResponse,
    JobStatus,
    ConversionMetrics,
    DuplicateChassisErrorResponse
)
from ..services.conversion_service import conversion_service, DuplicateChassisError
from ..services.storage_service import storage_service
from ..services.job_service import job_service
from ..services.usage_stats_service import get_usage_stats
from ..core.dependencies import validate_upload_file
from ..core.security import verify_api_key
from ..core.rate_limit import limiter, RateLimits

logger = logging.getLogger(__name__)


def _track_conversion(success: bool, is_async: bool = False,
                      has_chassis: bool = False, has_payment: bool = False) -> None:
    """Helper pour tracker une conversion dans les stats d'utilisation"""
    get_usage_stats().track_conversion(
        success=success, is_async=is_async,
        has_chassis=has_chassis, has_payment=has_payment
    )

router = APIRouter(prefix="/api/v1/convert", tags=["Conversion"])


@router.post(
    "",
    response_model=ConvertResponse,
    summary="Conversion synchrone PDF → XML ASYCUDA",
    description="""
Upload un PDF RFCV et retourne le XML ASYCUDA immédiatement.

### Paramètres requis
- **file**: Fichier PDF RFCV (max 50MB)
- **taux_douane**: Taux de change douanier (format: 573.1390)

### Paramètres optionnels
- **rapport_paiement**: Numéro de quittance du Trésor Public (ex: 25P2003J)
- **chassis_config**: Configuration JSON pour génération automatique de châssis VIN

### 🚗 Exemple de génération de châssis

**Configuration JSON** :
```json
{
  "generate_chassis": true,
  "quantity": 180,
  "wmi": "LZS",
  "year": 2025,
  "vds": "HCKZS",
  "plant_code": "S",
  "ensure_unique": true
}
```

**Exemple curl avec génération de 180 châssis** :
```bash
curl -X POST "http://localhost:8000/api/v1/convert" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F 'chassis_config={"generate_chassis":true,"quantity":180,"wmi":"LZS","year":2025}'
```

**Résultat** : VIN générés (LZSHCKZS0SS000001, LZSHCKZS2SS000002...) dans documents code 6022 (motos) ou 6122 (autres véhicules).

### 📄 Documents joints générés automatiquement
Chaque article inclut les documents ASYCUDA suivants :
| Code | Document |
|------|----------|
| 0007 | FACTURE |
| 0014 | JUSTIFICATION D'ASSURANCE |
| 6603 | BORDEREAU DE SUIVI DE CARGAISON (BSC) |
| 2500 | NUMERO DE LIGNE ARTICLE RFCV |
| 2501 | ATTESTATION DE VERIFICATION RFCV |
| 6022/6122 | NUMERO DE CHASSIS (si véhicule) |
    """,
    dependencies=[Depends(verify_api_key)],
    responses={409: {"model": DuplicateChassisErrorResponse, "description": "Châssis déjà traité"}}
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def convert_pdf(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: Optional[str] = Form(None, description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J). Optionnel - généré après paiement des taxes."),
    chassis_config: Optional[str] = Form(None, description="Configuration JSON pour génération automatique de châssis VIN. Format: {\"generate_chassis\": true, \"quantity\": 180, \"wmi\": \"LZS\", \"vds\": \"HCKZS\", \"year\": 2025, \"plant_code\": \"S\"}. Optionnel."),
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
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

        # Parser la configuration chassis si fournie
        chassis_config_dict = None
        if chassis_config:
            try:
                chassis_config_dict = json.loads(chassis_config)
                # Valider les champs requis si generate_chassis est activé
                if chassis_config_dict.get('generate_chassis'):
                    required_fields = ['quantity', 'wmi', 'year']
                    missing = [f for f in required_fields if f not in chassis_config_dict]
                    if missing:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Champs requis manquants dans chassis_config: {', '.join(missing)}"
                        )
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Format JSON invalide pour chassis_config: {str(e)}"
                )

        # Convertir
        start = time.time()
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement,
            chassis_config=chassis_config_dict,
            force_reprocess=force_reprocess,
        )

        if not result['success']:
            logger.error("Conversion échouée: file=%s, error=%s", file.filename, result['error_message'])
            _track_conversion(
                success=False, is_async=False,
                has_chassis=chassis_config_dict is not None,
                has_payment=rapport_paiement is not None
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error_message'] or "Erreur de conversion"
            )

        logger.info("Conversion réussie: file=%s, time=%.2fs", file.filename, time.time() - start)
        _track_conversion(
            success=True, is_async=False,
            has_chassis=chassis_config_dict is not None,
            has_payment=rapport_paiement is not None
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

    except DuplicateChassisError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "duplicate_chassis",
                "detail": f"{len(e.duplicates)} châssis déjà traité(s) dans ce RFCV",
                "duplicates": e.duplicates,
                "hint": "Relancer avec force_reprocess=true pour forcer le retraitement",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conversion échouée: file=%s, error=%s", file.filename, e)
        _track_conversion(success=False, is_async=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la conversion: {str(e)}"
        )


async def _async_convert_task(job_id: str, pdf_path: str, output_path: str, taux_douane: float, rapport_paiement: Optional[str] = None, chassis_config: Optional[dict] = None, force_reprocess: bool = False):
    """Tâche de conversion asynchrone (background)"""

    # Mettre à jour le status à PROCESSING
    job_service.update_job(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        progress=10,
        message="Conversion en cours..."
    )

    # Convertir
    try:
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement,
            chassis_config=chassis_config,
            force_reprocess=force_reprocess,
        )
    except DuplicateChassisError as e:
        _track_conversion(success=False, is_async=True)
        job_service.update_job(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=0,
            message=f"Châssis en doublon: {len(e.duplicates)} déjà traité(s)",
            error=str(e),
            duplicate_chassis=e.duplicates,
        )
        return

    # Mettre à jour le job avec le résultat
    if result['success']:
        logger.info("Conversion async réussie: job_id=%s, time=%.2fs", job_id, result['processing_time'])
        _track_conversion(
            success=True, is_async=True,
            has_chassis=chassis_config is not None,
            has_payment=rapport_paiement is not None
        )
        job_service.update_job(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            progress=100,
            message="Conversion terminée",
            result=result
        )
    else:
        logger.error("Conversion async échouée: job_id=%s, error=%s", job_id, result['error_message'])
        _track_conversion(
            success=False, is_async=True,
            has_chassis=chassis_config is not None,
            has_payment=rapport_paiement is not None
        )
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
    description="""
Upload un PDF RFCV et retourne un job_id pour récupérer le résultat plus tard.

### Paramètres requis
- **file**: Fichier PDF RFCV (max 50MB)
- **taux_douane**: Taux de change douanier (format: 573.1390)

### Paramètres optionnels
- **rapport_paiement**: Numéro de quittance du Trésor Public
- **chassis_config**: Configuration JSON pour génération automatique de châssis VIN

### Workflow asynchrone
1. **Upload** → Reçoit `job_id` immédiatement
2. **Status** → GET `/convert/{job_id}` pour vérifier progression
3. **Download** → GET `/convert/{job_id}/download` quand terminé

### 🚗 Génération de châssis en mode asynchrone

Même format de configuration que le mode synchrone :
```bash
curl -X POST "http://localhost:8000/api/v1/convert/async" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F 'chassis_config={"generate_chassis":true,"quantity":50,"wmi":"LFV","year":2024}'
```
    """,
    dependencies=[Depends(verify_api_key)]
)
@limiter.limit(RateLimits.UPLOAD_ASYNC)
async def convert_pdf_async(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: Optional[str] = Form(None, description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J). Optionnel - généré après paiement des taxes."),
    chassis_config: Optional[str] = Form(None, description="Configuration JSON pour génération automatique de châssis VIN. Format: {\"generate_chassis\": true, \"quantity\": 180, \"wmi\": \"LZS\", \"vds\": \"HCKZS\", \"year\": 2025, \"plant_code\": \"S\"}. Optionnel."),
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
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

        # Parser la configuration chassis si fournie
        chassis_config_dict = None
        if chassis_config:
            try:
                chassis_config_dict = json.loads(chassis_config)
                # Valider les champs requis si generate_chassis est activé
                if chassis_config_dict.get('generate_chassis'):
                    required_fields = ['quantity', 'wmi', 'year']
                    missing = [f for f in required_fields if f not in chassis_config_dict]
                    if missing:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Champs requis manquants dans chassis_config: {', '.join(missing)}"
                        )
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Format JSON invalide pour chassis_config: {str(e)}"
                )

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
            rapport_paiement=rapport_paiement,
            chassis_config=chassis_config_dict,
            force_reprocess=force_reprocess,
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
    description="""Récupère le status et la progression d'un job de conversion.

Si le job a échoué à cause de châssis en doublon, le champ `duplicate_chassis` contient
la liste structurée des doublons (numéro, date première vue, fichier source, numéro RFCV).
Relancer avec `force_reprocess=true` pour forcer le retraitement.""",
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
        error=job['error'],
        duplicate_chassis=job.get('duplicate_chassis'),
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


# ============= Endpoints Spécifiques pour Paramètres Optionnels =============


@router.post(
    "/with-payment",
    response_model=ConvertResponse,
    summary="Conversion avec rapport de paiement",
    description="""
Conversion synchrone PDF → XML ASYCUDA avec numéro de rapport de paiement (quittance Trésor).

### Paramètres requis
- **file**: Fichier PDF RFCV (max 50MB)
- **taux_douane**: Taux de change douanier (format: 573.1390)
- **rapport_paiement**: Numéro de quittance du Trésor Public (ex: 25P2003J)

### Cas d'usage
Utilisez cet endpoint quand vous avez DÉJÀ le numéro de quittance du Trésor Public après paiement des taxes douanières.

### Workflow typique
1. **Conversion initiale** → Utiliser `/convert` (sans rapport)
2. **Calcul des taxes** → ASYCUDA calcule les montants
3. **Paiement au Trésor** → Obtention du numéro de quittance (ex: 25P2003J)
4. **Re-conversion** → Utiliser `/convert/with-payment` pour inclure le numéro

### Exemple
```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-payment" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F "rapport_paiement=25P2003J"
```

### Résultat XML
Le champ `<Deffered_payment_reference>` sera rempli avec le numéro de quittance.
    """,
    dependencies=[Depends(verify_api_key)],
    responses={409: {"model": DuplicateChassisErrorResponse, "description": "Châssis déjà traité"}}
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def convert_with_payment(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: str = Form(..., description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J)", min_length=1),
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
):
    """
    Conversion avec rapport de paiement (quittance Trésor)

    - **file**: Fichier PDF à convertir
    - **taux_douane**: Taux de change douanier (format: 573.1390)
    - **rapport_paiement**: Numéro de quittance du Trésor Public (OBLIGATOIRE)

    Retourne le XML avec le champ `Deffered_payment_reference` rempli
    """
    file = await validate_upload_file(file)
    job_id = storage_service.generate_job_id()

    try:
        pdf_path = await storage_service.save_upload(file, job_id)
        output_path = storage_service.get_output_path(pdf_path)

        start = time.time()
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement,
            chassis_config=None,
            force_reprocess=force_reprocess,
        )

        if not result['success']:
            logger.error("Conversion avec paiement échouée: file=%s, error=%s", file.filename, result['error_message'])
            _track_conversion(success=False, is_async=False, has_payment=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error_message'] or "Erreur de conversion"
            )

        logger.info("Conversion avec paiement réussie: file=%s, time=%.2fs", file.filename, time.time() - start)
        _track_conversion(success=True, is_async=False, has_payment=True)

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
            message="Conversion réussie avec rapport de paiement",
            metrics=metrics,
            processing_time=result['processing_time']
        )

    except DuplicateChassisError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "duplicate_chassis",
                "detail": f"{len(e.duplicates)} châssis déjà traité(s) dans ce RFCV",
                "duplicates": e.duplicates,
                "hint": "Relancer avec force_reprocess=true pour forcer le retraitement",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conversion avec paiement échouée: file=%s, error=%s", file.filename, e)
        _track_conversion(success=False, is_async=False, has_payment=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la conversion: {str(e)}"
        )


@router.post(
    "/with-chassis",
    response_model=ConvertResponse,
    summary="Conversion avec génération de châssis VIN",
    description="""
Conversion synchrone PDF → XML ASYCUDA avec génération automatique de numéros de châssis VIN ISO 3779.

### Paramètres requis
- **file**: Fichier PDF RFCV (max 50MB)
- **taux_douane**: Taux de change douanier (format: 573.1390)
- **quantity**: Nombre de châssis VIN à générer
- **wmi**: World Manufacturer Identifier - Code fabricant 3 caractères (ex: LZS, LFV)
- **year**: Année de fabrication (ex: 2025)

### Paramètres optionnels
- **vds**: Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)
- **plant_code**: Code usine - 1 caractère (défaut: S)

### Fonctionnalités
- ✅ Génération VIN ISO 3779 avec checksum
- ✅ Séquences persistantes (pas de doublons)
- ✅ Thread-safe pour traitement parallèle
- ✅ Nettoyage automatique des anciens châssis dans descriptions
- ✅ Documents code 6022 (motos) et 6122 (autres véhicules)

### Exemple - 180 châssis LZS/2025
```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-chassis" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F "quantity=180" \\
  -F "wmi=LZS" \\
  -F "year=2025"
```

### Exemple - 50 châssis LFV/2024 avec VDS personnalisé
```bash
curl -X POST "http://localhost:8000/api/v1/convert/with-chassis" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F "quantity=50" \\
  -F "wmi=LFV" \\
  -F "year=2024" \\
  -F "vds=BA01A" \\
  -F "plant_code=P"
```

### Résultat
VIN générés (ex: LZSHCKZS0SS000001) apparaissent dans :
- Document code 6022 (motos) ou 6122 (autres véhicules) (`<Attached_document_reference>`)
- Marks2 avec préfixe CH: (`<Marks2_of_packages>`)

### Documents joints générés automatiquement
Chaque article inclut les documents suivants :
- **0007**: FACTURE
- **0014**: JUSTIFICATION D'ASSURANCE
- **6603**: BORDEREAU DE SUIVI DE CARGAISON (BSC)
- **2500**: NUMERO DE LIGNE ARTICLE RFCV
- **2501**: ATTESTATION DE VERIFICATION RFCV
- **6022/6122**: NUMERO DE CHASSIS (si véhicule)
    """,
    dependencies=[Depends(verify_api_key)],
    responses={409: {"model": DuplicateChassisErrorResponse, "description": "Châssis déjà traité"}}
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def convert_with_chassis(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    quantity: int = Form(..., description="Nombre de châssis VIN à générer", gt=0),
    wmi: str = Form(..., description="World Manufacturer Identifier - 3 caractères (ex: LZS, LFV)", min_length=3, max_length=3),
    year: int = Form(..., description="Année de fabrication (ex: 2025)", ge=1980, le=2055),
    vds: str = Form(default="HCKZS", description="Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)", min_length=5, max_length=5),
    plant_code: str = Form(default="S", description="Code usine de fabrication - 1 caractère (défaut: S)", min_length=1, max_length=1),
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
):
    """
    Conversion avec génération automatique de châssis VIN ISO 3779

    - **file**: Fichier PDF à convertir
    - **taux_douane**: Taux de change douanier (format: 573.1390)
    - **quantity**: Nombre de VIN à générer (OBLIGATOIRE)
    - **wmi**: Code fabricant 3 chars (OBLIGATOIRE)
    - **year**: Année de fabrication (OBLIGATOIRE)
    - **vds**: Descripteur véhicule 5 chars (optionnel)
    - **plant_code**: Code usine 1 char (optionnel)

    Retourne le XML avec VIN générés dans documents code 6122 et Marks2
    """
    file = await validate_upload_file(file)
    job_id = storage_service.generate_job_id()

    try:
        pdf_path = await storage_service.save_upload(file, job_id)
        output_path = storage_service.get_output_path(pdf_path)

        # Construire la config chassis
        chassis_config_dict = {
            "generate_chassis": True,
            "quantity": quantity,
            "wmi": wmi.upper(),
            "year": year,
            "vds": vds.upper(),
            "plant_code": plant_code.upper(),
            "ensure_unique": True
        }

        start = time.time()
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=None,
            chassis_config=chassis_config_dict,
            force_reprocess=force_reprocess,
        )

        if not result['success']:
            logger.error("Conversion avec châssis échouée: file=%s, error=%s", file.filename, result['error_message'])
            _track_conversion(success=False, is_async=False, has_chassis=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error_message'] or "Erreur de conversion"
            )

        logger.info("Conversion avec châssis réussie: file=%s, quantity=%d, time=%.2fs", file.filename, quantity, time.time() - start)
        _track_conversion(success=True, is_async=False, has_chassis=True)

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
            message=f"Conversion réussie avec génération de {quantity} châssis VIN",
            metrics=metrics,
            processing_time=result['processing_time']
        )

    except DuplicateChassisError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "duplicate_chassis",
                "detail": f"{len(e.duplicates)} châssis déjà traité(s) dans ce RFCV",
                "duplicates": e.duplicates,
                "hint": "Relancer avec force_reprocess=true pour forcer le retraitement",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conversion avec châssis échouée: file=%s, error=%s", file.filename, e)
        _track_conversion(success=False, is_async=False, has_chassis=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la conversion: {str(e)}"
        )


@router.post(
    "/complete",
    response_model=ConvertResponse,
    summary="Conversion complète (rapport + châssis)",
    description="""
Conversion synchrone PDF → XML ASYCUDA avec rapport de paiement ET génération de châssis VIN.

### Paramètres requis
- **file**: Fichier PDF RFCV (max 50MB)
- **taux_douane**: Taux de change douanier (format: 573.1390)
- **rapport_paiement**: Numéro de quittance du Trésor Public (ex: 25P2003J)
- **quantity**: Nombre de châssis VIN à générer
- **wmi**: World Manufacturer Identifier - Code fabricant 3 caractères
- **year**: Année de fabrication

### Paramètres optionnels
- **vds**: Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)
- **plant_code**: Code usine - 1 caractère (défaut: S)

### Cas d'usage
Utilisez cet endpoint pour une conversion complète incluant :
- ✅ Numéro de quittance du Trésor Public
- ✅ Génération automatique de châssis VIN ISO 3779
- ✅ Toutes les fonctionnalités combinées

### Exemple
```bash
curl -X POST "http://localhost:8000/api/v1/convert/complete" \\
  -H "X-API-Key: votre_cle_api" \\
  -F "file=@DOSSIER.pdf" \\
  -F "taux_douane=573.139" \\
  -F "rapport_paiement=25P2003J" \\
  -F "quantity=180" \\
  -F "wmi=LZS" \\
  -F "year=2025"
```

### Résultat
Le XML généré contiendra :
- `<Deffered_payment_reference>25P2003J</Deffered_payment_reference>`
- VIN générés dans documents code 6122 et Marks2
    """,
    dependencies=[Depends(verify_api_key)],
    responses={409: {"model": DuplicateChassisErrorResponse, "description": "Châssis déjà traité"}}
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def convert_complete(
    request: Request,
    file: UploadFile = File(..., description="Fichier PDF RFCV à convertir"),
    taux_douane: float = Form(..., description="Taux de change douanier (ex: 573.1390)", gt=0),
    rapport_paiement: str = Form(..., description="Numéro de rapport de paiement/quittance Trésor Public (ex: 25P2003J)", min_length=1),
    quantity: int = Form(..., description="Nombre de châssis VIN à générer", gt=0),
    wmi: str = Form(..., description="World Manufacturer Identifier - 3 caractères (ex: LZS)", min_length=3, max_length=3),
    year: int = Form(..., description="Année de fabrication (ex: 2025)", ge=1980, le=2055),
    vds: str = Form(default="HCKZS", description="Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)", min_length=5, max_length=5),
    plant_code: str = Form(default="S", description="Code usine de fabrication - 1 caractère (défaut: S)", min_length=1, max_length=1),
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
):
    """
    Conversion complète avec rapport de paiement ET génération de châssis

    - **file**: Fichier PDF à convertir
    - **taux_douane**: Taux de change douanier (format: 573.1390)
    - **rapport_paiement**: Numéro de quittance Trésor (OBLIGATOIRE)
    - **quantity**: Nombre de VIN à générer (OBLIGATOIRE)
    - **wmi**: Code fabricant 3 chars (OBLIGATOIRE)
    - **year**: Année de fabrication (OBLIGATOIRE)
    - **vds**: Descripteur véhicule 5 chars (optionnel)
    - **plant_code**: Code usine 1 char (optionnel)

    Retourne le XML avec rapport de paiement ET châssis VIN générés
    """
    file = await validate_upload_file(file)
    job_id = storage_service.generate_job_id()

    try:
        pdf_path = await storage_service.save_upload(file, job_id)
        output_path = storage_service.get_output_path(pdf_path)

        # Construire la config chassis
        chassis_config_dict = {
            "generate_chassis": True,
            "quantity": quantity,
            "wmi": wmi.upper(),
            "year": year,
            "vds": vds.upper(),
            "plant_code": plant_code.upper(),
            "ensure_unique": True
        }

        start = time.time()
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement,
            chassis_config=chassis_config_dict,
            force_reprocess=force_reprocess,
        )

        if not result['success']:
            logger.error("Conversion complète échouée: file=%s, error=%s", file.filename, result['error_message'])
            _track_conversion(success=False, is_async=False, has_chassis=True, has_payment=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result['error_message'] or "Erreur de conversion"
            )

        logger.info("Conversion complète réussie: file=%s, quantity=%d, time=%.2fs", file.filename, quantity, time.time() - start)
        _track_conversion(success=True, is_async=False, has_chassis=True, has_payment=True)

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
            message=f"Conversion complète réussie: rapport {rapport_paiement} + {quantity} châssis VIN",
            metrics=metrics,
            processing_time=result['processing_time']
        )

    except DuplicateChassisError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "duplicate_chassis",
                "detail": f"{len(e.duplicates)} châssis déjà traité(s) dans ce RFCV",
                "duplicates": e.duplicates,
                "hint": "Relancer avec force_reprocess=true pour forcer le retraitement",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conversion complète échouée: file=%s, error=%s", file.filename, e)
        _track_conversion(success=False, is_async=False, has_chassis=True, has_payment=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la conversion: {str(e)}"
        )
