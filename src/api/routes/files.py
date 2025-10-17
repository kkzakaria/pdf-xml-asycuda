"""
Routes de gestion des fichiers
"""
import re
import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import FileResponse
from pathlib import Path

from ..models.api_models import FileMetadataResponse
from ..services.storage_service import storage_service
from ..core.security import verify_api_key

router = APIRouter(prefix="/api/v1/files", tags=["Files"])
logger = logging.getLogger(__name__)


def validate_file_id(file_id: str, request: Request = None) -> str:
    """
    Valide et sanitise le file_id pour prévenir le path traversal

    Args:
        file_id: Identifiant de fichier fourni par l'utilisateur
        request: Request object pour logging

    Returns:
        Nom de fichier sanitisé

    Raises:
        HTTPException: Si le file_id contient des caractères dangereux
    """
    # Détecter les tentatives de path traversal
    if '..' in file_id or '/' in file_id or '\\' in file_id:
        # Logger la tentative d'attaque
        if request:
            logger.warning(
                f"Path traversal attempt detected: file_id={file_id}, "
                f"ip={request.client.host if request.client else 'unknown'}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_id invalide: caractères interdits détectés"
        )

    # Supprimer les caractères null bytes
    sanitized = file_id.replace('\0', '')

    # N'autoriser que les caractères alphanumériques, tirets, underscores et points
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', sanitized):
        if request:
            logger.warning(
                f"Invalid characters in file_id: file_id={file_id}, "
                f"ip={request.client.host if request.client else 'unknown'}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_id invalide: seuls les caractères alphanumériques, tirets, underscores et points sont autorisés"
        )

    # Limiter la longueur
    if len(sanitized) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_id trop long (maximum 255 caractères)"
        )

    return sanitized


@router.get(
    "/{file_id}/xml",
    response_class=FileResponse,
    summary="Télécharger XML",
    description="Télécharge un fichier XML généré par son ID",
    dependencies=[Depends(verify_api_key)]
)
async def download_xml_file(file_id: str, request: Request):
    """
    Télécharge un fichier XML

    - **file_id**: ID ou nom du fichier XML

    Retourne le fichier XML en téléchargement
    """
    # Valider et sanitiser le file_id
    safe_file_id = validate_file_id(file_id, request)

    # Ajouter extension .xml si absente
    if not safe_file_id.endswith('.xml'):
        safe_file_id = f"{safe_file_id}.xml"

    from ..core.config import settings

    # Construire le chemin et résoudre les liens symboliques
    output_dir = Path(settings.output_dir).resolve()
    file_path = (output_dir / safe_file_id).resolve()

    # CRITIQUE: Vérifier que le chemin résolu reste dans output_dir
    try:
        file_path.relative_to(output_dir)
    except ValueError:
        logger.error(
            f"Path traversal blocked: resolved path outside output_dir. "
            f"file_id={file_id}, resolved={file_path}, ip={request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé: chemin en dehors du répertoire autorisé"
        )

    # Vérifier l'existence du fichier (uniquement le chemin exact, pas de recherche récursive)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier {safe_file_id} introuvable"
        )

    # Logger l'accès au fichier
    logger.info(
        f"File download: file={safe_file_id}, ip={request.client.host if request.client else 'unknown'}"
    )

    return FileResponse(
        path=str(file_path),
        media_type="application/xml",
        filename=file_path.name
    )


@router.get(
    "/{file_id}/metadata",
    response_model=FileMetadataResponse,
    summary="Métadonnées fichier",
    description="Récupère les métadonnées d'un fichier XML",
    dependencies=[Depends(verify_api_key)]
)
async def get_file_metadata(file_id: str, request: Request):
    """
    Récupère les métadonnées d'un fichier

    - **file_id**: ID ou nom du fichier XML

    Retourne les métadonnées (taille, date de création, etc.)
    """
    # Valider et sanitiser le file_id
    safe_file_id = validate_file_id(file_id, request)

    # Ajouter extension .xml si absente
    if not safe_file_id.endswith('.xml'):
        safe_file_id = f"{safe_file_id}.xml"

    from ..core.config import settings

    # Construire le chemin et résoudre les liens symboliques
    output_dir = Path(settings.output_dir).resolve()
    file_path = (output_dir / safe_file_id).resolve()

    # CRITIQUE: Vérifier que le chemin résolu reste dans output_dir
    try:
        file_path.relative_to(output_dir)
    except ValueError:
        logger.error(
            f"Path traversal blocked in metadata: file_id={file_id}, "
            f"resolved={file_path}, ip={request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé: chemin en dehors du répertoire autorisé"
        )

    # Vérifier l'existence du fichier (uniquement le chemin exact)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier {safe_file_id} introuvable"
        )

    # Récupérer les métadonnées
    size = storage_service.get_file_size(str(file_path))
    mtime = storage_service.get_file_mtime(str(file_path))

    # Logger l'accès aux métadonnées
    logger.info(
        f"File metadata access: file={safe_file_id}, ip={request.client.host if request.client else 'unknown'}"
    )

    return FileMetadataResponse(
        file_id=file_path.stem,
        filename=file_path.name,
        size_bytes=size,
        created_at=mtime,
        mime_type="application/xml",
        is_available=True
    )
