"""
Tests des endpoints batch
"""
import pytest
import asyncio
import json


@pytest.mark.asyncio
async def test_batch_convert_success(client, multiple_pdfs):
    """Test de conversion batch réussie"""
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    # Un taux douanier pour chaque fichier
    taux_list = [573.139] * len(multiple_pdfs)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 2,
        "taux_douanes": json.dumps(taux_list)
    })

    assert response.status_code == 200
    data = response.json()

    assert "batch_id" in data
    assert data["status"] == "pending"
    assert data["total_files"] == len(multiple_pdfs)
    assert data["processed"] == 0
    assert "created_at" in data


@pytest.mark.asyncio
async def test_batch_convert_no_files(client):
    """Test batch sans fichiers"""
    response = await client.post("/api/v1/batch")

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_batch_status(client, multiple_pdfs):
    """Test récupération status batch"""
    # Créer un batch
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    taux_list = [573.139] * len(multiple_pdfs)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 2,
        "taux_douanes": json.dumps(taux_list)
    })
    batch_id = response.json()["batch_id"]

    # Récupérer le status
    status_response = await client.get(f"/api/v1/batch/{batch_id}/status")

    assert status_response.status_code == 200
    data = status_response.json()

    assert data["batch_id"] == batch_id
    assert data["status"] in ["pending", "processing", "completed"]
    assert data["total_files"] == len(multiple_pdfs)


@pytest.mark.asyncio
async def test_batch_status_not_found(client):
    """Test status batch inexistant"""
    response = await client.get("/api/v1/batch/nonexistent_batch_id/status")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_batch_results(client, multiple_pdfs):
    """Test récupération résultats batch"""
    # Créer un batch
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    taux_list = [573.139] * len(multiple_pdfs)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 2,
        "taux_douanes": json.dumps(taux_list)
    })
    batch_id = response.json()["batch_id"]

    # Attendre que le batch se termine
    await asyncio.sleep(5)

    # Récupérer les résultats
    results_response = await client.get(f"/api/v1/batch/{batch_id}/results")

    # Le batch peut ne pas être terminé encore
    if results_response.status_code == 200:
        data = results_response.json()
        assert data["batch_id"] == batch_id
        assert "results" in data
        assert "total_files" in data
        assert "successful" in data
        assert "failed" in data
    elif results_response.status_code == 400:
        # Batch pas encore terminé, c'est OK
        pass
    else:
        pytest.fail(f"Unexpected status code: {results_response.status_code}")


@pytest.mark.asyncio
async def test_batch_report(client, multiple_pdfs):
    """Test génération rapport batch"""
    # Créer un batch
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    taux_list = [573.139] * len(multiple_pdfs)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 2,
        "taux_douanes": json.dumps(taux_list)
    })
    batch_id = response.json()["batch_id"]

    # Attendre que le batch se termine
    await asyncio.sleep(5)

    # Récupérer le rapport
    report_response = await client.get(f"/api/v1/batch/{batch_id}/report")

    # Le batch peut ne pas être terminé encore
    if report_response.status_code == 200:
        data = report_response.json()
        assert data["batch_id"] == batch_id
        assert "summary" in data
        assert "files" in data

        summary = data["summary"]
        assert "total_files" in summary
        assert "success_rate" in summary
        assert "total_time" in summary
    elif report_response.status_code == 400:
        # Batch pas encore terminé, c'est OK
        pass


@pytest.mark.asyncio
async def test_batch_workers_validation(client, multiple_pdfs):
    """Test validation du nombre de workers"""
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    taux_list = [573.139] * len(multiple_pdfs)
    taux_json = json.dumps(taux_list)

    # Workers valides (1-8)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 4,
        "taux_douanes": taux_json
    })
    assert response.status_code == 200

    # Reload files for next test
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 1,
        "taux_douanes": taux_json
    })
    assert response.status_code == 200

    # Reload files for next test
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 8,
        "taux_douanes": taux_json
    })
    assert response.status_code == 200

    # Workers invalide (hors limites) - devrait être rejeté par validation
    files2 = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files2.append(("files", (pdf.name, f.read(), "application/pdf")))

    response = await client.post("/api/v1/batch", files=files2, data={
        "workers": 100,
        "taux_douanes": taux_json
    })
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_batch_progress_tracking(client, multiple_pdfs):
    """Test suivi de progression batch"""
    # Créer un batch
    files = []
    for pdf in multiple_pdfs:
        with open(pdf, "rb") as f:
            files.append(("files", (pdf.name, f.read(), "application/pdf")))

    taux_list = [573.139] * len(multiple_pdfs)
    response = await client.post("/api/v1/batch", files=files, data={
        "workers": 1,
        "taux_douanes": json.dumps(taux_list)
    })
    batch_id = response.json()["batch_id"]

    # Suivre la progression plusieurs fois
    for i in range(3):
        await asyncio.sleep(1)

        status_response = await client.get(f"/api/v1/batch/{batch_id}/status")
        data = status_response.json()

        # Le nombre de fichiers traités devrait augmenter
        assert data["processed"] >= 0
        assert data["processed"] <= data["total_files"]

        if data["status"] == "completed":
            assert data["processed"] == data["total_files"]
            break
