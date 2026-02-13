"""
Service de statistiques d'utilisation de l'API
Persistance JSON thread-safe (pattern ChassisSequenceManager)
"""

import json
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class UsageStatsService:
    """
    Service de statistiques d'utilisation avec persistance JSON.

    Thread-safe via threading.Lock. Sauvegarde automatique après chaque mise à jour.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = str(Path(__file__).parent.parent.parent.parent / "data" / "usage_stats.json")

        self.storage_path = Path(storage_path)
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {}

        # Créer répertoire si nécessaire
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._load()
        logger.info("UsageStatsService initialisé: %s", self.storage_path)

    def _default_stats(self) -> Dict[str, Any]:
        """Structure par défaut des statistiques"""
        now = datetime.now().isoformat()
        return {
            "initialized_at": now,
            "last_updated": now,
            "conversions": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "sync": 0,
                "async": 0,
                "with_chassis": 0,
                "with_payment": 0
            },
            "batches": {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_files_processed": 0
            },
            "chassis": {
                "generation_requests": 0,
                "total_vins_generated": 0
            },
            "requests": {
                "total": 0,
                "by_method": {},
                "by_status": {}
            }
        }

    def _load(self) -> None:
        """Charge les statistiques depuis le fichier JSON"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    self._stats = json.load(f)
                logger.info("Statistiques chargées depuis %s", self.storage_path)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Erreur chargement stats: %s. Initialisation.", e)
                self._stats = self._default_stats()
        else:
            logger.info("Aucun fichier de stats existant. Initialisation.")
            self._stats = self._default_stats()
            self._save()

    def _save(self) -> None:
        """Sauvegarde les statistiques dans le fichier JSON"""
        try:
            self._stats["last_updated"] = datetime.now().isoformat()
            with open(self.storage_path, 'w') as f:
                json.dump(self._stats, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error("Erreur sauvegarde stats: %s", e)

    def track_request(self, method: str, status_code: int) -> None:
        """Enregistre une requête HTTP"""
        with self._lock:
            self._stats["requests"]["total"] += 1

            method_key = method.upper()
            self._stats["requests"]["by_method"][method_key] = \
                self._stats["requests"]["by_method"].get(method_key, 0) + 1

            status_key = str(status_code)
            self._stats["requests"]["by_status"][status_key] = \
                self._stats["requests"]["by_status"].get(status_key, 0) + 1

            self._save()

    def track_conversion(
        self,
        success: bool,
        is_async: bool = False,
        has_chassis: bool = False,
        has_payment: bool = False
    ) -> None:
        """Enregistre une conversion"""
        with self._lock:
            self._stats["conversions"]["total"] += 1

            if success:
                self._stats["conversions"]["successful"] += 1
            else:
                self._stats["conversions"]["failed"] += 1

            if is_async:
                self._stats["conversions"]["async"] += 1
            else:
                self._stats["conversions"]["sync"] += 1

            if has_chassis:
                self._stats["conversions"]["with_chassis"] += 1

            if has_payment:
                self._stats["conversions"]["with_payment"] += 1

            self._save()

    def track_batch(self, successful: int, failed: int, files_processed: int) -> None:
        """Enregistre un traitement batch"""
        with self._lock:
            self._stats["batches"]["total"] += 1

            if failed == 0:
                self._stats["batches"]["successful"] += 1
            else:
                self._stats["batches"]["failed"] += 1

            self._stats["batches"]["total_files_processed"] += files_processed

            self._save()

    def track_chassis_generation(self, vins_count: int) -> None:
        """Enregistre une génération de VINs"""
        with self._lock:
            self._stats["chassis"]["generation_requests"] += 1
            self._stats["chassis"]["total_vins_generated"] += vins_count

            self._save()

    def get_stats(self) -> Dict[str, Any]:
        """Retourne toutes les statistiques"""
        with self._lock:
            return self._stats.copy()

    def get_conversion_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de conversion"""
        with self._lock:
            return self._stats["conversions"].copy()

    def get_request_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de requêtes"""
        with self._lock:
            return self._stats["requests"].copy()


def _create_usage_stats() -> UsageStatsService:
    """Crée le singleton avec le chemin depuis settings"""
    try:
        from ..core.config import settings
        return UsageStatsService(settings.stats_file)
    except Exception:
        return UsageStatsService()


# Singleton global
usage_stats = _create_usage_stats()
