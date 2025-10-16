"""
Fixtures pytest pour les tests API
"""
import pytest
import pytest_asyncio
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport
import asyncio

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.main import app
from api.core.config import settings


@pytest_asyncio.fixture
async def client():
    """
    Client HTTP async pour tester l'API
    """
    # Override settings pour les tests
    settings.upload_dir = "test_uploads"
    settings.output_dir = "test_output"

    # Créer les dossiers de test
    Path(settings.upload_dir).mkdir(exist_ok=True)
    Path(settings.output_dir).mkdir(exist_ok=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup après les tests
    import shutil
    try:
        shutil.rmtree("test_uploads", ignore_errors=True)
        shutil.rmtree("test_output", ignore_errors=True)
    except:
        pass


@pytest.fixture
def sample_pdf():
    """
    Retourne le chemin vers un PDF de test
    """
    # Chercher n'importe quel PDF dans tests/
    tests_dir = Path(__file__).parent.parent
    pdf_files = list(tests_dir.glob("*.pdf"))

    if not pdf_files:
        pytest.skip("Pas de PDF de test disponible")

    return pdf_files[0]


@pytest.fixture
def multiple_pdfs():
    """
    Retourne une liste de PDFs de test pour batch
    """
    tests_dir = Path(__file__).parent.parent
    pdf_files = list(tests_dir.glob("*.pdf"))

    if len(pdf_files) < 2:
        pytest.skip("Pas assez de PDFs pour tester le batch")

    return pdf_files[:3]  # Max 3 fichiers pour tests rapides
