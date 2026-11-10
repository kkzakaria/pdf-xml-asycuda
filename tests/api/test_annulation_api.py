"""Routes d'annulation d'un RFCV (registre des châssis)."""
import pytest

import chassis_registry
from chassis_registry import ChassisRegistry


@pytest.fixture
def temp_registry(tmp_path, monkeypatch):
    reg = ChassisRegistry(str(tmp_path / "registry.db"))
    monkeypatch.setattr(chassis_registry, "_registry", reg)
    return reg


@pytest.mark.asyncio
async def test_cancel_list_restore(client, temp_registry):
    for v in ("VIN00000000000001", "VIN00000000000002"):
        temp_registry.register_extracted(v, "rfcv_6014576.pdf", "RCSA6014576")

    r = await client.post("/api/v1/chassis/registry/annulations",
                          json={"rfcv_number": "6014576", "motif": "Éclaté en 6014621"})
    assert r.status_code == 200, r.text
    assert r.json() == {"rfcv_number": "6014576", "count": 2,
                        "cancelled": ["VIN00000000000001", "VIN00000000000002"]}
    assert temp_registry.check_extracted("VIN00000000000001") is None

    r = await client.get("/api/v1/chassis/registry/annulations", params={"rfcv_number": "RCSA6014576"})
    assert r.status_code == 200 and r.json()["total"] == 2
    assert r.json()["entries"][0]["reason"] == "Éclaté en 6014621"

    r = await client.post("/api/v1/chassis/registry/annulations/RCSA6014576/restaurer")
    assert r.status_code == 200 and len(r.json()["restored"]) == 2 and r.json()["conflicts"] == []
    assert temp_registry.check_extracted("VIN00000000000001") is not None


@pytest.mark.asyncio
async def test_cancel_errors(client, temp_registry):
    r = await client.post("/api/v1/chassis/registry/annulations", json={"rfcv_number": "RCSA1", "motif": "x"})
    assert r.status_code == 404
    r = await client.post("/api/v1/chassis/registry/annulations", json={"rfcv_number": "RCSA1", "motif": ""})
    assert r.status_code == 422
    r = await client.post("/api/v1/chassis/registry/annulations/RCSA1/restaurer")
    assert r.status_code == 404
    # la route de détail d'un châssis n'avale pas « annulations »
    r = await client.get("/api/v1/chassis/registry/annulations")
    assert r.status_code == 200 and r.json() == {"total": 0, "entries": []}
