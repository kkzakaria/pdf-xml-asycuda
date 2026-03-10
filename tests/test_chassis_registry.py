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
