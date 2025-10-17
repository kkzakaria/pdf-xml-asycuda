"""
Dépendances FastAPI pour injection
"""
import io
import logging
from fastapi import HTTPException, status, UploadFile
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)


def get_settings():
    """Retourne les settings de l'application"""
    return settings


async def validate_upload_file(file: UploadFile) -> UploadFile:
    """
    Valide un fichier uploadé (extension, taille, format)

    Args:
        file: Fichier uploadé

    Returns:
        Fichier validé avec file pointer réinitialisé

    Raises:
        HTTPException: Si le fichier est invalide ou trop grand
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier fourni"
        )

    # Vérifier l'extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extension {file_ext} non supportée. Extensions autorisées: {', '.join(settings.allowed_extensions)}"
        )

    # Valider la taille du fichier en le lisant par chunks
    max_size = settings.max_upload_size
    chunk_size = 1024 * 1024  # 1MB chunks
    total_size = 0
    chunks = []

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)
            chunks.append(chunk)

            # Vérifier la taille max
            if total_size > max_size:
                max_size_mb = max_size / (1024 * 1024)
                total_size_mb = total_size / (1024 * 1024)
                logger.warning(
                    f"File upload rejected: size {total_size_mb:.2f}MB exceeds limit {max_size_mb:.0f}MB, "
                    f"filename={file.filename}"
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Fichier trop volumineux: {total_size_mb:.2f}MB dépasse la limite de {max_size_mb:.0f}MB"
                )

        # Vérifier que le fichier n'est pas vide
        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier vide"
            )

        # Reconstituer le fichier depuis les chunks pour réinitialiser le file pointer
        file.file = io.BytesIO(b''.join(chunks))

        # Vérifier le magic number PDF (optionnel mais recommandé)
        file_header = chunks[0] if chunks else b''
        if len(file_header) >= 5 and not file_header[:5].startswith(b'%PDF-'):
            logger.warning(
                f"File upload rejected: not a valid PDF (invalid magic number), filename={file.filename}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format de fichier invalide: le fichier n'est pas un PDF valide"
            )

        # Logger l'upload validé
        logger.info(f"File upload validated: filename={file.filename}, size={total_size} bytes")

        return file

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la validation du fichier: {str(e)}"
        )


def ensure_directories():
    """Crée les répertoires nécessaires s'ils n'existent pas"""
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)


# Dépendance startup
def startup_tasks():
    """Tâches à exécuter au démarrage de l'API"""
    ensure_directories()
    print(f"✓ Directories created: {settings.upload_dir}, {settings.output_dir}")
