"""
Tests pour les endpoints spécifiques de l'API
Tests pour /convert/with-payment, /convert/with-chassis, /convert/complete
"""
import pytest
import sys
import secrets
from pathlib import Path
from fastapi.testclient import TestClient

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.main import app
from api.core.config import settings
from api.core.rate_limit import limiter

# Configuration pour les tests
TEST_API_KEY = secrets.token_urlsafe(32)
settings.keys = TEST_API_KEY
settings.require_authentication = True
limiter.enabled = False  # Désactiver rate limiting pour les tests

client = TestClient(app)

# Test file path
TEST_PDF_PATH = Path(__file__).parent.parent / "DOSSIER 18236.pdf"


class TestConvertWithPayment:
    """Tests pour l'endpoint /convert/with-payment"""

    def test_endpoint_requires_api_key(self):
        """L'endpoint nécessite une clé API"""
        response = client.post("/api/v1/convert/with-payment")
        assert response.status_code == 401
        assert "API key" in response.json()["detail"]

    def test_endpoint_requires_file(self):
        """L'endpoint nécessite un fichier"""
        response = client.post(
            "/api/v1/convert/with-payment",
            headers={"X-API-Key": TEST_API_KEY},
            data={"taux_douane": 573.139, "rapport_paiement": "25P2003J"}
        )
        assert response.status_code == 422  # Validation error

    def test_endpoint_requires_taux_douane(self):
        """L'endpoint nécessite le taux douanier"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-payment",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"rapport_paiement": "25P2003J"}
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_requires_rapport_paiement(self):
        """L'endpoint nécessite le rapport de paiement"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-payment",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"taux_douane": 573.139}
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_validates_taux_douane_positive(self):
        """Le taux douanier doit être positif"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-payment",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"taux_douane": -100, "rapport_paiement": "25P2003J"}
            )
        assert response.status_code == 422  # Validation error

    def test_successful_conversion_with_payment(self):
        """Conversion réussie avec rapport de paiement"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-payment",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "rapport_paiement": "25P2003J"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"]
        assert data["filename"] == "DOSSIER 18236.pdf"
        assert data["output_file"]
        assert "rapport de paiement" in data["message"]
        assert data["metrics"] is not None
        assert data["processing_time"] > 0


class TestConvertWithChassis:
    """Tests pour l'endpoint /convert/with-chassis"""

    def test_endpoint_requires_api_key(self):
        """L'endpoint nécessite une clé API"""
        response = client.post("/api/v1/convert/with-chassis")
        assert response.status_code == 401

    def test_endpoint_requires_quantity(self):
        """L'endpoint nécessite la quantité de châssis"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "wmi": "LZS",
                    "year": 2025
                }
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_requires_wmi(self):
        """L'endpoint nécessite le code WMI"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 10,
                    "year": 2025
                }
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_requires_year(self):
        """L'endpoint nécessite l'année"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 10,
                    "wmi": "LZS"
                }
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_validates_wmi_length(self):
        """Le code WMI doit faire 3 caractères"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 10,
                    "wmi": "AB",  # Trop court
                    "year": 2025
                }
            )
        assert response.status_code == 422  # Validation error

    def test_endpoint_validates_year_range(self):
        """L'année doit être dans la plage valide"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 10,
                    "wmi": "LZS",
                    "year": 1900  # Trop ancien
                }
            )
        assert response.status_code == 422  # Validation error

    def test_successful_conversion_with_chassis(self):
        """Conversion réussie avec génération de châssis"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 5,
                    "wmi": "LZS",
                    "year": 2025
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"]
        assert "5 châssis VIN" in data["message"]
        assert data["metrics"] is not None

    def test_conversion_with_custom_vds_and_plant(self):
        """Conversion avec VDS et plant_code personnalisés"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/with-chassis",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 3,
                    "wmi": "LFV",
                    "year": 2024,
                    "vds": "BA01A",
                    "plant_code": "P"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "3 châssis VIN" in data["message"]


class TestConvertComplete:
    """Tests pour l'endpoint /convert/complete"""

    def test_endpoint_requires_all_parameters(self):
        """L'endpoint nécessite tous les paramètres"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            # Manque rapport_paiement
            response = client.post(
                "/api/v1/convert/complete",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("test.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "quantity": 10,
                    "wmi": "LZS",
                    "year": 2025
                }
            )
        assert response.status_code == 422  # Validation error

    def test_successful_complete_conversion(self):
        """Conversion complète réussie"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/complete",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "rapport_paiement": "25P2003J",
                    "quantity": 5,
                    "wmi": "LZS",
                    "year": 2025
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["job_id"]
        assert "25P2003J" in data["message"]
        assert "5 châssis VIN" in data["message"]
        assert data["metrics"] is not None
        assert data["processing_time"] > 0

    def test_complete_conversion_with_all_params(self):
        """Conversion complète avec tous les paramètres optionnels"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert/complete",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={
                    "taux_douane": 573.139,
                    "rapport_paiement": "25P2003J",
                    "quantity": 3,
                    "wmi": "LFV",
                    "year": 2024,
                    "vds": "BA01A",
                    "plant_code": "P"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "25P2003J" in data["message"]
        assert "3 châssis VIN" in data["message"]


class TestEndpointsComparison:
    """Tests de comparaison entre les endpoints"""

    def test_all_endpoints_accessible(self):
        """Tous les endpoints spécialisés sont accessibles"""
        endpoints = [
            "/api/v1/convert/with-payment",
            "/api/v1/convert/with-chassis",
            "/api/v1/convert/complete"
        ]

        for endpoint in endpoints:
            response = client.post(endpoint)
            # 401 (API key manquante) confirme que l'endpoint existe
            assert response.status_code == 401, f"Endpoint {endpoint} non accessible"

    def test_generic_endpoint_still_works(self):
        """L'endpoint générique /convert fonctionne toujours"""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test PDF not found: {TEST_PDF_PATH}")

        with open(TEST_PDF_PATH, "rb") as f:
            response = client.post(
                "/api/v1/convert",
                headers={"X-API-Key": TEST_API_KEY},
                files={"file": ("DOSSIER 18236.pdf", f, "application/pdf")},
                data={"taux_douane": 573.139}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
