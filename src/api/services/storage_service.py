"""
Service de stockage de fichiers
Gestion des uploads et downloads
"""
import aiofiles
import secrets
import re
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime
from fastapi import UploadFile, HTTPException, status

from ..core.config import settings


class StorageService:
    """Service de gestion des fichiers"""

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Sanitise un nom de fichier pour éviter path traversal

        Args:
            filename: Nom de fichier original

        Returns:
            Nom de fichier sécurisé
        """
        # Supprimer les séparateurs de chemin
        safe_name = filename.replace('/', '_').replace('\\', '_')

        # Supprimer les références au répertoire parent
        safe_name = safe_name.replace('..', '')

        # Supprimer les caractères null
        safe_name = safe_name.replace('\0', '')

        # Ne garder que les caractères alphanumériques, tirets, underscores et points
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', safe_name)

        # Limiter la longueur (conserver l'extension)
        if len(safe_name) > 255:
            name, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
            safe_name = name[:250] + ('.' + ext if ext else '')

        # Si le nom est vide après sanitisation, utiliser un défaut
        return safe_name if safe_name else 'unnamed_file'

    @staticmethod
    async def save_upload(file: UploadFile, job_id: Optional[str] = None) -> str:
        """
        Sauvegarde un fichier uploadé avec sanitisation du nom

        Args:
            file: Fichier uploadé
            job_id: ID du job (optionnel)

        Returns:
            Chemin du fichier sauvegardé

        Raises:
            HTTPException: Si le chemin résolu est en dehors du répertoire upload
        """
        # Générer un ID sécurisé si non fourni
        if job_id is None:
            job_id = StorageService.generate_job_id()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitiser le nom de fichier
        safe_filename = StorageService._sanitize_filename(file.filename)
        filename = f"{job_id}_{timestamp}_{safe_filename}"

        # Construire et résoudre le chemin
        upload_dir = Path(settings.upload_dir).resolve()
        file_path = (upload_dir / filename).resolve()

        # CRITIQUE: Vérifier que le chemin résolu reste dans upload_dir
        try:
            file_path.relative_to(upload_dir)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chemin de fichier invalide: tentative de path traversal détectée"
            )

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
        """
        Génère un ID de job cryptographiquement sécurisé

        Returns:
            ID de job unique et non prévisible (128-bit de sécurité)
        """
        # Utiliser secrets.token_urlsafe pour éviter l'énumération
        # 16 bytes = 128 bits de sécurité
        random_part = secrets.token_urlsafe(16)
        return f"conv_{random_part}"

    @staticmethod
    def generate_batch_id() -> str:
        """
        Génère un ID de batch cryptographiquement sécurisé

        Returns:
            ID de batch unique et non prévisible (128-bit de sécurité)
        """
        # Utiliser secrets.token_urlsafe pour éviter l'énumération
        random_part = secrets.token_urlsafe(16)
        return f"batch_{random_part}"


# Instance globale
storage_service = StorageService()
