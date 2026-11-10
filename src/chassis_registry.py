"""
Registre de numéros de châssis RFCV
====================================

Registres SQLite :
- extracted_chassis : châssis extraits des PDFs RFCV
- generated_chassis : VINs générés automatiquement
- cancelled_chassis : historique des annulations (RFCV annulé par la société d'inspection,
  éclaté en d'autres RFCV…). Annuler un RFCV y déplace ses châssis extraits : ils peuvent alors
  réapparaître dans un nouveau RFCV sans être signalés en doublon, et l'annulation reste tracée.

Usage:
    from chassis_registry import ChassisRegistry, get_registry

    registry = get_registry()
    existing = registry.check_extracted("ABC123456789012")
    if existing:
        raise DuplicateChassisError([existing])
    registry.register_extracted("ABC123456789012", "DOSSIER.pdf", "CI-2025-001")
"""

import re
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
                CREATE TABLE IF NOT EXISTS cancelled_chassis (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    chassis_number TEXT NOT NULL,
                    registered_at  TEXT NOT NULL,
                    filename       TEXT NOT NULL,
                    rfcv_number    TEXT,
                    cancelled_at   TEXT NOT NULL,
                    reason         TEXT NOT NULL,
                    restored_at    TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_cancelled_chassis ON cancelled_chassis (chassis_number);
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

    def register_extracted(
        self,
        chassis_number: str,
        filename: str,
        rfcv_number: Optional[str],
        overwrite: bool = False,
    ) -> None:
        """Enregistre un châssis extrait.

        Args:
            chassis_number: Numéro de châssis à enregistrer.
            filename: Nom du fichier PDF source.
            rfcv_number: Numéro RFCV associé.
            overwrite: Si True, utilise INSERT OR REPLACE (écrase l'entrée existante).
                       Si False (défaut), lève ValueError si le châssis est déjà présent.
        """
        cn = chassis_number.upper()
        with self._lock:
            with self._connect() as conn:
                if overwrite:
                    conn.execute(
                        "INSERT OR REPLACE INTO extracted_chassis "
                        "(chassis_number, registered_at, filename, rfcv_number) "
                        "VALUES (?, ?, ?, ?)",
                        (cn, self._now(), filename, rfcv_number)
                    )
                else:
                    try:
                        conn.execute(
                            "INSERT INTO extracted_chassis "
                            "(chassis_number, registered_at, filename, rfcv_number) "
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


    # --- Annulation d'un RFCV ---

    def _rfcv_numbers(self, conn, table: str, rfcv_number: str) -> List[str]:
        """Numéros RFCV stockés dans la table qui désignent le même RFCV (normalize_rfcv)."""
        target = normalize_rfcv(rfcv_number)
        rows = conn.execute(f"SELECT DISTINCT rfcv_number FROM {table} WHERE rfcv_number IS NOT NULL").fetchall()
        return [r[0] for r in rows if normalize_rfcv(r[0]) == target]

    def cancel_rfcv(self, rfcv_number: str, reason: str,
                    chassis_numbers: Optional[List[str]] = None) -> List[str]:
        """
        Annule un RFCV : ses châssis extraits passent dans cancelled_chassis (avec le motif et la
        date) et ne bloquent plus un nouveau RFCV. chassis_numbers limite l'annulation à ces
        châssis du RFCV. Rend les châssis annulés (liste vide si le RFCV n'a aucun châssis
        enregistré). Le motif est obligatoire.
        """
        if not reason or not reason.strip():
            raise ValueError("Motif d'annulation obligatoire")
        if not normalize_rfcv(rfcv_number):
            raise ValueError(f"Numéro RFCV invalide: {rfcv_number!r}")
        only = {c.upper() for c in chassis_numbers} if chassis_numbers else None
        now = self._now()
        with self._lock:
            with self._connect() as conn:
                numbers = self._rfcv_numbers(conn, "extracted_chassis", rfcv_number)
                if not numbers:
                    return []
                marks = ",".join("?" * len(numbers))
                rows = conn.execute(
                    f"SELECT * FROM extracted_chassis WHERE rfcv_number IN ({marks}) ORDER BY chassis_number",
                    numbers).fetchall()
                rows = [r for r in rows if only is None or r["chassis_number"] in only]
                for r in rows:
                    conn.execute(
                        "INSERT INTO cancelled_chassis (chassis_number, registered_at, filename, rfcv_number, "
                        "cancelled_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
                        (r["chassis_number"], r["registered_at"], r["filename"], r["rfcv_number"], now, reason.strip()))
                    conn.execute("DELETE FROM extracted_chassis WHERE chassis_number = ?", (r["chassis_number"],))
                cancelled = [r["chassis_number"] for r in rows]
        logger.info("RFCV %s annulé : %d châssis (%s)", rfcv_number, len(cancelled), reason.strip())
        return cancelled

    def restore_rfcv(self, rfcv_number: str) -> Dict[str, List[str]]:
        """
        Annule l'annulation d'un RFCV (erreur de manipulation) : ses châssis annulés et non encore
        restaurés reviennent dans extracted_chassis. Un châssis repris entre-temps par un autre RFCV
        n'est pas restauré (conflicts). Rend {"restored": [...], "conflicts": [...]}.
        """
        now = self._now()
        restored, conflicts = [], []
        with self._lock:
            with self._connect() as conn:
                numbers = self._rfcv_numbers(conn, "cancelled_chassis", rfcv_number)
                if not numbers:
                    return {"restored": [], "conflicts": []}
                marks = ",".join("?" * len(numbers))
                rows = conn.execute(
                    f"SELECT * FROM cancelled_chassis WHERE rfcv_number IN ({marks}) AND restored_at IS NULL "
                    "ORDER BY chassis_number", numbers).fetchall()
                for r in rows:
                    taken = conn.execute("SELECT 1 FROM extracted_chassis WHERE chassis_number = ?",
                                         (r["chassis_number"],)).fetchone()
                    if taken:
                        conflicts.append(r["chassis_number"])
                        continue
                    conn.execute(
                        "INSERT INTO extracted_chassis (chassis_number, registered_at, filename, rfcv_number) "
                        "VALUES (?, ?, ?, ?)", (r["chassis_number"], r["registered_at"], r["filename"], r["rfcv_number"]))
                    conn.execute("UPDATE cancelled_chassis SET restored_at = ? WHERE id = ?", (now, r["id"]))
                    restored.append(r["chassis_number"])
        logger.info("RFCV %s restauré : %d châssis, %d en conflit", rfcv_number, len(restored), len(conflicts))
        return {"restored": restored, "conflicts": conflicts}

    def get_cancelled(self, rfcv_number: Optional[str] = None, chassis_number: Optional[str] = None) -> List[Dict]:
        """Historique des annulations (le plus récent d'abord), filtré par RFCV ou par châssis."""
        with self._lock:
            with self._connect() as conn:
                rows = [dict(r) for r in conn.execute(
                    "SELECT * FROM cancelled_chassis ORDER BY cancelled_at DESC, chassis_number").fetchall()]
        if rfcv_number:
            target = normalize_rfcv(rfcv_number)
            rows = [r for r in rows if normalize_rfcv(r["rfcv_number"]) == target]
        if chassis_number:
            rows = [r for r in rows if r["chassis_number"] == chassis_number.upper()]
        return rows


def normalize_rfcv(value: Optional[str]) -> str:
    """'RCSA6014576', 'rcsa 6014576', '6014576' -> '6014576' ; 'RCS26159491' -> '26159491'."""
    if not value:
        return ""
    v = re.sub(r"\s+", "", value).upper()
    return re.sub(r"^RCS[A-Z]?(?=\d)", "", v)


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
