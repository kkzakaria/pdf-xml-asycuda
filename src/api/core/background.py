"""
Tâches background pour l'API
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

from .config import settings

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Gestionnaire de tâches background"""

    @staticmethod
    async def cleanup_old_files():
        """
        Nettoie les fichiers expirés (uploads et outputs)

        Supprime les fichiers plus vieux que job_expiry_hours
        """
        try:
            expiry_time = datetime.now() - timedelta(hours=settings.job_expiry_hours)

            deleted_count = 0

            # Nettoyer uploads
            for file_path in Path(settings.upload_dir).rglob("*"):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < expiry_time:
                        file_path.unlink()
                        deleted_count += 1

            # Nettoyer outputs
            for file_path in Path(settings.output_dir).rglob("*"):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < expiry_time:
                        file_path.unlink()
                        deleted_count += 1

            if deleted_count > 0:
                logger.info("Nettoyage: %d fichiers expirés supprimés", deleted_count)

        except Exception as e:
            logger.error("Erreur nettoyage: %s", e)

    @staticmethod
    async def periodic_cleanup():
        """
        Lance le nettoyage périodique des fichiers

        S'exécute toutes les cleanup_interval_hours heures
        """
        while True:
            await BackgroundTaskManager.cleanup_old_files()
            await asyncio.sleep(settings.cleanup_interval_hours * 3600)


# Instance globale
task_manager = BackgroundTaskManager()
