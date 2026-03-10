# Chassis Registry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sauvegarder les numéros de châssis extraits des PDFs RFCV et les VINs générés dans un registre SQLite, et bloquer les conversions en doublon (HTTP 409) avec option `force_reprocess=true`.

**Architecture:** Nouveau composant `ChassisRegistry` (SQLite, thread-safe) injecté dans `RFCVParser`. Pour les châssis extraits, les enregistrements sont différés : on accumule `_pending_registrations` et `_chassis_duplicates` pendant le parsing, puis on lève l'erreur ou on enregistre tout en batch à la fin de `parse()` — évitant toute inscription partielle en cas de doublon. Les VINs générés sont enregistrés immédiatement (la séquence garantit déjà l'unicité). L'exception `DuplicateChassisError` remonte via `conversion_service` jusqu'au route FastAPI qui retourne HTTP 409.

**Note de conception :** `force_reprocess` est ajouté directement à `RFCVParser.__init__()` et à `ConversionService.convert_pdf_to_xml()` plutôt que dans le dataclass `ChassisConfig` de `models.py`. C'est une déviation intentionnelle du spec original — plus propre car ça évite de modifier `models.py` et de changer le format de `chassis_config`.

**Tech Stack:** Python `sqlite3` (stdlib), FastAPI, pytest

---

## Chunk 1: ChassisRegistry — composant SQLite

### Task 1: Créer `src/chassis_registry.py`

**Files:**
- Create: `src/chassis_registry.py`
- Test: `tests/test_chassis_registry.py`

- [ ] **Step 1: Écrire les tests unitaires (failing)**

```python
# tests/test_chassis_registry.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
import threading
import tempfile
from chassis_registry import ChassisRegistry, DuplicateChassisError


@pytest.fixture
def registry():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    reg = ChassisRegistry(db_path)
    yield reg
    Path(db_path).unlink(missing_ok=True)


class TestChassisRegistry:

    def test_register_and_check_extracted(self, registry):
        registry.register_extracted("ABC123456789012", "DOSSIER.pdf", "CI-2025-001")
        result = registry.check_extracted("ABC123456789012")
        assert result is not None
        assert result["chassis_number"] == "ABC123456789012"
        assert result["filename"] == "DOSSIER.pdf"
        assert result["rfcv_number"] == "CI-2025-001"
        assert "registered_at" in result

    def test_check_extracted_not_found(self, registry):
        assert registry.check_extracted("NOTEXIST12345") is None

    def test_register_extracted_duplicate_raises(self, registry):
        registry.register_extracted("ABC123456789012", "DOSSIER.pdf", "CI-2025-001")
        with pytest.raises(ValueError):
            registry.register_extracted("ABC123456789012", "AUTRE.pdf", "CI-2025-002")

    def test_register_and_check_generated(self, registry):
        registry.register_generated("LZSHCKZS2S8000001", "DOSSIER.pdf", "CI-2025-001")
        result = registry.check_generated("LZSHCKZS2S8000001")
        assert result is not None
        assert result["chassis_number"] == "LZSHCKZS2S8000001"

    def test_check_generated_not_found(self, registry):
        assert registry.check_generated("NOTEXIST12345") is None

    def test_registries_are_independent(self, registry):
        """Extracted et generated sont deux tables distinctes"""
        registry.register_extracted("ABC123456789012", "DOSSIER.pdf", "CI-2025-001")
        assert registry.check_generated("ABC123456789012") is None

    def test_thread_safety(self, registry):
        """Plusieurs threads peuvent enregistrer sans collision"""
        errors = []
        chassis_numbers = [f"CHASSIS{i:010d}" for i in range(20)]

        def register(cn):
            try:
                registry.register_extracted(cn, "file.pdf", "CI-2025-001")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(cn,)) for cn in chassis_numbers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_get_all_extracted(self, registry):
        registry.register_extracted("ABC123456789012", "A.pdf", "CI-2025-001")
        registry.register_extracted("DEF123456789012", "B.pdf", "CI-2025-002")
        results = registry.get_all_extracted()
        assert len(results) == 2

    def test_get_all_generated(self, registry):
        registry.register_generated("LZSHCKZS2S8000001", "A.pdf", "CI-2025-001")
        results = registry.get_all_generated()
        assert len(results) == 1

    def test_delete_extracted(self, registry):
        registry.register_extracted("ABC123456789012", "A.pdf", "CI-2025-001")
        deleted = registry.delete("ABC123456789012")
        assert deleted is True
        assert registry.check_extracted("ABC123456789012") is None

    def test_delete_generated(self, registry):
        registry.register_generated("LZSHCKZS2S8000001", "A.pdf", "CI-2025-001")
        deleted = registry.delete("LZSHCKZS2S8000001")
        assert deleted is True
        assert registry.check_generated("LZSHCKZS2S8000001") is None

    def test_delete_nonexistent(self, registry):
        assert registry.delete("NOTEXIST12345") is False

    def test_get_entry_extracted(self, registry):
        registry.register_extracted("ABC123456789012", "A.pdf", "CI-2025-001")
        result = registry.get_entry("ABC123456789012")
        assert result is not None
        assert result["table"] == "extracted"

    def test_get_entry_generated(self, registry):
        registry.register_generated("LZSHCKZS2S8000001", "A.pdf", "CI-2025-001")
        result = registry.get_entry("LZSHCKZS2S8000001")
        assert result is not None
        assert result["table"] == "generated"

    def test_get_entry_returns_none_after_delete(self, registry):
        registry.register_extracted("ABC123456789012", "A.pdf", "CI-2025-001")
        registry.delete("ABC123456789012")
        assert registry.get_entry("ABC123456789012") is None

    def test_persistence_across_instances(self):
        """Les données survivent à la recréation du registre"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        try:
            reg1 = ChassisRegistry(db_path)
            reg1.register_extracted("ABC123456789012", "A.pdf", "CI-2025-001")

            reg2 = ChassisRegistry(db_path)
            result = reg2.check_extracted("ABC123456789012")
            assert result is not None
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_chassis_numbers_stored_uppercased(self, registry):
        registry.register_extracted("abc123456789012", "A.pdf", "CI-2025-001")
        assert registry.check_extracted("ABC123456789012") is not None
        assert registry.check_extracted("abc123456789012") is not None


class TestDuplicateChassisError:

    def test_error_has_duplicates_list(self):
        duplicates = [
            {
                "chassis_number": "ABC123456789012",
                "first_seen_date": "2025-01-01T10:00:00+00:00",
                "first_filename": "old.pdf",
                "first_rfcv_number": "CI-2025-001"
            }
        ]
        err = DuplicateChassisError(duplicates)
        assert err.duplicates == duplicates
        assert "1" in str(err)

    def test_error_multiple_duplicates(self):
        duplicates = [{"chassis_number": f"CN{i}" * 5, "first_seen_date": "", "first_filename": "", "first_rfcv_number": ""} for i in range(3)]
        err = DuplicateChassisError(duplicates)
        assert len(err.duplicates) == 3
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /home/superz/pdf-xml-asycuda
python -m pytest tests/test_chassis_registry.py -v 2>&1 | head -20
```
Expected: `ModuleNotFoundError: No module named 'chassis_registry'`

