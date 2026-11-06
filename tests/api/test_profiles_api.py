"""
Profil société et options de déclaration dans l'API (conversion unitaire et batch).
"""
import xml.etree.ElementTree as ET  # XML produit par l'API sous test
from pathlib import Path

import pytest

from api.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDF = ROOT / "OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf"  # RFCV sans VIN : registre non touché


@pytest.fixture(autouse=True)
def profiles_dir():
    original = settings.profiles_dir
    settings.profiles_dir = str(ROOT / "profils")
    yield
    settings.profiles_dir = original


@pytest.mark.asyncio
async def test_list_profiles(client):
    response = await client.get("/api/v1/profils")
    assert response.status_code == 200
    profils = {p["nom"]: p for p in response.json()["profils"]}
    assert profils["karta-transit"]["bureau_code"] == "CIAB6"


@pytest.mark.asyncio
@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
async def test_convert_with_profile(client):
    pdf_bytes = SAMPLE_PDF.read_bytes()
    response = await client.post(
        "/api/v1/convert",
        files={"file": (SAMPLE_PDF.name, pdf_bytes, "application/pdf")},
        data={"taux_douane": "576.42", "profil": "karta-transit", "dossier": "28926",
              "manifeste": "CIAB1 2026 5876", "nationalite_transport": "LR"},
    )
    assert response.status_code == 200, response.text
    xml_path = next(Path(settings.output_dir).rglob(response.json()["output_file"]))
    root = ET.parse(xml_path).getroot()
    assert root.findtext("Identification/Office_segment/Customs_clearance_office_code") == "CIAB6"
    assert root.findtext("Identification/Manifest_reference_number") == "CIAB1 2026 5876"
    assert root.findtext("Declarant/Declarant_code") == "00537M"
    assert root.findtext("Declarant/Reference/Number") == "KARTA28926"
    assert root.findtext("Financial/Bank/Code") == "BDU1"
    assert root.findtext("Financial/Deffered_payment_reference") == "2600537M"
    assert root.findtext("Transport/Location_of_goods") == "AIRE"
    assert root.findtext("Transport/Means_of_transport/Departure_arrival_information/Nationality") == "LR"


@pytest.mark.asyncio
@pytest.mark.parametrize("data, expected", [
    ({"profil": "inconnu"}, "Profil inconnu"),
    ({"profil": "../secret"}, "Nom de profil invalide"),
    ({"assurance": "autre"}, "assurance invalide"),
])
async def test_convert_rejects_bad_options(client, data, expected):
    response = await client.post(
        "/api/v1/convert",
        files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        data={"taux_douane": "576.42", **data},
    )
    assert response.status_code == 400
    assert expected in response.text


@pytest.mark.asyncio
async def test_batch_rejects_dossier_count_mismatch(client):
    files = [("files", (f"f{i}.pdf", b"%PDF-1.4", "application/pdf")) for i in range(2)]
    response = await client.post(
        "/api/v1/batch",
        files=files,
        data={"taux_douanes": "[576.42, 576.42]", "dossiers": '["31287"]'},
    )
    assert response.status_code == 400
    assert "dossiers" in response.text


@pytest.mark.asyncio
@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
async def test_convert_takikro(client):
    response = await client.post(
        "/api/v1/convert",
        files={"file": (SAMPLE_PDF.name, SAMPLE_PDF.read_bytes(), "application/pdf")},
        data={"taux_douane": "576.42", "profil": "karta-transit", "takikro": "true"},
    )
    assert response.status_code == 200, response.text
    xml_path = next(Path(settings.output_dir).rglob(response.json()["output_file"]))
    root = ET.parse(xml_path).getroot()
    assert root.findtext("Identification/Office_segment/Customs_clearance_office_code") == "CITKK"
    assert root.findtext("Transport/Border_office/Code") == "CITKK"
    assert root.findtext("General_information/Country/Country_first_destination") == "GH"
    assert root.findtext("Item/Previous_doc/Summary_declaration") == "ADM"


@pytest.mark.asyncio
@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
async def test_convert_disp(client):
    response = await client.post(
        "/api/v1/convert",
        files={"file": (SAMPLE_PDF.name, SAMPLE_PDF.read_bytes(), "application/pdf")},
        data={"taux_douane": "576.42", "profil": "karta-transit", "disp": "true"},
    )
    assert response.status_code == 200, response.text
    xml_path = next(Path(settings.output_dir).rglob(response.json()["output_file"]))
    assert ET.parse(xml_path).getroot().findtext("Financial/Bank/Code") == "DISP"


@pytest.mark.asyncio
@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
async def test_corps_of_converted_xml(client):
    response = await client.post(
        "/api/v1/convert",
        files={"file": (SAMPLE_PDF.name, SAMPLE_PDF.read_bytes(), "application/pdf")},
        data={"taux_douane": "576.42", "profil": "karta-transit", "disp": "true"},
    )
    assert response.status_code == 200, response.text
    output_file = response.json()["output_file"]
    corps = await client.get(f"/api/v1/corps/{Path(output_file).stem}")
    assert corps.status_code == 200, corps.text
    assert corps.headers["content-type"].startswith("text/plain")
    assert f'corps_{Path(output_file).stem}.txt' in corps.headers["content-disposition"]
    assert "Fcx_28b=DISP" in corps.text.splitlines()
    assert int(corps.headers["x-corps-items"]) >= 1

    # même XML envoyé : même corps (hors en-tête qui cite le nom du fichier)
    xml_path = next(Path(settings.output_dir).rglob(output_file))
    upload = await client.post("/api/v1/corps", files={"file": (output_file, xml_path.read_bytes(), "application/xml")})
    assert upload.status_code == 200, upload.text
    assert upload.text == corps.text


@pytest.mark.asyncio
async def test_corps_errors(client):
    assert (await client.get("/api/v1/corps/inexistant")).status_code == 404
    assert (await client.get("/api/v1/corps/..%2Fsecret")).status_code in (400, 404)
    bad = await client.post("/api/v1/corps", files={"file": ("x.txt", b"<ASYCUDA/>", "text/plain")})
    assert bad.status_code == 400
    other = await client.post("/api/v1/corps", files={"file": ("x.xml", b"<Autre/>", "application/xml")})
    assert other.status_code == 422
    bomb = (b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY e "x"><!ENTITY f "&e;&e;">]><ASYCUDA>&f;</ASYCUDA>')
    assert (await client.post("/api/v1/corps", files={"file": ("b.xml", bomb, "application/xml")})).status_code == 422
