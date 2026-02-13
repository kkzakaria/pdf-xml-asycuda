"""
Tests pour le service de statistiques d'utilisation
"""
import json
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.services.usage_stats_service import UsageStatsService


@pytest.fixture
def stats_file(tmp_path):
    """Fichier de stats temporaire"""
    return str(tmp_path / "test_usage_stats.json")


@pytest.fixture
def stats_service(stats_file):
    """Instance de UsageStatsService pour les tests"""
    return UsageStatsService(stats_file)


class TestInitialization:
    def test_initialization(self, stats_file):
        """Crée le fichier JSON avec structure vide"""
        service = UsageStatsService(stats_file)
        assert Path(stats_file).exists()

        with open(stats_file, 'r') as f:
            data = json.load(f)

        assert "initialized_at" in data
        assert "last_updated" in data
        assert data["conversions"]["total"] == 0
        assert data["batches"]["total"] == 0
        assert data["chassis"]["generation_requests"] == 0
        assert data["requests"]["total"] == 0

    def test_creates_parent_directory(self, tmp_path):
        """Crée le répertoire parent si nécessaire"""
        path = str(tmp_path / "subdir" / "stats.json")
        service = UsageStatsService(path)
        assert Path(path).exists()


class TestTrackConversion:
    def test_track_conversion_success(self, stats_service):
        """Incrémente total + successful + sync"""
        stats_service.track_conversion(success=True, is_async=False)

        stats = stats_service.get_conversion_stats()
        assert stats["total"] == 1
        assert stats["successful"] == 1
        assert stats["failed"] == 0
        assert stats["sync"] == 1
        assert stats["async"] == 0

    def test_track_conversion_failure(self, stats_service):
        """Incrémente total + failed"""
        stats_service.track_conversion(success=False, is_async=False)

        stats = stats_service.get_conversion_stats()
        assert stats["total"] == 1
        assert stats["successful"] == 0
        assert stats["failed"] == 1

    def test_track_conversion_async(self, stats_service):
        """Incrémente async au lieu de sync"""
        stats_service.track_conversion(success=True, is_async=True)

        stats = stats_service.get_conversion_stats()
        assert stats["sync"] == 0
        assert stats["async"] == 1

    def test_track_conversion_with_flags(self, stats_service):
        """Vérifie with_chassis, with_payment"""
        stats_service.track_conversion(
            success=True, is_async=False,
            has_chassis=True, has_payment=True
        )

        stats = stats_service.get_conversion_stats()
        assert stats["with_chassis"] == 1
        assert stats["with_payment"] == 1

    def test_track_conversion_multiple(self, stats_service):
        """Compteurs cumulatifs"""
        stats_service.track_conversion(success=True, is_async=False)
        stats_service.track_conversion(success=True, is_async=True)
        stats_service.track_conversion(success=False, is_async=False)

        stats = stats_service.get_conversion_stats()
        assert stats["total"] == 3
        assert stats["successful"] == 2
        assert stats["failed"] == 1
        assert stats["sync"] == 2
        assert stats["async"] == 1


class TestTrackBatch:
    def test_track_batch(self, stats_service):
        """Incrémente batches + files_processed"""
        stats_service.track_batch(successful=3, failed=0, files_processed=3)

        stats = stats_service.get_stats()
        assert stats["batches"]["total"] == 1
        assert stats["batches"]["successful"] == 1
        assert stats["batches"]["failed"] == 0
        assert stats["batches"]["total_files_processed"] == 3

    def test_track_batch_with_failures(self, stats_service):
        """Batch avec échecs comptabilisé comme failed"""
        stats_service.track_batch(successful=2, failed=1, files_processed=3)

        stats = stats_service.get_stats()
        assert stats["batches"]["total"] == 1
        assert stats["batches"]["successful"] == 0
        assert stats["batches"]["failed"] == 1


