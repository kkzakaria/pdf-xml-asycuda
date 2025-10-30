"""
Tests des endpoints files
"""
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_download_xml_by_id(client, sample_pdf):
    """Test téléchargement XML par file_id"""
    # D'abord créer un fichier XML via conversion
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"taux_douane": "573.139"}
        response = await client.post("/api/v1/convert", files=files, data=data)

    assert response.status_code == 200
    output_file = response.json()["output_file"]

    # Extraire le file_id (nom du fichier sans extension)
    file_id = Path(output_file).stem

    # Télécharger via endpoint files
    download_response = await client.get(f"/api/v1/files/{file_id}/xml")

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/xml"

    # Vérifier que c'est du XML
    content = download_response.content
    assert content.startswith(b"<?xml") or content.startswith(b"<ASYCUDA")


@pytest.mark.asyncio
async def test_download_xml_not_found(client):
    """Test téléchargement XML inexistant"""
    response = await client.get("/api/v1/files/nonexistent_file_id/xml")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_file_metadata(client, sample_pdf):
    """Test récupération métadonnées fichier"""
    # D'abord créer un fichier XML
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"taux_douane": "573.139"}
        response = await client.post("/api/v1/convert", files=files, data=data)

    assert response.status_code == 200
    output_file = response.json()["output_file"]
    file_id = Path(output_file).stem

    # Récupérer les métadonnées
    metadata_response = await client.get(f"/api/v1/files/{file_id}/metadata")

    assert metadata_response.status_code == 200
    data = metadata_response.json()

    assert data["file_id"] == file_id
    assert data["filename"] == output_file
    assert data["size_bytes"] > 0
    assert data["mime_type"] == "application/xml"
    assert data["is_available"] is True
    assert "created_at" in data


@pytest.mark.asyncio
async def test_file_metadata_not_found(client):
    """Test métadonnées fichier inexistant"""
    response = await client.get("/api/v1/files/nonexistent_file_id/metadata")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_with_extension(client, sample_pdf):
    """Test téléchargement avec extension .xml dans file_id"""
    # Créer un fichier XML
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"taux_douane": "573.139"}
        response = await client.post("/api/v1/convert", files=files, data=data)

    output_file = response.json()["output_file"]
    file_id = Path(output_file).stem

    # Télécharger avec .xml dans le file_id
    download_response = await client.get(f"/api/v1/files/{file_id}.xml/xml")

    assert download_response.status_code == 200
