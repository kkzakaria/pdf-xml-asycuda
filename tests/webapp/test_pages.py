"""Écrans de la webapp : Dossiers, Nouveau, Dossier (spécification §5.3 à §5.5)."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT  # noqa: E402

from api.main import app  # noqa: E402
from chassis_registry import ChassisRegistry  # noqa: E402
from webapp.auth import current_user  # noqa: E402

pytestmark = pytest.mark.asyncio

OTHER_TEXT = MULTILINE_TEXT.replace("RCSA6099999", "RCSA6088888")
VIN = "LK1PCJL85T1050418"
OP, CHEF = "op@karta.ci", "chef@karta.ci"
HX = {"HX-Request": "true"}


def pdf_bytes(text):
    return b"%PDF-1.4\n" + text.encode("utf-8")


@pytest.fixture
def fake_pdf(monkeypatch):
    """Extracteur PDF factice (comme test_dossiers.py) : le texte est lu dans le fichier."""
    import pdf_extractor
    import rfcv_parser

    class FakeExtractor:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return Path(self.path).read_bytes().split(b"\n", 1)[1].decode("utf-8")

        def extract_all_tables(self):
            return []

    monkeypatch.setattr(rfcv_parser, "PDFExtractor", FakeExtractor)
    monkeypatch.setattr(pdf_extractor, "PDFExtractor", FakeExtractor)


@pytest.fixture
def as_user(webapp_settings, tmp_path):
    """Passe en mode développement avec l'utilisateur donné (registre temporaire)."""
    def _as(email=OP):
        return webapp_settings(access_aud="", dev_user=email, admins=[CHEF],
                               registry_path=tmp_path / "registre.db",
                               profile_path=ROOT / "profils" / "karta-transit.ini")
    _as()
    return _as


async def upload(client, *files):
    return await client.post("/nouveau", files=[("fichiers", (name, pdf_bytes(text), "application/pdf"))
                                                 for name, text in files])


async def new_dossier(client, name="a.pdf", text=MULTILINE_TEXT) -> int:
    r = await upload(client, (name, text))
    assert r.status_code == 303, r.text
    r = await client.get("/")
    ids = [int(i) for i in re.findall(r'href="/dossiers/(\d+)"', r.text)]
    return max(ids)


def form(**kw):
    data = {"taux_douane": "596,302", "profile": "karta-transit.ini", "fob_mode": "prorata",
            "assurance_mode": "formule", "designation": "MOTO"}
    data.update(kw)
    return data


async def generate(client, dossier_id, **kw):
    return await client.post(f"/dossiers/{dossier_id}/generer", data=form(**kw), headers=HX)


def declare_button(html):
    m = re.search(r'<button[^>]*id="declarer"[^>]*>', html)
    assert m, "bouton « Déclaré dans SYDAM » absent"
    return m.group(0)


# ------------------------------------------------------------------ Nouveau / Dossiers
async def test_upload_two_pdfs_creates_two_dossiers(client, as_user, fake_pdf):
    r = await client.get("/nouveau")
    assert r.status_code == 200 and 'type="file"' in r.text and "multiple" in r.text
    r = await upload(client, ("a.pdf", MULTILINE_TEXT), ("b.pdf", OTHER_TEXT))
    assert r.status_code == 303 and r.headers["location"] == "/"
    r = await client.get("/")
    assert r.status_code == 200
    assert "RCSA6099999" in r.text and "RCSA6088888" in r.text
    assert len(set(re.findall(r'href="/dossiers/(\d+)"', r.text))) == 2
    assert "Brouillon" in r.text and OP in r.text
    # un fichier qui n'est pas un PDF : message, les autres sont créés
    r = await client.post("/nouveau", files=[
        ("fichiers", ("c.pdf", pdf_bytes(MULTILINE_TEXT), "application/pdf")),
        ("fichiers", ("<script>x</script>.pdf", b"<html>", "application/pdf"))])
    assert r.status_code == 200
    assert "n'est pas un fichier PDF" in r.text or "n&#39;est pas un fichier PDF" in r.text
    assert "<script>x</script>" not in r.text          # échappé
    r = await client.get("/")
    assert len(set(re.findall(r'href="/dossiers/(\d+)"', r.text))) == 3


