"""
Service de stockage de fichiers
Gestion des uploads et downloads
"""
import aiofiles
import uuid
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime
from fastapi import UploadFile

from ..core.config import settings


class StorageService:
    """Service de gestion des fichiers"""

    @staticmethod
    async def save_upload(file: UploadFile, job_id: Optional[str] = None) -> str:
        """
        Sauvegarde un fichier uploadé

        Args:
            file: Fichier uploadé
            job_id: ID du job (optionnel)

        Returns:
            Chemin du fichier sauvegardé
        """
        # Générer un nom de fichier unique
        if job_id is None:
            job_id = str(uuid.uuid4())[:8]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{job_id}_{timestamp}_{file.filename}"

        # Créer le chemin complet
        file_path = Path(settings.upload_dir) / filename

        # Sauvegarder le fichier de manière asynchrone
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)

        return str(file_path)

    @staticmethod
    async def save_multiple_uploads(files: list[UploadFile], batch_id: str) -> list[str]:
        """
        Sauvegarde plusieurs fichiers uploadés

        Args:
            files: Liste de fichiers
            batch_id: ID du batch

        Returns:
            Liste des chemins sauvegardés
        """
        saved_paths = []

        for i, file in enumerate(files):
            job_id = f"{batch_id}_{i+1}"
            path = await StorageService.save_upload(file, job_id)
            saved_paths.append(path)

        return saved_paths

    @staticmethod
    def get_output_path(pdf_path: str, output_dir: Optional[str] = None) -> str:
        """
        Génère le chemin de sortie XML pour un PDF

        Args:
            pdf_path: Chemin du PDF
            output_dir: Dossier de sortie (défaut: settings.output_dir)

        Returns:
            Chemin du fichier XML
        """
        if output_dir is None:
            output_dir = settings.output_dir

        pdf_name = Path(pdf_path).stem
        xml_filename = f"{pdf_name}.xml"

        return str(Path(output_dir) / xml_filename)

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Vérifie si un fichier existe"""
        return Path(file_path).exists()

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Retourne la taille d'un fichier en octets"""
        return Path(file_path).stat().st_size if Path(file_path).exists() else 0

    @staticmethod
    def get_file_mtime(file_path: str) -> datetime:
        """Retourne la date de modification d'un fichier"""
        if Path(file_path).exists():
            timestamp = Path(file_path).stat().st_mtime
            return datetime.fromtimestamp(timestamp)
        return datetime.now()

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """
        Supprime un fichier

        Args:
            file_path: Chemin du fichier

        Returns:
            True si supprimé, False sinon
        """
        try:
            if Path(file_path).exists():
                Path(file_path).unlink()
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def generate_job_id() -> str:
        """Génère un ID de job unique"""
        return f"conv_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def generate_batch_id() -> str:
        """Génère un ID de batch unique"""
        return f"batch_{uuid.uuid4().hex[:12]}"


# Instance globale
storage_service = StorageService()