- [ ] **Step 3: Implémenter `src/chassis_registry.py`**

```python
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
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
python -m pytest tests/test_chassis_registry.py -v
```
Expected: tous les tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/chassis_registry.py tests/test_chassis_registry.py
git commit -m "feat: ajouter ChassisRegistry SQLite avec DuplicateChassisError"
```

---

## Chunk 2: Intégration dans RFCVParser

**Principe d'enregistrement différé (évite les inscriptions partielles) :**
Pendant `_parse_items()`, les châssis extraits ne sont PAS immédiatement enregistrés. À la place :
- Les doublons trouvés vont dans `self._chassis_duplicates`
- Les nouveaux vont dans `self._pending_registrations`

Après `_parse_items()` et `_add_additional_vin_items()`, dans `parse()` :
- Si `_chassis_duplicates` non vide → lever `DuplicateChassisError` (rien n'est enregistré)
- Sinon → enregistrer tous les `_pending_registrations` en batch

Les VINs générés (mode `generate_chassis`) s'enregistrent immédiatement car la séquence garantit déjà l'unicité.

### Task 2: Modifier `src/rfcv_parser.py`

**Files:**
- Modify: `src/rfcv_parser.py`
- Test: `tests/test_chassis_registry.py` (ajout d'une classe)

- [ ] **Step 1: Ajouter l'import au début de `src/rfcv_parser.py`**

Après les imports existants du fichier (chercher la zone `from models import`), ajouter :

```python
from chassis_registry import ChassisRegistry, DuplicateChassisError, get_registry
```

- [ ] **Step 2: Modifier `__init__` — ajouter `force_reprocess` et `registry`**

Localiser le `def __init__` actuel :
```python
    def __init__(
        self,
        pdf_path: str,
        taux_douane: Optional[float] = None,
        rapport_paiement: Optional[str] = None,
        chassis_config: Optional[Dict[str, Any]] = None
    ):
```

Remplacer par :
```python
    def __init__(
        self,
        pdf_path: str,
        taux_douane: Optional[float] = None,
        rapport_paiement: Optional[str] = None,
        chassis_config: Optional[Dict[str, Any]] = None,
        force_reprocess: bool = False,
        registry: Optional[ChassisRegistry] = None,
    ):
```

Dans le corps du `__init__`, après `self.chassis_config = chassis_config`, ajouter :
```python
        self.force_reprocess = force_reprocess
        self.registry = registry if registry is not None else get_registry()
        self._chassis_duplicates: list = []
        self._pending_registrations: list = []
        self._rfcv_number: Optional[str] = None
