"""
Dépendances FastAPI pour injection
"""
from fastapi import Depends, HTTPException, status, UploadFile
from typing import Optional
import os
from pathlib import Path

from .config import settings


def get_settings():
    """Retourne les settings de l'application"""
    return settings


def validate_upload_file(file: UploadFile) -> UploadFile:
    """
    Valide un fichier uploadé

    Args:
        file: Fichier uploadé

    Returns:
        Fichier validé

    Raises:
        HTTPException: Si le fichier est invalide
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

    return file


def ensure_directories():
    """Crée les répertoires nécessaires s'ils n'existent pas"""
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)


# Dépendance startup
def startup_tasks():
    """Tâches à exécuter au démarrage de l'API"""
    ensure_directories()
    print(f"✓ Directories created: {settings.upload_dir}, {settings.output_dir}")
