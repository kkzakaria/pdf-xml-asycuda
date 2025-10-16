"""
Tests des endpoints health et metrics
"""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test du health check endpoint"""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "total_jobs" in data
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test de l'endpoint racine"""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert "name" in data
    assert "version" in data
    assert "endpoints" in data
    assert "conversion" in data["endpoints"]
    assert "batch" in data["endpoints"]


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    """Test de l'endpoint métriques"""
    response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    data = response.json()

    assert "total_conversions" in data
    assert "successful" in data
    assert "failed" in data
    assert "success_rate" in data
    assert "avg_processing_time" in data
    assert data["total_conversions"] >= 0


@pytest.mark.asyncio
async def test_openapi_docs(client):
    """Test que la doc OpenAPI est accessible"""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    data = response.json()

    assert "openapi" in data
    assert "info" in data
    assert "paths" in data

    # Vérifier que les endpoints sont documentés
    assert "/api/v1/health" in data["paths"]
    assert "/api/v1/convert" in data["paths"]
    assert "/api/v1/batch" in data["paths"]