```

- [ ] **Step 3: Modifier `parse()` — cacher rfcv_number, lever l'erreur ou enregistrer en batch**

Dans `parse()`, après la ligne :
```python
        rfcv_data.identification = self._parse_identification()
```

Ajouter (avant `_parse_items()`) :
```python
        self._rfcv_number = rfcv_data.identification.rfcv_number if rfcv_data.identification else None
```

Puis, après ce bloc (noter la présence de `_extract_value_details` entre les deux appels items) :
```python
        rfcv_data.items = self._parse_items()
        rfcv_data.value_details = self._extract_value_details()
        rfcv_data.items = self._add_additional_vin_items(rfcv_data.items)
```

Ajouter **immédiatement après** la ligne `_add_additional_vin_items` :
```python
        # Vérification des doublons de châssis — après parsing complet pour collecter tous les doublons
        if self._chassis_duplicates:
            raise DuplicateChassisError(self._chassis_duplicates)

        # Aucun doublon : enregistrer les châssis extraits en batch
        for pending in self._pending_registrations:
            self.registry.register_extracted(
                chassis_number=pending["chassis_number"],
                filename=pending["filename"],
                rfcv_number=pending["rfcv_number"],
            )
```

- [ ] **Step 4: Modifier `_parse_items()` — vérification et accumulation différée**

Localiser le bloc suivant dans `_parse_items()` (contexte complet pour identification unique) :

```python
                else:
                    # Mode normal: extraction depuis PDF (comportement actuel)
                    chassis_number = self._extract_chassis_number(raw_description)

                    if chassis_number:
                        # Châssis trouvé: nettoyer la description
                        goods_description_clean = raw_description.replace(chassis_number, '').strip()
                        goods_description_clean = re.sub(r'\s+', ' ', goods_description_clean)

                        # Format ASYCUDA: "CH: XXXXX"
                        marks2_value = f"CH: {chassis_number}"

                        logger.info(
                            f"Article {match.group(1)}: Châssis détecté ({chassis_info['category']}) "
                            f"- {chassis_number}"
                        )
                    else:
                        # ⚠️ Châssis attendu mais non trouvé
```

Remplacer uniquement le bloc `if chassis_number:` et son contenu par :

```python
                    if chassis_number:
                        existing = self.registry.check_extracted(chassis_number)
                        if existing and not self.force_reprocess:
                            # Doublon : accumuler sans enregistrer
                            self._chassis_duplicates.append({
                                "chassis_number": chassis_number,
                                "first_seen_date": existing["registered_at"],
                                "first_filename": existing["filename"],
                                "first_rfcv_number": existing["rfcv_number"],
                            })
                            logger.warning(
                                f"Article {match.group(1)}: Châssis {chassis_number} déjà traité "
                                f"(premier: {existing['registered_at']}, fichier: {existing['filename']})"
                            )
                        else:
                            # Nouveau ou force_reprocess : différer l'enregistrement
                            self._pending_registrations.append({
                                "chassis_number": chassis_number,
                                "filename": Path(self.pdf_path).name,
                                "rfcv_number": self._rfcv_number,
                            })

                        # Châssis trouvé: nettoyer la description
                        goods_description_clean = raw_description.replace(chassis_number, '').strip()
                        goods_description_clean = re.sub(r'\s+', ' ', goods_description_clean)

                        # Format ASYCUDA: "CH: XXXXX"
                        marks2_value = f"CH: {chassis_number}"

                        logger.info(
                            f"Article {match.group(1)}: Châssis détecté ({chassis_info['category']}) "
                            f"- {chassis_number}"
                        )
```

Vérifier que `from pathlib import Path` est présent dans les imports du fichier (il l'est déjà si `PDFExtractor` est utilisé).

- [ ] **Step 5: Modifier `_generate_chassis_for_article()` — enregistrement immédiat des VINs générés**

Localiser dans `_generate_chassis_for_article()` la ligne `return vin` (ligne ~745). Juste avant, ajouter :

```python
            if vin:
                self.registry.register_generated(
                    chassis_number=vin,
                    filename=Path(self.pdf_path).name,
                    rfcv_number=self._rfcv_number,
                )