class TestTrackChassis:
    def test_track_chassis(self, stats_service):
        """Incrémente generation_requests + total_vins"""
        stats_service.track_chassis_generation(vins_count=180)

        stats = stats_service.get_stats()
        assert stats["chassis"]["generation_requests"] == 1
        assert stats["chassis"]["total_vins_generated"] == 180

    def test_track_chassis_multiple(self, stats_service):
        """Compteurs cumulatifs pour VINs"""
        stats_service.track_chassis_generation(vins_count=100)
        stats_service.track_chassis_generation(vins_count=50)

        stats = stats_service.get_stats()
        assert stats["chassis"]["generation_requests"] == 2
        assert stats["chassis"]["total_vins_generated"] == 150


class TestTrackRequest:
    def test_track_request(self, stats_service):
        """Incrémente by_method + by_status"""
        stats_service.track_request("GET", 200)

        stats = stats_service.get_request_stats()
        assert stats["total"] == 1
        assert stats["by_method"]["GET"] == 1
        assert stats["by_status"]["200"] == 1

    def test_track_request_multiple_methods(self, stats_service):
        """Répartition par méthode"""
        stats_service.track_request("GET", 200)
        stats_service.track_request("POST", 201)
        stats_service.track_request("GET", 200)

        stats = stats_service.get_request_stats()
        assert stats["total"] == 3
        assert stats["by_method"]["GET"] == 2
        assert stats["by_method"]["POST"] == 1

    def test_track_request_multiple_statuses(self, stats_service):
        """Répartition par status"""
        stats_service.track_request("GET", 200)
        stats_service.track_request("GET", 404)
        stats_service.track_request("POST", 500)

        stats = stats_service.get_request_stats()
        assert stats["by_status"]["200"] == 1
        assert stats["by_status"]["404"] == 1
        assert stats["by_status"]["500"] == 1


class TestPersistence:
    def test_persistence(self, stats_file):
        """Reload après save conserve les données"""
        # Premier service: ajouter des données
        service1 = UsageStatsService(stats_file)
        service1.track_conversion(success=True, is_async=False)
        service1.track_batch(successful=2, failed=1, files_processed=3)
        service1.track_chassis_generation(vins_count=50)
        service1.track_request("POST", 200)

        # Deuxième service: recharger depuis le fichier
        service2 = UsageStatsService(stats_file)
        stats = service2.get_stats()

        assert stats["conversions"]["total"] == 1
        assert stats["conversions"]["successful"] == 1
        assert stats["batches"]["total"] == 1
        assert stats["batches"]["total_files_processed"] == 3
        assert stats["chassis"]["total_vins_generated"] == 50
        assert stats["requests"]["total"] == 1

    def test_corrupted_file_recovery(self, stats_file):
        """Récupère d'un fichier corrompu"""
        # Écrire un JSON invalide
        Path(stats_file).parent.mkdir(parents=True, exist_ok=True)
        with open(stats_file, 'w') as f:
            f.write("invalid json{{{")

        # Le service doit s'initialiser avec des valeurs par défaut
        service = UsageStatsService(stats_file)
        stats = service.get_stats()
        assert stats["conversions"]["total"] == 0


class TestStatsEndpoints:
    """Tests d'intégration pour les endpoints stats"""

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client):
        """GET /api/v1/stats retourne les statistiques"""
        response = await client.get("/api/v1/stats")
        assert response.status_code == 200

        data = response.json()
        assert "conversions" in data
        assert "batches" in data
        assert "chassis" in data
        assert "requests" in data

    @pytest.mark.asyncio
    async def test_stats_conversions_endpoint(self, client):
        """GET /api/v1/stats/conversions retourne les stats de conversion"""
        response = await client.get("/api/v1/stats/conversions")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "successful" in data
        assert "failed" in data

    @pytest.mark.asyncio
    async def test_stats_requests_endpoint(self, client):
        """GET /api/v1/stats/requests retourne les stats de requêtes"""
        response = await client.get("/api/v1/stats/requests")
        assert response.status_code == 200

        data = response.json()
        assert "total" in data
        assert "by_method" in data
        assert "by_status" in data
