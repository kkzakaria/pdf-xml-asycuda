"""
Tâches background pour l'API
"""
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import shutil

from .config import settings


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
                print(f"🧹 Cleaned up {deleted_count} expired files")

        except Exception as e:
            print(f"❌ Error during cleanup: {e}")

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
