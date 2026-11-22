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
from webapp.routes import same_origin  # noqa: E402

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


async def test_banque_setting(client, as_user, fake_pdf):
    """Réglage « Banque (case 28) » : remplace la banque du profil, conservé dans le formulaire."""
    d = await new_dossier(client)
    r = await client.get(f"/dossiers/{d}")
    assert 'name="banque"' in r.text and "Banque (case 28)" in r.text
    r = await generate(client, d, banque=" SGBC ")
    assert r.status_code == 200, r.text
    r = await client.get(f"/dossiers/{d}/fichiers/1/corps")
    assert "Fcx_28b=SGBC" in r.text
    r = await client.get(f"/dossiers/{d}")
    assert 'name="banque" value="SGBC"' in r.text


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


async def test_declare_button_disabled_without_rfcv_number(client, as_user, fake_pdf):
    d = await new_dossier(client, "a.pdf", MULTILINE_TEXT.replace("RCSA6099999", "XXXA6099999"))
    r = await generate(client, d)
    assert "disabled" in declare_button(r.text)
    assert "N° RFCV illisible" in r.text
    r = await client.post(f"/dossiers/{d}/declarer")
    assert r.status_code == 409 and "N° RFCV illisible" in r.text


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
        calls = {d.call for d in dependant.dependencies}
        assert current_user in calls and same_origin in calls, path
        checked.add((path, tuple(sorted(route.methods))))
    assert len(checked) >= 8
    assert ("/dossiers/{dossier_id}/fichiers/{n}/{kind}", ("GET",)) in checked


async def test_static_and_layout(client, as_user):
    r = await client.get("/static/htmx.min.js")
    assert r.status_code == 200 and 'version:"1.9.12"' in r.text
    # /static/app.css est compilé (scripts/css.sh, étape « css » du Dockerfile) : les tests n'en dépendent pas
    r = await client.get("/")
    assert "Génération XML &amp; corps" in r.text or "Génération XML & corps" in r.text
    assert 'title="op@karta.ci"' in r.text and 'href="/chassis"' not in r.text
    assert "https://" not in re.sub(r"<a [^>]*>", "", r.text)              # aucun script externe