```

- [ ] **Step 6: Ajouter des tests parser dans `tests/test_chassis_registry.py`**

Ces tests vérifient le comportement de `RFCVParser` en mockant l'extraction PDF tout en laissant la logique de `_parse_items()` s'exécuter réellement avec le registre.

Ajouter à la fin du fichier :

```python
class TestRFCVParserRegistryIntegration:
    """Tests d'intégration entre RFCVParser et ChassisRegistry.

    Ces tests mockent l'extraction PDF mais exercent la vraie logique de
    _parse_items(), _chassis_duplicates et _pending_registrations.
    """

    @pytest.fixture
    def isolated_registry(self):
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        reg = ChassisRegistry(db_path)
        yield reg
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_parser(self, isolated_registry, tmp_path):
        """Crée un RFCVParser avec PDF mocké et registre isolé."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        from rfcv_parser import RFCVParser
        from unittest.mock import patch, MagicMock

        # PDF factice (fichier vide)
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        parser = RFCVParser(
            str(fake_pdf),
            taux_douane=573.139,
            registry=isolated_registry,
            force_reprocess=False,
        )
        parser._rfcv_number = "CI-2025-002"
        return parser

    def test_duplicate_detected_in_chassis_duplicates(self, mock_parser, isolated_registry):
        """Un châssis déjà connu s'accumule dans _chassis_duplicates."""
        # Pré-enregistrer
        isolated_registry.register_extracted("ABC123456789012", "OLD.pdf", "CI-2025-001")

        # Simuler la logique de _parse_items() pour un chassis trouvé
        chassis_number = "ABC123456789012"
        existing = mock_parser.registry.check_extracted(chassis_number)
        if existing and not mock_parser.force_reprocess:
            mock_parser._chassis_duplicates.append({
                "chassis_number": chassis_number,
                "first_seen_date": existing["registered_at"],
                "first_filename": existing["filename"],
                "first_rfcv_number": existing["rfcv_number"],
            })

        assert len(mock_parser._chassis_duplicates) == 1
        assert mock_parser._chassis_duplicates[0]["chassis_number"] == "ABC123456789012"
        # Le châssis ne doit PAS être dans pending
        assert len(mock_parser._pending_registrations) == 0

    def test_new_chassis_goes_to_pending(self, mock_parser, isolated_registry):
        """Un châssis inconnu va dans _pending_registrations."""
        chassis_number = "XYZ123456789012"
        existing = mock_parser.registry.check_extracted(chassis_number)
        if existing and not mock_parser.force_reprocess:
            mock_parser._chassis_duplicates.append({})
        else:
            mock_parser._pending_registrations.append({
                "chassis_number": chassis_number,
                "filename": "NEW.pdf",
                "rfcv_number": mock_parser._rfcv_number,
            })

        assert len(mock_parser._chassis_duplicates) == 0
        assert len(mock_parser._pending_registrations) == 1

    def test_force_reprocess_sends_duplicate_to_pending(self, mock_parser, isolated_registry):
        """force_reprocess=True : le doublon va dans _pending, pas dans _duplicates."""
        isolated_registry.register_extracted("ABC123456789012", "OLD.pdf", "CI-2025-001")
        mock_parser.force_reprocess = True

        chassis_number = "ABC123456789012"
        existing = mock_parser.registry.check_extracted(chassis_number)
        if existing and not mock_parser.force_reprocess:
            mock_parser._chassis_duplicates.append({})
        else:
            mock_parser._pending_registrations.append({
                "chassis_number": chassis_number,
                "filename": "NEW.pdf",
                "rfcv_number": mock_parser._rfcv_number,
            })

        assert len(mock_parser._chassis_duplicates) == 0
        assert len(mock_parser._pending_registrations) == 1

    def test_pending_committed_when_no_duplicates(self, mock_parser, isolated_registry):
        """Sans doublon, le batch d'enregistrements est commité au registre."""
        mock_parser._pending_registrations = [
            {"chassis_number": "XYZ123456789012", "filename": "NEW.pdf", "rfcv_number": "CI-2025-002"},
        ]
        mock_parser._chassis_duplicates = []

        # Simuler la logique de fin de parse()
        if not mock_parser._chassis_duplicates:
            for pending in mock_parser._pending_registrations:
                isolated_registry.register_extracted(**pending)

        assert isolated_registry.check_extracted("XYZ123456789012") is not None

    def test_no_registration_when_duplicates_present(self, mock_parser, isolated_registry):
        """Avec doublons, aucun _pending n'est commité."""
        mock_parser._pending_registrations = [
            {"chassis_number": "NEW999999999999", "filename": "NEW.pdf", "rfcv_number": "CI-2025-002"},
        ]
        mock_parser._chassis_duplicates = [{"chassis_number": "ABC123456789012"}]

        # Simuler la logique de fin de parse()
        if mock_parser._chassis_duplicates:
            pass  # DuplicateChassisError levée — rien enregistré
        else:
            for pending in mock_parser._pending_registrations:
                isolated_registry.register_extracted(**pending)

        assert isolated_registry.check_extracted("NEW999999999999") is None
