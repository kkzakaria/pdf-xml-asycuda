"""
Routes de gestion des fichiers
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pathlib import Path

from ..models.api_models import FileMetadataResponse
from ..services.storage_service import storage_service

router = APIRouter(prefix="/api/v1/files", tags=["Files"])


@router.get(
    "/{file_id}/xml",
    response_class=FileResponse,
    summary="Télécharger XML",
    description="Télécharge un fichier XML généré par son ID"
)
async def download_xml_file(file_id: str):
    """
    Télécharge un fichier XML

    - **file_id**: ID ou nom du fichier XML

    Retourne le fichier XML en téléchargement
    """
    # Construire le chemin du fichier
    # Le file_id peut être un nom de fichier ou un chemin relatif
    if not file_id.endswith('.xml'):
        file_id = f"{file_id}.xml"

    file_path = Path(storage_service.settings.output_dir) / file_id

    # Vérifier que le fichier existe
    if not storage_service.file_exists(str(file_path)):
        # Essayer de chercher dans les sous-dossiers
        matching_files = list(Path(storage_service.settings.output_dir).rglob(file_id))
        if matching_files:
            file_path = matching_files[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier {file_id} introuvable"
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
    description="Récupère les métadonnées d'un fichier XML"
)
async def get_file_metadata(file_id: str):
    """
    Récupère les métadonnées d'un fichier

    - **file_id**: ID ou nom du fichier XML

    Retourne les métadonnées (taille, date de création, etc.)
    """
    # Construire le chemin du fichier
    if not file_id.endswith('.xml'):
        file_id = f"{file_id}.xml"

    file_path = Path(storage_service.settings.output_dir) / file_id

    # Vérifier que le fichier existe
    if not storage_service.file_exists(str(file_path)):
        # Essayer de chercher dans les sous-dossiers
        matching_files = list(Path(storage_service.settings.output_dir).rglob(file_id))
        if matching_files:
            file_path = matching_files[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Fichier {file_id} introuvable"
            )

    # Récupérer les métadonnées
    size = storage_service.get_file_size(str(file_path))
    mtime = storage_service.get_file_mtime(str(file_path))

    return FileMetadataResponse(
        file_id=file_path.stem,
        filename=file_path.name,
        size_bytes=size,
        created_at=mtime,
        mime_type="application/xml",
        is_available=True
    )
