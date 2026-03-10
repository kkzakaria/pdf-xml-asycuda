"""
Registre de numéros de châssis RFCV
====================================

Deux registres SQLite séparés :
- extracted_chassis : châssis extraits des PDFs RFCV
- generated_chassis : VINs générés automatiquement

Usage:
    from chassis_registry import ChassisRegistry, get_registry

    registry = get_registry()
    existing = registry.check_extracted("ABC123456789012")
    if existing:
        raise DuplicateChassisError([existing])
    registry.register_extracted("ABC123456789012", "DOSSIER.pdf", "CI-2025-001")
"""

import sqlite3
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DB_DEFAULT = str(Path(__file__).parent.parent / "data" / "chassis_registry.db")


class DuplicateChassisError(Exception):
    """Levée quand un ou plusieurs châssis ont déjà été traités"""

    def __init__(self, duplicates: List[Dict]):
        self.duplicates = duplicates
        super().__init__(f"{len(duplicates)} châssis en doublon détecté(s)")


class ChassisRegistry:
    """
    Registre SQLite thread-safe pour tracer les numéros de châssis RFCV.

    Tables:
        extracted_chassis — châssis lus dans les PDFs
        generated_chassis — VINs générés automatiquement

    Attributes:
        db_path: Chemin vers le fichier SQLite
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or _DB_DEFAULT)
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        logger.info("ChassisRegistry initialisé: %s", self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS extracted_chassis (
                    chassis_number TEXT PRIMARY KEY,
                    registered_at  TEXT NOT NULL,
                    filename       TEXT NOT NULL,
                    rfcv_number    TEXT
                );
                CREATE TABLE IF NOT EXISTS generated_chassis (
                    chassis_number TEXT PRIMARY KEY,
                    registered_at  TEXT NOT NULL,
                    filename       TEXT NOT NULL,
                    rfcv_number    TEXT
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row) -> Optional[Dict]:
        return dict(row) if row else None

    # --- Extracted chassis ---

    def check_extracted(self, chassis_number: str) -> Optional[Dict]:
        """Retourne l'entrée existante pour ce châssis extrait, ou None."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM extracted_chassis WHERE chassis_number = ?",
                    (chassis_number.upper(),)
                ).fetchone()
                return self._row_to_dict(row)

    def register_extracted(self, chassis_number: str, filename: str, rfcv_number: Optional[str]) -> None:
        """Enregistre un châssis extrait. Lève ValueError si déjà présent."""
        cn = chassis_number.upper()
        with self._lock:
            with self._connect() as conn:
                try:
                    conn.execute(
                        "INSERT INTO extracted_chassis (chassis_number, registered_at, filename, rfcv_number) "
                        "VALUES (?, ?, ?, ?)",
                        (cn, self._now(), filename, rfcv_number)
                    )
                except sqlite3.IntegrityError:
                    raise ValueError(f"Châssis extrait déjà enregistré: {cn}")

    def get_all_extracted(self) -> List[Dict]:
        """Retourne tous les châssis extraits, du plus récent au plus ancien."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM extracted_chassis ORDER BY registered_at DESC"
                ).fetchall()
                return [dict(r) for r in rows]

    # --- Generated chassis ---

    def check_generated(self, chassis_number: str) -> Optional[Dict]:
        """Retourne l'entrée existante pour ce VIN généré, ou None."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM generated_chassis WHERE chassis_number = ?",
                    (chassis_number.upper(),)
                ).fetchone()
                return self._row_to_dict(row)

    def register_generated(self, chassis_number: str, filename: str, rfcv_number: Optional[str]) -> None:
        """Enregistre un VIN généré. Ignore silencieusement si déjà présent."""
        cn = chassis_number.upper()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO generated_chassis "
                    "(chassis_number, registered_at, filename, rfcv_number) VALUES (?, ?, ?, ?)",
                    (cn, self._now(), filename, rfcv_number)
                )

    def get_all_generated(self) -> List[Dict]:
        """Retourne tous les VINs générés, du plus récent au plus ancien."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM generated_chassis ORDER BY registered_at DESC"
                ).fetchall()
                return [dict(r) for r in rows]

    # --- Admin ---

    def get_entry(self, chassis_number: str) -> Optional[Dict]:
        """Cherche dans les deux tables. Retourne l'entrée avec champ 'table'."""
        entry = self.check_extracted(chassis_number)
        if entry:
            entry["table"] = "extracted"
            return entry
        entry = self.check_generated(chassis_number)
        if entry:
            entry["table"] = "generated"
            return entry
        return None

    def delete(self, chassis_number: str) -> bool:
        """Supprime de l'une ou l'autre table. Retourne True si supprimé."""
        cn = chassis_number.upper()
        with self._lock:
            with self._connect() as conn:
                r1 = conn.execute(
                    "DELETE FROM extracted_chassis WHERE chassis_number = ?", (cn,)
                ).rowcount
                r2 = conn.execute(
                    "DELETE FROM generated_chassis WHERE chassis_number = ?", (cn,)
                ).rowcount
                return (r1 + r2) > 0


# Singleton global — thread-safe via double-check
_registry: Optional[ChassisRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ChassisRegistry:
    """Retourne l'instance singleton du registre (thread-safe)."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ChassisRegistry()
    return _registry