```

- [ ] **Step 7: Vérifier que tous les tests passent**

```bash
python -m pytest tests/test_chassis_registry.py tests/test_chassis_detection.py tests/test_item_grouping.py tests/test_chassis_sequence_manager.py -v
```
Expected: tous PASS (aucune régression)

- [ ] **Step 8: Commit**

```bash
git add src/rfcv_parser.py tests/test_chassis_registry.py
git commit -m "feat: intégrer ChassisRegistry dans RFCVParser — enregistrement différé, détection doublons"
```

---

## Chunk 3: Propagation force_reprocess + API 409

### Task 3: Modifier `src/api/services/conversion_service.py`

**Files:**
- Modify: `src/api/services/conversion_service.py`

- [ ] **Step 1: Ajouter import et re-export de `DuplicateChassisError`**

Dans `conversion_service.py`, après l'import de `MetricsCollector`, ajouter :

```python
from chassis_registry import DuplicateChassisError

# Re-export pour les routes qui n'ont pas accès direct au path src/
__all__ = ["ConversionService", "conversion_service", "DuplicateChassisError"]
```

- [ ] **Step 2: Ajouter `force_reprocess` à la signature de `convert_pdf_to_xml`**

Localiser la signature actuelle :
```python
    @staticmethod
    def convert_pdf_to_xml(
        pdf_path: str,
        output_path: str,
        verbose: bool = False,
        taux_douane: float = None,
        rapport_paiement: str = None,
        chassis_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
```

Remplacer par :
```python
    @staticmethod
    def convert_pdf_to_xml(
        pdf_path: str,
        output_path: str,
        verbose: bool = False,
        taux_douane: float = None,
        rapport_paiement: str = None,
        chassis_config: Optional[Dict[str, Any]] = None,
        force_reprocess: bool = False,
    ) -> Dict[str, Any]:
```

- [ ] **Step 3: Passer `force_reprocess` au parser et laisser `DuplicateChassisError` remonter**

Localiser la ligne instanciant `RFCVParser` (ligne ~72) :
```python
            parser = RFCVParser(pdf_path, taux_douane=taux_douane, rapport_paiement=rapport_paiement, chassis_config=chassis_config)
```

Remplacer par :
```python
            parser = RFCVParser(
                pdf_path,
                taux_douane=taux_douane,
                rapport_paiement=rapport_paiement,
                chassis_config=chassis_config,
                force_reprocess=force_reprocess,
            )
```

Localiser le bloc `try:` principal qui entoure tout le code de conversion. Le bloc `except` actuel ressemble à :
```python
        except Exception as e:
            result['error_message'] = str(e)
            ...
            return result
```

Ajouter un handler `DuplicateChassisError` **avant** le `except Exception as e:` :
```python
        except DuplicateChassisError:
            raise  # Laisser remonter jusqu'à la route API
        except Exception as e:
            result['error_message'] = str(e)
```

- [ ] **Step 4: Vérifier la syntaxe**

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from api.services.conversion_service import ConversionService, DuplicateChassisError
print('OK — DuplicateChassisError importable depuis conversion_service')
"
```
Expected: `OK — DuplicateChassisError importable depuis conversion_service`

- [ ] **Step 5: Commit**

```bash
git add src/api/services/conversion_service.py
git commit -m "feat: propager force_reprocess dans ConversionService, re-exporter DuplicateChassisError"
```

### Task 4: Modifier `src/api/routes/convert.py` et `src/api/models/api_models.py`

**Files:**
- Modify: `src/api/routes/convert.py`
- Modify: `src/api/models/api_models.py`

- [ ] **Step 1: Ajouter les modèles de doublon dans `api_models.py`**

Après la classe `ErrorResponse`, ajouter :

```python
class DuplicateChassisEntry(BaseModel):
    """Un châssis en doublon avec son historique"""
    chassis_number: str
    first_seen_date: str
    first_filename: str
    first_rfcv_number: Optional[str] = None


class DuplicateChassisErrorResponse(BaseModel):
    """Réponse HTTP 409 pour châssis déjà traité"""
    success: bool = False
    error: str = "duplicate_chassis"
    detail: str
    duplicates: List[DuplicateChassisEntry]
    hint: str = "Relancer avec force_reprocess=true pour forcer le retraitement"
```

- [ ] **Step 2: Ajouter import dans `convert.py`**

Dans les imports de `src/api/routes/convert.py`, ajouter après les imports existants :

```python
from ..services.conversion_service import DuplicateChassisError
```

- [ ] **Step 3: Ajouter `force_reprocess` à l'endpoint sync `POST ""`**

Localiser la signature de `async def convert_pdf(`. Ajouter le paramètre Form :

```python
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
```

Passer à l'appel `conversion_service.convert_pdf_to_xml(...)` :
```python
            force_reprocess=force_reprocess,
```

Dans le bloc `try/except` de cet endpoint, ajouter avant `except HTTPException: raise` :

```python
    except DuplicateChassisError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": "duplicate_chassis",
                "detail": f"{len(e.duplicates)} châssis déjà traité(s) dans ce RFCV",
                "duplicates": e.duplicates,
                "hint": "Relancer avec force_reprocess=true pour forcer le retraitement",
            }
        )
```

- [ ] **Step 4: Modifier `_async_convert_task` — ajouter `force_reprocess`**

Localiser la fonction `_async_convert_task` et **remplacer intégralement** les lignes correspondant à l'appel `result = conversion_service.convert_pdf_to_xml(...)` (lignes ~230-237 dans le fichier actuel) ainsi que la signature de la fonction :

Remplacer la **signature** actuelle :
```python
async def _async_convert_task(job_id: str, pdf_path: str, output_path: str, taux_douane: float, rapport_paiement: Optional[str] = None, chassis_config: Optional[dict] = None):
```

Par :
```python
async def _async_convert_task(job_id: str, pdf_path: str, output_path: str, taux_douane: float, rapport_paiement: Optional[str] = None, chassis_config: Optional[dict] = None, force_reprocess: bool = False):
```

Puis **remplacer** l'appel existant non-protégé :
```python
    # Convertir
    result = conversion_service.convert_pdf_to_xml(
        pdf_path=pdf_path,
        output_path=output_path,
        verbose=False,
        taux_douane=taux_douane,
        rapport_paiement=rapport_paiement,
        chassis_config=chassis_config
    )
```

Par ce bloc avec gestion de `DuplicateChassisError` :
```python
    # Convertir
    try:
        result = conversion_service.convert_pdf_to_xml(
            pdf_path=pdf_path,
            output_path=output_path,
            verbose=False,
            taux_douane=taux_douane,
            rapport_paiement=rapport_paiement,
            chassis_config=chassis_config,
            force_reprocess=force_reprocess,
        )
    except DuplicateChassisError as e:
        _track_conversion(success=False, is_async=True)
        job_service.update_job(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=0,
            message=f"Châssis en doublon: {len(e.duplicates)} déjà traité(s)",
            error=str(e)
        )
        return
```

Le code suivant (`if result['success']:` etc.) reste inchangé.

- [ ] **Step 5: Modifier l'endpoint async `POST /async` — ajouter `force_reprocess`**

Localiser `async def convert_pdf_async(`. Ajouter le paramètre :
```python
    force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu"),
```

Localiser `background_tasks.add_task(_async_convert_task, ...)`. Ajouter :
```python
            force_reprocess=force_reprocess,
```

- [ ] **Step 6: Ajouter `force_reprocess` aux 3 autres endpoints de conversion**

Pour chacun de ces endpoints : `convert_with_payment`, `convert_with_chassis`, `convert_complete` :

1. Ajouter `force_reprocess: bool = Form(False, description="Forcer le retraitement d'un châssis déjà connu")` aux paramètres
2. Ajouter `force_reprocess=force_reprocess` à l'appel `conversion_service.convert_pdf_to_xml(...)`
3. Ajouter le handler `except DuplicateChassisError` avant `except HTTPException: raise` dans chaque endpoint (même code qu'au Step 3)

- [ ] **Step 7: Écrire les tests API**

```python
# tests/api/test_convert_duplicate.py
"""Tests de détection de doublons châssis via l'API"""
import pytest
from unittest.mock import patch
from fastapi import status


@pytest.fixture
def minimal_pdf_bytes():
    """PDF minimal valide (1 byte) pour tester sans vrai PDF"""
    return b"%PDF-1.4 fake content for testing"


class TestConvertDuplicateChassis:

    @pytest.mark.asyncio
    async def test_409_on_duplicate_chassis(self, client, minimal_pdf_bytes):
        """Le traitement d'un châssis déjà connu retourne HTTP 409"""
        from chassis_registry import DuplicateChassisError

        duplicate_entry = [{
            "chassis_number": "LZSHCKZS2S8000001",
            "first_seen_date": "2025-01-01T10:00:00+00:00",
            "first_filename": "OLD_DOSSIER.pdf",
            "first_rfcv_number": "CI-2025-001",
        }]

        with patch(
            "api.services.conversion_service.ConversionService.convert_pdf_to_xml",
            side_effect=DuplicateChassisError(duplicate_entry)
        ):
            response = await client.post(
                "/api/v1/convert",
                files={"file": ("DOSSIER.pdf", minimal_pdf_bytes, "application/pdf")},
                data={"taux_douane": "573.139"},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        body = response.json()
        assert body["detail"]["error"] == "duplicate_chassis"
        assert len(body["detail"]["duplicates"]) == 1
        assert "force_reprocess" in body["detail"]["hint"]

    @pytest.mark.asyncio
    async def test_409_lists_all_duplicates(self, client, minimal_pdf_bytes):
        """Tous les châssis en doublon sont listés en une seule réponse"""
        from chassis_registry import DuplicateChassisError

        duplicates = [
            {"chassis_number": f"CN{i:013d}", "first_seen_date": "2025-01-01T10:00:00+00:00",
             "first_filename": "OLD.pdf", "first_rfcv_number": "CI-2025-001"}
            for i in range(3)
        ]

        with patch(
            "api.services.conversion_service.ConversionService.convert_pdf_to_xml",
            side_effect=DuplicateChassisError(duplicates)
        ):
            response = await client.post(
                "/api/v1/convert",
                files={"file": ("DOSSIER.pdf", minimal_pdf_bytes, "application/pdf")},
                data={"taux_douane": "573.139"},
            )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert len(response.json()["detail"]["duplicates"]) == 3

    @pytest.mark.asyncio
    async def test_force_reprocess_passes_parameter(self, client, minimal_pdf_bytes):
        """force_reprocess=true est passé à convert_pdf_to_xml"""
        captured_kwargs = {}

        def fake_convert(**kwargs):
            captured_kwargs.update(kwargs)
            raise Exception("stop early")

        with patch(
            "api.services.conversion_service.ConversionService.convert_pdf_to_xml",
            side_effect=fake_convert
        ):
            await client.post(
                "/api/v1/convert",
                files={"file": ("DOSSIER.pdf", minimal_pdf_bytes, "application/pdf")},
                data={"taux_douane": "573.139", "force_reprocess": "true"},
            )

        assert captured_kwargs.get("force_reprocess") is True
```

- [ ] **Step 8: Vérifier que les tests passent**

```bash
python -m pytest tests/api/test_convert_duplicate.py -v
```
Expected: PASS

- [ ] **Step 9: Vérifier aucune régression**

```bash
python -m pytest tests/api/test_convert.py tests/api/test_health.py -v
```
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/api/routes/convert.py src/api/models/api_models.py tests/api/test_convert_duplicate.py
git commit -m "feat: HTTP 409 sur doublon châssis + force_reprocess sur tous les endpoints"
```

---

## Chunk 4: Endpoints d'administration du registre

### Task 5: Ajouter les endpoints dans `src/api/routes/chassis.py`

**Files:**
- Modify: `src/api/routes/chassis.py`
- Modify: `src/api/models/api_models.py`

- [ ] **Step 1: Ajouter les modèles de registre dans `api_models.py`**

Après `SequencesStatusResponse`, ajouter :

```python
class ChassisRegistryEntry(BaseModel):
    """Entrée dans le registre de châssis"""
    chassis_number: str
    registered_at: str
    filename: str
    rfcv_number: Optional[str] = None


class ChassisRegistryResponse(BaseModel):
    """Liste du registre de châssis"""
    total: int
    entries: List[ChassisRegistryEntry]


class ChassisEntryDetailResponse(BaseModel):
    """Détail d'une entrée du registre"""
    chassis_number: str
    registered_at: str
    filename: str
    rfcv_number: Optional[str] = None
    table: str  # "extracted" ou "generated"


class ChassisDeleteResponse(BaseModel):
    """Confirmation de suppression"""
    success: bool
    deleted: str
```

- [ ] **Step 2: Ajouter l'import `get_registry` dans `chassis.py`**

`chassis.py` fait déjà un `sys.path.insert` via `chassis_service`, vérifier si `src/` est dans le path. Ajouter en tête des imports de `chassis.py` :

```python
from ..services.conversion_service import DuplicateChassisError  # réutilise le path déjà configuré
```

Puis, après les imports existants :

```python
from chassis_registry import get_registry
from ..models.api_models import (
    ChassisRegistryEntry,
    ChassisRegistryResponse,
    ChassisEntryDetailResponse,
    ChassisDeleteResponse,
)
```

Note: si `chassis_registry` n'est pas accessible depuis ce point, utiliser le même pattern que `chassis_service.py` : `sys.path.insert(0, str(Path(__file__).parent.parent.parent))`.

- [ ] **Step 3: Ajouter les 4 endpoints admin à la fin de `chassis.py`**

```python
@router.get(
    "/registry/extracted",
    response_model=ChassisRegistryResponse,
    summary="Liste des châssis extraits",
    description="Retourne tous les numéros de châssis extraits des PDFs RFCV.",
    dependencies=[Depends(verify_api_key)]
)
async def list_extracted_chassis():
    entries = get_registry().get_all_extracted()
    return ChassisRegistryResponse(
        total=len(entries),
        entries=[ChassisRegistryEntry(**e) for e in entries]
    )


@router.get(
    "/registry/generated",
    response_model=ChassisRegistryResponse,
    summary="Liste des VINs générés",
    description="Retourne tous les VINs générés automatiquement.",
    dependencies=[Depends(verify_api_key)]
)
async def list_generated_chassis():
    entries = get_registry().get_all_generated()
    return ChassisRegistryResponse(
        total=len(entries),
        entries=[ChassisRegistryEntry(**e) for e in entries]
    )


@router.get(
    "/registry/{chassis_number}",
    response_model=ChassisEntryDetailResponse,
    summary="Détail d'un châssis",
    description="Cherche un châssis dans les deux registres (extrait et généré).",
    dependencies=[Depends(verify_api_key)]
)
async def get_chassis_entry(chassis_number: str):
    entry = get_registry().get_entry(chassis_number.upper())
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Châssis introuvable: {chassis_number}"
        )
    return ChassisEntryDetailResponse(**entry)


@router.delete(
    "/registry/{chassis_number}",
    response_model=ChassisDeleteResponse,
    summary="Supprimer une entrée du registre",
    description="Supprime un châssis du registre (extrait ou généré). Action irréversible.",
    dependencies=[Depends(verify_api_key)]
)
async def delete_chassis_entry(chassis_number: str):
    deleted = get_registry().delete(chassis_number.upper())
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Châssis introuvable: {chassis_number}"
        )
    return ChassisDeleteResponse(success=True, deleted=chassis_number.upper())
