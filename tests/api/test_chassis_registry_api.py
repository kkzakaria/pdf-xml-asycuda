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
