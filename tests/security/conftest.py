"""
Configuration pytest pour les tests de sécurité
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import secrets

# Ajouter le chemin src au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.main import app
from api.core.config import settings


@pytest.fixture
def client():
    """
    Fixture pour le client de test FastAPI

    Configure un environnement de test avec authentification désactivée
    pour faciliter les tests
    """
    # Sauvegarder la configuration originale
    original_auth = settings.require_authentication
    original_keys = settings.keys

    # Générer une clé de test
    test_key = secrets.token_urlsafe(32)
    settings.keys = test_key
    settings.require_authentication = True

    # Créer le client de test
    with TestClient(app) as test_client:
        yield test_client

    # Restaurer la configuration
    settings.require_authentication = original_auth
    settings.keys = original_keys


@pytest.fixture
def test_api_key():
    """Fixture pour obtenir une clé API de test"""
    return secrets.token_urlsafe(32)


@pytest.fixture
def authenticated_client(client, test_api_key):
    """Fixture pour un client authentifié"""
    # Configurer la clé API
    from api.core.config import settings
    original_keys = settings.keys
    settings.keys = test_api_key

    yield client, test_api_key

    # Restaurer
    settings.keys = original_keys