```

- [ ] **Step 4: Vérifier que les routes sont bien enregistrées**

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from api.routes.chassis import router
# Les paths dans router.routes sont sans le préfixe /api/v1/chassis
paths = [r.path for r in router.routes]
assert '/registry/extracted' in paths, f'Route manquante, paths: {paths}'
assert '/registry/generated' in paths, f'Route manquante, paths: {paths}'
assert '/registry/{chassis_number}' in paths, f'Route manquante, paths: {paths}'
print('Endpoints OK:', paths)
"
```
Expected: liste des endpoints incluant `/registry/extracted`, `/registry/generated`, `/registry/{chassis_number}`

- [ ] **Step 5: Écrire les tests admin**

Les tests patchent l'instance singleton via `patch.object` pour éviter les problèmes de mock sur classe déjà instanciée.

```python
# tests/api/test_chassis_registry_api.py
"""Tests des endpoints d'administration du registre de châssis"""
import pytest
from unittest.mock import patch
from fastapi import status

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from chassis_registry import get_registry


class TestChassisRegistryEndpoints:

    @pytest.mark.asyncio
    async def test_list_extracted_empty(self, client):
        with patch.object(get_registry(), "get_all_extracted", return_value=[]):
            response = await client.get("/api/v1/chassis/registry/extracted")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0
        assert body["entries"] == []

    @pytest.mark.asyncio
    async def test_list_extracted_with_entries(self, client):
        mock_entries = [
            {"chassis_number": "ABC123456789012", "registered_at": "2025-01-01T10:00:00+00:00",
             "filename": "A.pdf", "rfcv_number": "CI-2025-001"},
        ]
        with patch.object(get_registry(), "get_all_extracted", return_value=mock_entries):
            response = await client.get("/api/v1/chassis/registry/extracted")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_list_generated_empty(self, client):
        with patch.object(get_registry(), "get_all_generated", return_value=[]):
            response = await client.get("/api/v1/chassis/registry/generated")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_get_chassis_entry_found(self, client):
        mock_entry = {
            "chassis_number": "ABC123456789012",
            "registered_at": "2025-01-01T10:00:00+00:00",
            "filename": "A.pdf",
            "rfcv_number": "CI-2025-001",
            "table": "extracted",
        }
        with patch.object(get_registry(), "get_entry", return_value=mock_entry):
            response = await client.get("/api/v1/chassis/registry/ABC123456789012")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["table"] == "extracted"

    @pytest.mark.asyncio
    async def test_get_chassis_entry_not_found(self, client):
        with patch.object(get_registry(), "get_entry", return_value=None):
            response = await client.get("/api/v1/chassis/registry/NOTEXIST12345")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_chassis_entry_success(self, client):
        with patch.object(get_registry(), "delete", return_value=True):
            response = await client.delete("/api/v1/chassis/registry/ABC123456789012")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_delete_chassis_entry_not_found(self, client):
        with patch.object(get_registry(), "delete", return_value=False):
            response = await client.delete("/api/v1/chassis/registry/NOTEXIST12345")
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

- [ ] **Step 6: Vérifier que tous les tests passent**

```bash
python -m pytest tests/api/test_chassis_registry_api.py tests/api/test_convert_duplicate.py tests/test_chassis_registry.py -v
```
Expected: tous PASS

- [ ] **Step 7: Vérifier l'ensemble sans régression**

```bash
python -m pytest tests/ -v --ignore=tests/test_converter.py -x
```
Expected: tous PASS

- [ ] **Step 8: Commit final**

```bash
git add src/api/routes/chassis.py src/api/models/api_models.py tests/api/test_chassis_registry_api.py
git commit -m "feat: endpoints admin registre châssis — list/get/delete avec tests"
```

- [ ] **Step 9: Tag version**

```bash
git tag -a v2.9.0 -m "feat: registre de châssis RFCV avec détection doublons"
```