# ------------------------------------------------------------------ CSRF
async def test_cross_site_post_rejected(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await generate(client, d)
    r = await client.post(f"/dossiers/{d}/declarer", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403 and "autre site" in r.text
    r = await client.post(f"/dossiers/{d}/declarer", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post(f"/dossiers/{d}/declarer", headers={"Origin": "null"})
    assert r.status_code == 403
    r = await client.post("/nouveau", headers={"Origin": "https://evil.example"},
                          files=[("fichiers", ("x.pdf", pdf_bytes(OTHER_TEXT), "application/pdf"))])
    assert r.status_code == 403
    assert "statut-genere" in (await client.get(f"/dossiers/{d}")).text      # rien déclaré (brouillon généré)
    # GET non concerné, même depuis un autre site
    r = await client.get(f"/dossiers/{d}", headers={"Sec-Fetch-Site": "cross-site",
                                                    "Origin": "https://evil.example"})
    assert r.status_code == 200
    # même origine : accepté
    r = await client.post(f"/dossiers/{d}/declarer", headers={"Origin": "http://test",
                                                              "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 303


async def test_api_routes_not_subject_to_origin_check(client, as_user):
    r = await client.get("/api", headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
    assert r.status_code == 200


# ------------------------------------------------------------------ revue finale
async def test_dossier_page_shows_history(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await generate(client, d)
    await client.post(f"/dossiers/{d}/declarer")
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Historique du dossier" in page
    hist = page[page.index("Historique du dossier"):]
    # le plus récent d'abord : déclaration, génération, dépôt
    assert hist.index("Déclaré dans SYDAM") < hist.index("Génération") < hist.index("Dépôt")
    assert OP in hist
    # n° de la génération déclarée
    assert "génération 1 déclarée" in page


async def test_chassis_page_shows_recent_admin_actions(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await generate(client, d)
    await client.post(f"/dossiers/{d}/declarer")
    as_user(CHEF)
    r = await client.post("/chassis/annuler", data={"rfcv": "RCSA6099999", "motif": "éclaté en deux"})
    assert r.status_code == 303
    page = (await client.get("/chassis")).text
    assert "Dernières actions" in page
    actions = page[page.index("Dernières actions"):]
    assert "RFCV annulé" in actions and CHEF in actions and "éclaté en deux" in actions


async def test_abandon_and_reopen_pages(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Abandonner ce brouillon" in page and "confirm(" in page
    # un autre opérateur ne voit pas le bouton et est refusé
    as_user("autre@karta.ci")
    assert "Abandonner ce brouillon" not in (await client.get(f"/dossiers/{d}")).text
    assert (await client.post(f"/dossiers/{d}/abandonner")).status_code == 403
    as_user(OP)
    r = await client.post(f"/dossiers/{d}/abandonner")
    assert r.status_code == 303
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Abandonné" in page and 'name="taux_douane"' not in page and "Rouvrir" not in page
    assert (await client.post(f"/dossiers/{d}/abandonner")).status_code == 409
    liste = (await client.get("/")).text
    assert 'class="abandonne ' in liste and "Abandonné" in liste
    assert (await client.post(f"/dossiers/{d}/reouvrir")).status_code == 403
    as_user(CHEF)
    assert "Rouvrir" in (await client.get(f"/dossiers/{d}")).text
    assert (await client.post(f"/dossiers/{d}/reouvrir")).status_code == 303
    assert 'name="taux_douane"' in (await client.get(f"/dossiers/{d}")).text


async def test_failed_regeneration_labels_previous_and_blocks_declare(client, as_user, fake_pdf, monkeypatch):
    import webapp.dossiers as dossiers_mod
    d = await new_dossier(client)
    r = await generate(client, d)
    assert "disabled" not in declare_button(r.text)
    original = dossiers_mod.generate_drafts

    def boom(*a, **kw):
        raise RuntimeError("moteur en panne")

    monkeypatch.setattr(dossiers_mod, "generate_drafts", boom)
    r = await generate(client, d)
    monkeypatch.setattr(dossiers_mod, "generate_drafts", original)
    assert "moteur en panne" in r.text
    assert "précédente — la dernière tentative a échoué" in r.text
    assert "disabled" in declare_button(r.text)
    r = await generate(client, d)
    assert "précédente" not in r.text and "disabled" not in declare_button(r.text)


async def test_zero_amounts_rejected(client, as_user, fake_pdf):
    d = await new_dossier(client)
    for field, label in (("fob_revise", "FOB révisé"), ("fret", "Fret"), ("assurance", "Assurance")):
        extra = {"assurance_mode": "imposee"} if field == "assurance" else {}
        r = await client.post(f"/dossiers/{d}/generer", data=form(**{field: "0"}, **extra))
        assert r.status_code == 422, field
        assert f"{label} : le montant doit être strictement positif" in r.text
    assert "Génération 1" not in (await client.get(f"/dossiers/{d}")).text


async def test_htmx_error_handler_in_layout(client, as_user):
    page = (await client.get("/nouveau")).text
    assert "htmx:sendError" in page and "htmx:responseError" in page
    assert "Session expirée ou erreur réseau : rechargez la page." in page


async def test_original_pdf_download_without_generation(client, as_user, fake_pdf):
    d = await new_dossier(client, "a.pdf")
    r = await client.get(f"/dossiers/{d}/pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert 'filename="a.pdf"' in r.headers["content-disposition"]
    assert r.content == pdf_bytes(MULTILINE_TEXT)
    assert f'href="/dossiers/{d}/pdf"' in (await client.get(f"/dossiers/{d}")).text
    assert (await client.get("/dossiers/999/pdf")).status_code == 404


async def test_original_pdf_path_confined(client, as_user, fake_pdf, tmp_path):
    import sqlite3
    d = await new_dossier(client, "a.pdf")
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF secret")
    conn = sqlite3.connect(tmp_path / "webapp" / "webapp.db")
    conn.execute("UPDATE dossiers SET pdf_path = ? WHERE id = ?", (str(secret), d))
    conn.commit()
    conn.close()
    assert (await client.get(f"/dossiers/{d}/pdf")).status_code == 404


async def test_currency_label_before_first_generation(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert "devise du RFCV : devise du RFCV" not in page
    assert "(devise du RFCV)" in page


# ------------------------------------------------------------------ mise en page Karta
async def test_menu_lateral(client, as_user):
    r = await client.get("/")
    assert '/static/img/logo-karta-transit.jpg' in r.text
    assert re.search(r'<a [^>]*href="/"[^>]*aria-current="page"', r.text)
    assert 'href="/nouveau"' in r.text and "Déposer des RFCV" in r.text
    assert OP in r.text and "Opérateur" in r.text


async def test_menu_chassis_admin_seulement(client, as_user):
    page = (await client.get("/")).text
    assert 'href="/chassis"' not in page and "ADMIN" not in page
    as_user(CHEF)
    page = (await client.get("/")).text
    assert 'href="/chassis"' in page and "ADMIN" in page and "Administrateur" in page


async def test_menu_actif_suit_la_page(client, as_user):
    page = (await client.get("/nouveau")).text
    assert re.search(r'<a [^>]*href="/nouveau"[^>]*aria-current="page"', page)
    assert not re.search(r'<a [^>]*href="/"[^>]*aria-current="page"', page)


async def test_page_filtres(client, as_user, fake_pdf):
    await new_dossier(client)
    r = await client.get("/", params={"statut": "declare"})
    assert r.status_code == 200
    assert re.search(r'<a [^>]*href="/\?statut=declare"[^>]*aria-current="true"', r.text)
    assert "RCSA6099999" not in r.text                                   # brouillon filtré
    r = await client.get("/", params={"statut": "zzz"})
    assert r.status_code == 200 and "RCSA6099999" in r.text              # filtre inconnu : tous
    assert re.search(r'<a [^>]*href="/"[^>]*aria-current="true"', r.text)


async def test_page_vide(client, as_user):
    r = await client.get("/")
    assert "Aucun dossier" in r.text and 'href="/nouveau"' in r.text


async def test_recherche_garde_le_filtre(client, as_user):
    r = await client.get("/", params={"statut": "genere", "q": "6099"})
    assert 'name="statut" value="genere"' in r.text and 'value="6099"' in r.text


async def test_page_depot(client, as_user):
    r = await client.get("/nouveau")
    assert 'type="file"' in r.text and 'name="fichiers"' in r.text and "multiple" in r.text
    assert 'accept="application/pdf,.pdf"' in r.text
    assert "Glissez vos PDF RFCV ici" in r.text and "/static/depot.js" in r.text
    assert (await client.get("/static/depot.js")).status_code == 200


# ------------------------------------------------------------------ fiche dossier (refonte)
def etat_etape(html, libelle):
    m = re.search(r'<li[^>]*data-etat="([a-z_]+)"[^>]*>(?:(?!</li>).)*' + re.escape(libelle), html, re.S)
    assert m, f"étape « {libelle} » absente"
    return m.group(1)


async def test_fiche_etapes_avant_generation(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert 'id="etapes"' in page
    assert etat_etape(page, "Réglages et génération") == "actif"
    assert etat_etape(page, "Vérification") == "a_faire"
    assert "Pas encore généré" in page


async def test_generation_htmx_met_a_jour_etapes(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d)
    assert 'id="recap"' in r.text
    assert re.search(r'<ol[^>]*id="etapes"[^>]*hx-swap-oob="true"', r.text)
    assert etat_etape(r.text, "Vérification") == "actif"
    assert etat_etape(r.text, "Réglages et génération") == "fait"


async def test_generation_erreur_saisie_htmx(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d, taux_douane="abc")
    assert r.headers.get("HX-Retarget") == "#reglages"
    assert "Taux douanier" in r.text and 'id="recap"' not in r.text


async def test_bouton_declarer_desactive_puis_vert(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert "disabled" in declare_button(page) and "Générer le dossier avant de le déclarer" in page
    r = await generate(client, d)
    bouton = declare_button(r.text)
    assert "disabled" not in bouton and "bg-succes" in bouton


async def test_dossier_abandonne_etapes_inactives(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await client.post(f"/dossiers/{d}/abandonner")
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Brouillon abandonné" in page and 'id="generer"' not in page
    assert etat_etape(page, "Vérification") == "inactif"


async def test_indicateur_generation(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert re.search(r'id="generation-en-cours"[^>]*class="[^"]*htmx-indicator', page)
    assert "environ 20 s pour 300 motos" in page
    assert re.search(r'id="recap"[^>]*aria-live="polite"', page)


async def test_fiche_cartes_montants(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d)
    for libelle in ("FOB", "Fret", "Assurance", "CIF"):
        assert f">{libelle}</span>" in r.text
    assert "Génération n° 1 réussie" in r.text


async def test_generation_htmx_met_a_jour_pastille(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d)
    m = re.search(r'<span[^>]*id="statut-dossier"[^>]*hx-swap-oob="true"[^>]*>(.*?)</span>\s*</span>', r.text, re.S)
    assert m and "Généré" in m.group(0)


# ------------------------------------------------------------------ revue finale
async def test_dossier_abandonne_sans_invitation_a_generer(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await client.post(f"/dossiers/{d}/abandonner")
    page = (await client.get(f"/dossiers/{d}")).text
    assert "Pas encore généré" not in page and "lancez la génération" not in page


async def test_generation_htmx_met_a_jour_bouton_generer(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d)
    m = re.search(r'<button[^>]*id="generer"[^>]*>', r.text)
    assert m and 'hx-swap-oob="true"' in m.group(0)
    assert "Régénérer" in r.text[m.start():m.start() + 2000]
    assert re.search(r'id="derniere-generation"[^>]*hx-swap-oob="true"[^>]*>[^<]*n° 1', r.text)


def test_accessibilite_contraste_et_cibles():
    gabarits = Path(ROOT / "src" / "webapp" / "templates")
    texte = "".join(p.read_text(encoding="utf-8") for p in gabarits.glob("*.html"))
    assert "#8A8EAE" not in texte                         # gris 3,2:1 : sous le seuil de 4,5:1
    liste = (gabarits / "dossiers.html").read_text(encoding="utf-8")
    assert "h-9" not in liste and "outline-none" not in liste
    assert "focus-within:ring" in liste
    assert "focus-within:ring" in (gabarits / "nouveau.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------ petits défauts (revue finale)
async def test_bandeau_fige_gris(client, as_user, fake_pdf):
    d = await new_dossier(client)
    await client.post(f"/dossiers/{d}/abandonner")
    page = (await client.get(f"/dossiers/{d}")).text
    m = re.search(r'<div class="[^"]*alerte-(\w+)[^"]*"[^>]*>(?:(?!</div>).)*Brouillon abandonné', page, re.S)
    assert m and m.group(1) == "neutre"


async def test_badge_admin_rouge_karta(client, as_user):
    as_user(CHEF)
    page = (await client.get("/")).text
    badge = re.search(r'<span class="([^"]*)">ADMIN</span>', page)
    assert badge and "karta-rouge" in badge.group(1) and "erreur" not in badge.group(1)


async def test_filtre_inconnu_et_recherche(client, as_user, fake_pdf):
    await new_dossier(client)
    await new_dossier(client, "b.pdf", OTHER_TEXT)
    r = await client.get("/", params={"statut": "zzz", "q": "6088888"})
    assert r.status_code == 200 and "RCSA6088888" in r.text and "RCSA6099999" not in r.text


def test_depot_filtre_les_pdf_glisses():
    js = (ROOT / "src" / "webapp" / "static" / "depot.js").read_text(encoding="utf-8")
    assert "new DataTransfer()" in js and "estPdf" in js


def test_script_css_multi_plateforme():
    script = (ROOT / "scripts" / "css.sh").read_text(encoding="utf-8")
    for plateforme in ("linux-x64", "linux-arm64", "macos-arm64", "macos-x64"):
        assert f"tailwindcss-{plateforme}" in script


async def test_menu_lateral_fixe(client, as_user):
    page = (await client.get("/")).text
    aside = re.search(r'<aside class="([^"]*)"', page).group(1).split()
    assert {"md:sticky", "md:top-0", "md:h-screen", "md:overflow-y-auto"} <= set(aside)


# ------------------------------------------------------------------ date de FDI (validation)
from fdi_fictive import ecrire_pdf, fdi_fictive  # noqa: E402


async def generer_avec_fdi(client, dossier_id, pdf: Path | None = None, **kw):
    files = [("fdi", ("fdi.pdf", pdf.read_bytes(), "application/pdf"))] if pdf else None
    return await client.post(f"/dossiers/{dossier_id}/generer", data=form(**kw), files=files, headers=HX)


async def test_reglages_champs_fdi(client, as_user, fake_pdf):
    d = await new_dossier(client)
    page = (await client.get(f"/dossiers/{d}")).text
    assert 'name="date_fdi"' in page and 'name="fdi"' in page and 'type="file"' in page
    assert 'hx-encoding="multipart/form-data"' in page


async def test_generation_sans_fdi_avertit(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d)
    assert "Date de FDI non vérifiée (date de la RFCV : 30/10/2026)" in r.text
    assert "disabled" not in declare_button(r.text)               # avertissement non bloquant


async def test_generation_date_fdi_saisie(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d, date_fdi="02/11/2026")
    assert "non vérifiée" not in r.text and "02/11/2026 (saisie)" in r.text
    assert 'name="date_fdi" value="02/11/2026"' in (await client.get(f"/dossiers/{d}")).text


async def test_generation_date_fdi_invalide(client, as_user, fake_pdf):
    d = await new_dossier(client)
    r = await generate(client, d, date_fdi="2026-11-02")
    assert r.headers.get("HX-Retarget") == "#reglages" and "JJ/MM/AAAA" in r.text


async def test_generation_pdf_fdi_conserve(client, as_user, fake_pdf, tmp_path):
    d = await new_dossier(client)
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260200000", date_validation="03/11/2026")
    r = await generer_avec_fdi(client, d, pdf)
    assert r.status_code == 200 and "03/11/2026 (FDI validée)" in r.text and "non vérifiée" not in r.text
    # régénération sans renvoyer le PDF : la FDI jointe reste utilisée
    r = await generate(client, d)
    assert "03/11/2026 (FDI validée)" in r.text
    page = (await client.get(f"/dossiers/{d}")).text
    assert "FDI jointe" in page and "260200000" in page


async def test_generation_pdf_fdi_numero_different_bloque(client, as_user, fake_pdf, tmp_path):
    d = await new_dossier(client)
    r = await generer_avec_fdi(client, d, fdi_fictive(tmp_path / "fdi.pdf", numero="260299999"))
    assert "N° de FDI différent" in r.text and "disabled" in declare_button(r.text)


async def test_generation_pdf_qui_n_est_pas_une_fdi(client, as_user, fake_pdf, tmp_path):
    d = await new_dossier(client)
    autre = ecrire_pdf(tmp_path / "x.pdf", [(50, 50, "AUTRE DOCUMENT")])
    r = await generer_avec_fdi(client, d, autre)
    assert r.headers.get("HX-Retarget") == "#reglages" and "pas une FDI lisible" in r.text
