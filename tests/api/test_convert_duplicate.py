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