async def test_search_by_vin(client, as_user, fake_pdf):
    a = await new_dossier(client, "a.pdf", MULTILINE_TEXT)
    b = await new_dossier(client, "b.pdf", OTHER_TEXT.replace(VIN, "ZZZ00000000000001"))
    assert (await generate(client, a)).status_code == 200
    assert (await generate(client, b)).status_code == 200
    r = await client.get("/", params={"q": VIN.lower()})
    assert r.status_code == 200
    assert f'href="/dossiers/{a}"' in r.text and f'href="/dossiers/{b}"' not in r.text
    r = await client.get("/", params={"q": "6088888"})
    assert f'href="/dossiers/{b}"' in r.text and f'href="/dossiers/{a}"' not in r.text


# ------------------------------------------------------------------ Dossier : génération
async def test_generate_shows_recap_values(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await client.get(f"/dossiers/{d}")
    assert r.status_code == 200
    assert 'name="taux_douane"' in r.text and "596.302" in r.text      # pré-rempli
    assert "Générer" in r.text
    assert "devise du RFCV" in r.text and "(XOF)" in r.text
    r = await generate(client, d, fob_revise="5 400", fob_revise_par_article="1", fob_mode="uniforme",
                       fret="2000", fret_par_article="1", assurance_mode="imposee",
                       assurance="93", assurance_par_article="1")
    assert r.status_code == 200, r.text
    html = r.text
    assert "<html" not in html                         # fragment htmx
    assert "3 × 5 400" in html and "3 × 2 000" in html and "3 × 93" in html
    assert "16 200" in html                            # FOB total
    assert "CIAB6" in html                             # bureau (profil Karta)
    assert "FOB révisé" in html                        # écart
    assert "Fichiers" in html and f"/dossiers/{d}/fichiers/1/corps" in html
    # la page affiche la dernière génération et ses réglages
    r = await client.get(f"/dossiers/{d}")
    assert "3 × 5 400" in r.text and 'value="5400"' in r.text
    assert "Génération 1" in r.text
    # sans htmx : redirection vers la page du dossier
    r = await client.post(f"/dossiers/{d}/generer", data=form())
    assert r.status_code == 303 and r.headers["location"] == f"/dossiers/{d}"
    r = await client.get(f"/dossiers/{d}")
    assert "Génération 2" in r.text


async def test_invalid_amount_rerenders_form_with_error(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await client.post(f"/dossiers/{d}/generer", data=form(fob_revise="12abc", taux_douane="600"))
    assert r.status_code == 422
    assert "FOB révisé" in r.text and "nombre" in r.text
    assert 'name="taux_douane"' in r.text and 'value="600"' in r.text      # saisie conservée
    assert 'value="12abc"' in r.text
    r = await generate(client, d, taux_douane="")
    assert r.status_code == 200 and r.headers.get("HX-Retarget") == "#reglages"
    assert "Taux douanier" in r.text and 'name="taux_douane"' in r.text
    r = await generate(client, d, assurance_mode="imposee", assurance="")
    assert "assurance" in r.text.lower() and r.headers.get("HX-Retarget") == "#reglages"
    r = await client.get(f"/dossiers/{d}")
    assert "Génération 1" not in r.text


async def test_generation_failure_shown(client, as_user):
    r = await client.post("/nouveau", files=[("fichiers", ("casse.pdf", b"%PDF-1.4\nrien", "application/pdf"))])
    assert r.status_code == 303
    d = int(re.findall(r'href="/dossiers/(\d+)"', (await client.get("/")).text)[0])
    r = await generate(client, d)
    assert r.status_code == 200 and "Échec de la génération" in r.text


# ------------------------------------------------------------------ téléchargements
async def test_download_corps_is_text_with_filename(client, as_user, fake_pdf):
    d = await new_dossier(client, "a.pdf")
    await generate(client, d)
    r = await client.get(f"/dossiers/{d}/fichiers/1/corps")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert 'filename="corps_a.txt"' in r.headers["content-disposition"]
    assert "Fcx_10=" in r.text
    r = await client.get(f"/dossiers/{d}/fichiers/1/xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert 'filename="a.xml"' in r.headers["content-disposition"]
    r = await client.get(f"/dossiers/{d}/fichiers/1/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content == pdf_bytes(MULTILINE_TEXT)
    for url in (f"/dossiers/{d}/fichiers/2/corps", f"/dossiers/{d}/fichiers/1/exe",
                f"/dossiers/{d + 1}/fichiers/1/corps", f"/dossiers/{d}/fichiers/1/..%2F..%2Fwebapp.db",
                "/dossiers/999/fichiers/1/xml"):
        assert (await client.get(url)).status_code == 404, url
    assert (await client.get("/dossiers/999")).status_code == 404


# ------------------------------------------------------------------ déclaration
async def test_declare_button_disabled_with_blocking_alert(client, as_user, fake_pdf, tmp_path):
    a = await new_dossier(client, "a.pdf", MULTILINE_TEXT)
    b = await new_dossier(client, "b.pdf", OTHER_TEXT)
    # aucune génération : bouton désactivé
    assert "disabled" in declare_button((await client.get(f"/dossiers/{a}")).text)
    r = await generate(client, a)
    assert "disabled" not in declare_button(r.text)
    r = await client.post(f"/dossiers/{a}/declarer")
    assert r.status_code == 303
    page = (await client.get(f"/dossiers/{a}")).text
    assert "Déclaré" in page and 'name="taux_douane"' not in page and "Générer" not in page
    assert {e["chassis_number"] for e in ChassisRegistry(str(tmp_path / "registre.db")).get_all_extracted()} \
        >= {VIN}
    # b reprend les châssis déclarés par a : alerte bloquante en rouge, bouton désactivé
    r = await generate(client, b)
    assert "alerte-bloquante" in r.text and "déjà déclaré" in r.text
    assert "disabled" in declare_button(r.text)
    # la déclaration forcée est refusée, sans erreur 500
    r = await client.post(f"/dossiers/{b}/declarer")
    assert r.status_code == 409
    assert "RCSA6099999" in r.text and "<html" in r.text
    # dossier déjà déclaré : refus lisible
    r = await client.post(f"/dossiers/{a}/declarer")
    assert r.status_code == 409 and "déclaré" in r.text


async def test_operator_cannot_revert(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await generate(client, d)
    assert (await client.post(f"/dossiers/{d}/declarer")).status_code == 303
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Remettre en brouillon" not in page
    r = await client.post(f"/dossiers/{d}/brouillon")
    assert r.status_code == 403
    assert "Déclaré" in (await client.get(f"/dossiers/{d}")).text
    as_user(CHEF)
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Remettre en brouillon" in page and 'href="/chassis"' in page
    r = await client.post(f"/dossiers/{d}/brouillon")
    assert r.status_code == 303
    page = (await client.get(f"/dossiers/{d}")).text
    assert 'name="taux_douane"' in page


# ------------------------------------------------------------------ structure
def _http_routes(routes):
    """Routes HTTP de l'application, routeurs inclus dépliés (FastAPI récent : _IncludedRouter)."""
    for route in routes:
        if hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()
        else:
            yield route


async def test_every_webapp_route_requires_user():
    """Sans configuration d'accès le garde laisse passer : chaque page doit exiger current_user."""
    docs = {app.docs_url, app.redoc_url, app.openapi_url, app.swagger_ui_oauth2_redirect_url}
    checked = set()
    for route in _http_routes(app.routes):
        path = getattr(route, "path", "")
        if path.startswith("/api") or path.startswith("/static") or path in docs:
            continue
        dependant = getattr(route, "dependant", None)
        assert dependant is not None, f"route sans dépendances : {path}"
        assert current_user in {d.call for d in dependant.dependencies}, path
        checked.add((path, tuple(sorted(route.methods))))
    assert len(checked) >= 8
    assert ("/dossiers/{dossier_id}/fichiers/{n}/{kind}", ("GET",)) in checked


async def test_static_and_layout(client, as_user):
    r = await client.get("/static/htmx.min.js")
    assert r.status_code == 200 and 'version:"1.9.12"' in r.text
    r = await client.get("/static/app.css")
    assert r.status_code == 200
    r = await client.get("/")
    assert "Génération XML &amp; corps" in r.text or "Génération XML & corps" in r.text
    assert "Connecté : op@karta.ci" in r.text and 'href="/chassis"' not in r.text
    assert "https://" not in re.sub(r"<a [^>]*>", "", r.text)              # aucun script externe
