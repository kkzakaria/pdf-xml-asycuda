"""
Service de statistiques d'utilisation de l'API
Persistance JSON thread-safe (pattern ChassisSequenceManager)
"""

import json
import threading
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Flush périodique : sauvegarde toutes les N secondes ou N mutations
_FLUSH_INTERVAL_SECONDS = 30
_FLUSH_INTERVAL_MUTATIONS = 100


class UsageStatsService:
    """
    Service de statistiques d'utilisation avec persistance JSON.

    Thread-safe via threading.Lock.
    Sauvegarde périodique (toutes les 30s ou 100 mutations) pour éviter
    l'I/O disque à chaque requête.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            storage_path = str(Path(__file__).parent.parent.parent.parent / "data" / "usage_stats.json")

        self.storage_path = Path(storage_path)
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {}
        self._dirty = False
        self._mutations_since_flush = 0
        self._last_flush_time = time.monotonic()

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
                "total_files_processed": 0,
                "successful_files": 0,
                "failed_files": 0
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
                # Migration : ajouter les champs manquants si upgrade
                batches = self._stats.get("batches", {})
                if "successful_files" not in batches:
                    batches["successful_files"] = 0
                if "failed_files" not in batches:
                    batches["failed_files"] = 0
                logger.info("Statistiques chargées depuis %s", self.storage_path)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Erreur chargement stats: %s. Initialisation.", e)
                self._stats = self._default_stats()
        else:
            logger.info("Aucun fichier de stats existant. Initialisation.")
            self._stats = self._default_stats()
            self._force_save()

    def _force_save(self) -> None:
        """Sauvegarde immédiate sur disque (appelé sous lock)"""
        try:
            self._stats["last_updated"] = datetime.now().isoformat()
            with open(self.storage_path, 'w') as f:
                json.dump(self._stats, f, indent=2, ensure_ascii=False)
            self._dirty = False
            self._mutations_since_flush = 0
            self._last_flush_time = time.monotonic()
        except IOError as e:
            logger.error("Erreur sauvegarde stats: %s", e)

    def _maybe_flush(self) -> None:
        """Flush si le seuil de mutations ou le délai est atteint (appelé sous lock)"""
        self._dirty = True
        self._mutations_since_flush += 1

        elapsed = time.monotonic() - self._last_flush_time
        if (self._mutations_since_flush >= _FLUSH_INTERVAL_MUTATIONS
                or elapsed >= _FLUSH_INTERVAL_SECONDS):
            self._force_save()

    def flush(self) -> None:
        """Force la sauvegarde si des données sont en attente. Safe à appeler au shutdown."""
        with self._lock:
            if self._dirty:
                self._force_save()

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

            self._maybe_flush()

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

            self._maybe_flush()

    def track_batch(self, successful: int, failed: int, files_processed: int) -> None:
        """Enregistre un traitement batch avec compteurs par fichier"""
        with self._lock:
            self._stats["batches"]["total"] += 1
            self._stats["batches"]["total_files_processed"] += files_processed
            self._stats["batches"]["successful_files"] += successful
            self._stats["batches"]["failed_files"] += failed

            if failed == 0:
                self._stats["batches"]["successful"] += 1
            else:
                self._stats["batches"]["failed"] += 1

            self._maybe_flush()

    def track_chassis_generation(self, vins_count: int) -> None:
        """Enregistre une génération de VINs"""
        with self._lock:
            self._stats["chassis"]["generation_requests"] += 1
            self._stats["chassis"]["total_vins_generated"] += vins_count

            self._maybe_flush()

    def get_stats(self) -> Dict[str, Any]:
        """Retourne toutes les statistiques"""
        with self._lock:
            return json.loads(json.dumps(self._stats))

    def get_conversion_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de conversion"""
        with self._lock:
            return self._stats["conversions"].copy()

    def get_request_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de requêtes"""
        with self._lock:
            return json.loads(json.dumps(self._stats["requests"]))


# Lazy singleton
_usage_stats: Optional[UsageStatsService] = None
_singleton_lock = threading.Lock()


def get_usage_stats() -> UsageStatsService:
    """Retourne le singleton UsageStatsService (créé au premier appel)"""
    global _usage_stats
    if _usage_stats is None:
        with _singleton_lock:
            if _usage_stats is None:
                try:
                    from ..core.config import settings
                    _usage_stats = UsageStatsService(settings.stats_file)
                except Exception:
                    _usage_stats = UsageStatsService()
    return _usage_stats


def reset_usage_stats() -> None:
    """Réinitialise le singleton (pour les tests)"""
    global _usage_stats
    with _singleton_lock:
        if _usage_stats is not None:
            _usage_stats.flush()
        _usage_stats = None
