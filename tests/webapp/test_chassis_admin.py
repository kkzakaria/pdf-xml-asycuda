"""Écran Châssis (administrateurs) : annulation d'un RFCV, restauration, codes SH habituels."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT  # noqa: E402

from chassis_registry import ChassisRegistry  # noqa: E402
from webapp import config, db  # noqa: E402

pytestmark = pytest.mark.asyncio

OTHER_TEXT = MULTILINE_TEXT.replace("RCSA6099999", "RCSA6088888")
VIN = "LK1PCJL85T1050418"
OP, CHEF = "op@karta.ci", "chef@karta.ci"
RFCV_A, RFCV_B = "RCSA6099999", "RCSA6088888"


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
    def _as(email=CHEF):
        return webapp_settings(access_aud="", dev_user=email, admins=[CHEF],
                               registry_path=tmp_path / "registre.db",
                               profile_path=ROOT / "profils" / "karta-transit.ini")
    _as()
    return _as


@pytest.fixture
def registry(tmp_path, as_user):
    return ChassisRegistry(str(tmp_path / "registre.db"))


async def declared_dossier(client, name, text):
    """Dossier généré puis déclaré ; renvoie son id."""
    r = await client.post("/nouveau", files=[("fichiers", (name, pdf_bytes(text), "application/pdf"))])
    assert r.status_code == 303, r.text
    d = max(int(i) for i in re.findall(r'href="/dossiers/(\d+)"', (await client.get("/")).text))
    r = await generer(client, d)
    assert r.status_code == 303, r.text
    r = await client.post(f"/dossiers/{d}/declarer")
    return d, r


async def generer(client, d):
    return await client.post(f"/dossiers/{d}/generer", data={
        "taux_douane": "596,302", "profile": "karta-transit.ini", "fob_mode": "prorata",
        "assurance_mode": "formule", "designation": "MOTO"})


def status_of(d):
    conn = db.connect(config.get_settings().data_dir / "webapp.db")
    try:
        return conn.execute("SELECT status FROM dossiers WHERE id = ?", (d,)).fetchone()[0]
    finally:
        conn.close()


async def test_cancel_rfcv_marks_dossier_and_frees_chassis(client, as_user, fake_pdf, registry):
    a, r = await declared_dossier(client, "a.pdf", MULTILINE_TEXT)
    assert r.status_code == 303 and status_of(a) == "declare"
    assert registry.get_entry(VIN)["rfcv_number"] == RFCV_A
    # le même VIN dans un autre RFCV est bloqué tant que le premier n'est pas annulé
    b, r = await declared_dossier(client, "b.pdf", OTHER_TEXT)
    assert r.status_code == 409 and status_of(b) == "brouillon"

    r = await client.post("/chassis/annuler", data={"rfcv": "rcsa 6099999", "motif": "Annulé par l'inspection"})
    assert r.status_code == 303 and r.headers["location"].startswith("/chassis")
    assert status_of(a) == "annule"
    assert registry.get_entry(VIN) is None
    page = (await client.get("/chassis", params={"vin": VIN.lower()})).text
    assert "Annulé par l&#39;inspection" in page and RFCV_A in page and f'href="/dossiers/{a}"' in page
    assert "Absent du registre actif" in page
    # le nouveau RFCV peut maintenant être régénéré (plus d'alerte bloquante) puis déclaré
    await generer(client, b)
    assert (await client.post(f"/dossiers/{b}/declarer")).status_code == 303
    assert registry.get_entry(VIN)["rfcv_number"] == RFCV_B
    # RFCV sans châssis enregistré : message, aucun changement
    r = await client.post("/chassis/annuler", data={"rfcv": "RCSA1111111", "motif": "x"})
    assert r.status_code == 422 and "châssis enregistré pour ce RFCV" in r.text
    assert status_of(a) == "annule"


async def test_restore_conflict_shown(client, as_user, fake_pdf, registry):
    a, _ = await declared_dossier(client, "a.pdf", MULTILINE_TEXT)
    await client.post("/chassis/annuler", data={"rfcv": RFCV_A, "motif": "erreur"})
    b, r = await declared_dossier(client, "b.pdf", OTHER_TEXT)
    assert r.status_code == 303
    r = await client.post(f"/chassis/restaurer/{RFCV_A}")
    assert r.status_code == 200 and VIN in r.text and "conflit" in r.text
    assert status_of(a) == "annule"                      # reste annulé
    assert registry.get_entry(VIN)["rfcv_number"] == RFCV_B


async def test_restore_back_to_declare(client, as_user, fake_pdf, registry):
    a, _ = await declared_dossier(client, "a.pdf", MULTILINE_TEXT)
    await client.post("/chassis/annuler", data={"rfcv": RFCV_A, "motif": "erreur de manipulation"})
    assert status_of(a) == "annule"
    page = (await client.get("/chassis")).text
    assert f"/chassis/restaurer/{RFCV_A}" in page and "erreur de manipulation" in page
    r = await client.post(f"/chassis/restaurer/{RFCV_A}")
    assert r.status_code == 303
    assert status_of(a) == "declare"
    assert registry.get_entry(VIN)["rfcv_number"] == RFCV_A
    assert f"/chassis/restaurer/{RFCV_A}" not in (await client.get("/chassis")).text
    # plus rien à restaurer : message, pas d'erreur 500
    r = await client.post(f"/chassis/restaurer/{RFCV_A}")
    assert r.status_code == 422 and "restaurer" in r.text


async def test_empty_motif_rejected(client, as_user, fake_pdf, registry):
    a, _ = await declared_dossier(client, "a.pdf", MULTILINE_TEXT)
    for motif in ("", "   "):
        r = await client.post("/chassis/annuler", data={"rfcv": RFCV_A, "motif": motif})
        assert r.status_code == 422 and "Motif d&#39;annulation obligatoire" in r.text
    assert status_of(a) == "declare" and registry.get_entry(VIN) is not None


async def test_operator_forbidden_403(client, as_user, fake_pdf, registry):
    a, _ = await declared_dossier(client, "a.pdf", MULTILINE_TEXT)
    as_user(OP)
    assert (await client.get("/chassis")).status_code == 403
    assert (await client.post("/chassis/annuler", data={"rfcv": RFCV_A, "motif": "x"})).status_code == 403
    assert (await client.post(f"/chassis/restaurer/{RFCV_A}")).status_code == 403
    r = await client.post("/chassis/code-sh-normal", data={"designation": "MOTO", "hs_code": "8711"})
    assert r.status_code == 403
    assert status_of(a) == "declare" and registry.get_entry(VIN) is not None
    assert "/chassis" not in (await client.get("/")).text.replace("/chassis?", "")  # pas de lien
    # même origine exigée : une requête inter-sites est refusée même pour un administrateur
    as_user(CHEF)
    r = await client.post("/chassis/annuler", data={"rfcv": RFCV_A, "motif": "x"},
                          headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403 and status_of(a) == "declare"


async def test_mark_hs_known_silences_alert(client, as_user, fake_pdf):
    # un couple déjà connu pour que les alertes de code SH soient actives
    conn = db.connect(config.get_settings().data_dir / "webapp.db")
    db.init(conn)
    conn.execute("INSERT INTO hs_known (designation, hs_code) VALUES ('AUTRE', '0000000000')")
    conn.commit()
    conn.close()
    r = await client.post("/nouveau", files=[("fichiers", ("a.pdf", pdf_bytes(MULTILINE_TEXT), "application/pdf"))])
    d = max(int(i) for i in re.findall(r'href="/dossiers/(\d+)"', (await client.get("/")).text))

    await generer(client, d)
    page = (await client.get(f"/dossiers/{d}")).text
    assert "jamais déclaré" in page and 'action="/chassis/code-sh-normal"' in page
    m = re.search(r'name="designation" value="([^"]*)">\s*<input type="hidden" name="hs_code" value="([^"]*)"', page)
    assert m, page
    # un opérateur ne voit pas le bouton
    as_user(OP)
    assert 'action="/chassis/code-sh-normal"' not in (await client.get(f"/dossiers/{d}")).text
    as_user(CHEF)
    r = await client.post("/chassis/code-sh-normal", data={"designation": m.group(1), "hs_code": m.group(2),
                                                           "retour": f"/dossiers/{d}"})
    assert r.status_code == 303 and r.headers["location"] == f"/dossiers/{d}"
    # idempotent ; retour externe ignoré
    r = await client.post("/chassis/code-sh-normal", data={"designation": m.group(1), "hs_code": m.group(2),
                                                           "retour": "https://evil.example/"})
    assert r.status_code == 303 and r.headers["location"].startswith("/chassis")
    page = (await client.get("/chassis")).text
    assert page[page.index("<h2>Codes SH habituels</h2>"):].count(m.group(2)) == 1
    assert page[page.index("Dernières actions"):].count("Code SH habituel") == 1     # une seule fois au journal
    await generer(client, d)
    assert "jamais déclaré" not in (await client.get(f"/dossiers/{d}")).text
    # champs vides : message, pas d'erreur 500
    r = await client.post("/chassis/code-sh-normal", data={"designation": "", "hs_code": ""})
    assert r.status_code == 422
