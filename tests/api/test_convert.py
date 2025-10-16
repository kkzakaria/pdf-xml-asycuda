"""
Tests des endpoints de conversion
"""
import pytest
import asyncio
from pathlib import Path


@pytest.mark.asyncio
async def test_convert_sync_success(client, sample_pdf):
    """Test de conversion synchrone réussie"""
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = await client.post("/api/v1/convert", files=files)

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "job_id" in data
    assert data["filename"] == sample_pdf.name
    assert "output_file" in data
    assert data["output_file"].endswith(".xml")
    assert "processing_time" in data
    assert data["processing_time"] > 0

    # Vérifier les métriques
    if data.get("metrics"):
        metrics = data["metrics"]
        assert "items_count" in metrics
        assert "fill_rate" in metrics
        assert "xml_valid" in metrics


@pytest.mark.asyncio
async def test_convert_sync_no_file(client):
    """Test de conversion sans fichier"""
    response = await client.post("/api/v1/convert")

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_convert_sync_invalid_file(client):
    """Test de conversion avec fichier invalide"""
    files = {"file": ("test.txt", b"not a pdf", "text/plain")}
    response = await client.post("/api/v1/convert", files=files)

    # Devrait échouer car pas un PDF
    assert response.status_code in [400, 422, 500]


@pytest.mark.asyncio
async def test_convert_async_success(client, sample_pdf):
    """Test de conversion asynchrone"""
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = await client.post("/api/v1/convert/async", files=files)

    assert response.status_code == 200
    data = response.json()

    assert "job_id" in data
    assert data["status"] == "pending"
    assert "created_at" in data
    assert "message" in data

    job_id = data["job_id"]

    # Attendre un peu que le job se termine
    await asyncio.sleep(2)

    # Vérifier le status
    status_response = await client.get(f"/api/v1/convert/{job_id}")
    assert status_response.status_code == 200
    status_data = status_response.json()

    assert status_data["job_id"] == job_id
    assert status_data["status"] in ["pending", "processing", "completed"]


@pytest.mark.asyncio
async def test_get_job_status_not_found(client):
    """Test récupération status job inexistant"""
    response = await client.get("/api/v1/convert/nonexistent_job_id")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_get_job_result_success(client, sample_pdf):
    """Test récupération résultat job"""
    # D'abord créer un job async
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = await client.post("/api/v1/convert/async", files=files)

    job_id = response.json()["job_id"]

    # Attendre que le job se termine
    await asyncio.sleep(3)

    # Récupérer le résultat
    result_response = await client.get(f"/api/v1/convert/{job_id}/result")

    # Le job peut ne pas être terminé encore
    if result_response.status_code == 200:
        data = result_response.json()
        assert "job_id" in data
        assert "result" in data
    elif result_response.status_code == 400:
        # Job pas encore terminé, c'est OK
        pass
    else:
        pytest.fail(f"Unexpected status code: {result_response.status_code}")


@pytest.mark.asyncio
async def test_download_xml_success(client, sample_pdf):
    """Test téléchargement XML généré"""
    # D'abord faire une conversion synchrone
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = await client.post("/api/v1/convert", files=files)

    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Télécharger le XML
    download_response = await client.get(f"/api/v1/convert/{job_id}/download")

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/xml"

    # Vérifier que c'est du XML valide
    content = download_response.content
    assert content.startswith(b"<?xml") or content.startswith(b"<ASYCUDA")


@pytest.mark.asyncio
async def test_download_xml_not_found(client):
    """Test téléchargement XML inexistant"""
    response = await client.get("/api/v1/convert/nonexistent_job/download")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_concurrent_conversions(client, sample_pdf):
    """Test conversions concurrentes"""
    tasks = []

    for _ in range(3):
        async def convert():
            with open(sample_pdf, "rb") as f:
                files = {"file": (sample_pdf.name, f, "application/pdf")}
                return await client.post("/api/v1/convert/async", files=files)

        tasks.append(convert())

    responses = await asyncio.gather(*tasks)

    # Toutes les conversions doivent réussir
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data

    # Les job_ids doivent être uniques
    job_ids = [r.json()["job_id"] for r in responses]
    assert len(job_ids) == len(set(job_ids))
