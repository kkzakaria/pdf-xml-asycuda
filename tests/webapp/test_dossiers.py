"""Cycle d'un dossier : brouillon, génération, déclaration, retour en brouillon."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT  # noqa: E402

from chassis_registry import ChassisRegistry  # noqa: E402
from generation import GenerationSettings  # noqa: E402
from webapp import db  # noqa: E402
from webapp.auth import User  # noqa: E402
from webapp.config import WebappSettings  # noqa: E402
from webapp.dossiers import (DeclarationRefusee, DossierFige, DossierIntrouvable,  # noqa: E402
                             DossierService)

SAMPLE_PDF = ROOT / "OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf"
VINS = ["LC6XCH1G7T1519802", "LC6XCH1G7T1519489", "LK1PCJL85T1050418"]
OTHER_TEXT = MULTILINE_TEXT.replace("RCSA6099999", "RCSA6088888")
OP = User("op@karta.ci", False)
ADMIN = User("chef@karta.ci", True)


def pdf_bytes(text):
    """« PDF » de test : en-tête %PDF puis le texte que l'extracteur factice renvoie."""
    return b"%PDF-1.4\n" + text.encode("utf-8")


@pytest.fixture
def fake_pdf(monkeypatch):
    """Extracteur PDF factice (comme tests/test_generation.py) : le texte est lu dans le fichier."""
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
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "r.db"))


@pytest.fixture
def svc(tmp_path, registry):
    settings = WebappSettings(data_dir=tmp_path / "webapp", registry_path=tmp_path / "r.db",
                              profile_path=ROOT / "profils" / "karta-transit.ini",
                              access_aud="", dev_user="op@karta.ci", default_taux=596.302)
    conn = db.connect(settings.db_path)
    db.init(conn)
    yield DossierService(conn, settings, registry)
    conn.close()


def actions(svc, dossier_id):
    return [r["action"] for r in svc.conn.execute(
        "SELECT action FROM events WHERE dossier_id = ? ORDER BY id", (dossier_id,))]


def status(svc, dossier_id):
    return svc.conn.execute("SELECT status FROM dossiers WHERE id = ?", (dossier_id,)).fetchone()[0]


def latest_summary(svc, dossier_id):
    row = svc.conn.execute("SELECT summary_json FROM generations WHERE dossier_id = ? "
                           "ORDER BY n DESC LIMIT 1", (dossier_id,)).fetchone()
    return json.loads(row[0])


def alert_codes(summary):
    return {a["code"]: a for a in summary["alertes"]}


def gen(svc, dossier_id, **kw):
    s = svc.default_settings(dossier_id)
    for k, v in kw.items():
        setattr(s, k, v)
    return svc.generate(OP, dossier_id, s)


# ------------------------------------------------------------------ création
def test_create_stores_pdf_and_reads_rfcv(svc, fake_pdf, tmp_path):
    d = svc.create(OP, "../RFCV 6099999?.pdf", pdf_bytes(MULTILINE_TEXT))
    row = svc.conn.execute("SELECT * FROM dossiers WHERE id = ?", (d,)).fetchone()
    assert row["rfcv_number"] == "RCSA6099999"
    assert row["status"] == "brouillon" and row["created_by"] == OP.email
    pdf = Path(row["pdf_path"])
    assert pdf.parent == tmp_path / "webapp" / "dossiers" / str(d)
    assert pdf.name == "RFCV_6099999.pdf" and row["filename"] == pdf.name
    assert pdf.read_bytes() == pdf_bytes(MULTILINE_TEXT)


def test_create_rejects_non_pdf(svc):
    with pytest.raises(ValueError, match="PDF"):
        svc.create(OP, "a.pdf", b"<html>pas un pdf</html>")
    assert svc.conn.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0] == 0


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
def test_create_sample_pdf_and_default_settings(svc):
    d = svc.create(OP, SAMPLE_PDF.name, SAMPLE_PDF.read_bytes())
    assert svc.get(d)["rfcv_number"] == "RCSA6013381"
    s = svc.default_settings(d)
    assert s.taux_douane == 596.302
    assert s.takikro is False           # maritime, venu de Chine
    assert s.designation == "MOTO"      # « MOTORCYCLE »
    assert s.profile is not None and s.profile.bureau_code


def test_default_settings_takikro_and_last_taux(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    s = svc.default_settings(d)
    assert s.takikro is True            # « Transport par route », provenance Togo
    assert s.designation == "MOTO"
    assert s.taux_douane == 596.302
    gen(svc, d, taux_douane=600.5)
    d2 = svc.create(OP, "b.pdf", pdf_bytes(OTHER_TEXT))
    assert svc.default_settings(d2).taux_douane == 600.5


def test_unknown_dossier(svc):
    with pytest.raises(DossierIntrouvable):
        svc.default_settings(42)


# ------------------------------------------------------------------ génération
def test_generate_twice_never_registers(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    assert gen(svc, d) == 1
    assert gen(svc, d) == 2
    assert registry.get_all_extracted() == []
    rows = svc.conn.execute("SELECT * FROM generations WHERE dossier_id = ? ORDER BY n", (d,)).fetchall()
    assert [r["n"] for r in rows] == [1, 2]
    assert GenerationSettings.from_dict(json.loads(rows[0]["settings_json"])).takikro is True
    assert json.loads(rows[1]["summary_json"])["vins"] == VINS


def test_files_never_overwritten(svc, fake_pdf, tmp_path):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    base = tmp_path / "webapp" / "dossiers" / str(d)
    first = {p.name: p.read_bytes() for p in (base / "gen-1").iterdir()}
    assert len(first) == 2
    gen(svc, d, designation="TRICYCLE", taux_douane=700.0)
    assert {p.name: p.read_bytes() for p in (base / "gen-1").iterdir()} == first
    assert sorted(p.name for p in (base / "gen-2").iterdir()) == sorted(first)
    # dossier gen-3 laissé sur le disque (arrêt brutal) : jamais réutilisé
    (base / "gen-3").mkdir()
    (base / "gen-3" / "reste.txt").write_text("x")
    assert gen(svc, d) == 4
    assert (base / "gen-3" / "reste.txt").read_text() == "x"
    paths = [r[0] for r in svc.conn.execute("SELECT xml_path FROM generations WHERE dossier_id = ?", (d,))]
    assert len(set(paths)) == 3


def test_generate_unreadable_pdf_sets_error(svc, registry):
    d = svc.create(OP, "casse.pdf", b"%PDF-1.4\nceci n'est pas un vrai PDF")
    assert svc.get(d)["rfcv_number"] is None
    assert svc.generate(OP, d, GenerationSettings(taux_douane=596.302)) is None
    err = svc.get(d)["error"]
    assert err and err.startswith("Échec de la génération")
    assert svc.conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == 0
    assert "generation_echec" in actions(svc, d)


def test_success_clears_error(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    from generation import Amount
    assert gen(svc, d, assurance_mode="imposee", assurance=None) is None
    assert svc.get(d)["error"]
    assert gen(svc, d, assurance_mode="imposee", assurance=Amount(93, True)) == 1
    assert svc.get(d)["error"] is None


def test_other_draft_alert_between_two_dossiers(svc, fake_pdf):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    b = svc.create(OP, "b.pdf", pdf_bytes(OTHER_TEXT))
    gen(svc, a)
    gen(svc, b)
    alert = alert_codes(latest_summary(svc, b))["chassis_autre_brouillon"]
    assert alert["bloquante"] is False
    assert f"RFCV RCSA6099999 (dossier {a})" in alert["message"]


def test_declared_dossier_cannot_be_regenerated(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    with pytest.raises(DossierFige):
        svc.generate(OP, d, GenerationSettings(taux_douane=1.0))
    assert svc.conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0] == 1


# ------------------------------------------------------------------ déclaration
def test_declare_registers_chassis(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    row = svc.get(d)
    assert row["status"] == "declare" and row["declared_by"] == OP.email and row["declared_at"]
    entries = {e["chassis_number"]: e for e in registry.get_all_extracted()}
    assert set(entries) == set(VINS)
    assert {e["rfcv_number"] for e in entries.values()} == {"RCSA6099999"}
    assert {e["filename"] for e in entries.values()} == {"a.pdf"}
    hs = {tuple(r) for r in svc.conn.execute("SELECT designation, hs_code FROM hs_known")}
    assert hs == {("MOTO", "87112099")}
    with pytest.raises(DossierFige):
        svc.declare(OP, d)


def test_declare_requires_generation(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    with pytest.raises(DeclarationRefusee):
        svc.declare(OP, d)
    assert status(svc, d) == "brouillon"


def test_declare_refuses_chassis_declared_by_other_dossier(svc, fake_pdf, registry):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    b = svc.create(OP, "b.pdf", pdf_bytes(OTHER_TEXT))
    gen(svc, a)
    gen(svc, b)                         # pas encore déclaré : simple avertissement
    assert not any(x["bloquante"] for x in latest_summary(svc, b)["alertes"])
    svc.declare(OP, a)
    # le registre a changé depuis la génération de b : contrôle refait à la déclaration
    with pytest.raises(DeclarationRefusee) as exc:
        svc.declare(OP, b)
    assert "RCSA6099999" in str(exc.value)
    assert {c["chassis_number"] for c in exc.value.conflicts} == set(VINS)
    assert {c["rfcv_number"] for c in exc.value.conflicts} == {"RCSA6099999"}
    assert status(svc, b) == "brouillon"
    assert {e["rfcv_number"] for e in registry.get_all_extracted()} == {"RCSA6099999"}
    # régénéré : l'alerte bloquante refuse aussi la déclaration
    gen(svc, b)
    assert alert_codes(latest_summary(svc, b))["chassis_declares"]["bloquante"] is True
    with pytest.raises(DeclarationRefusee):
        svc.declare(OP, b)


def test_declare_rolls_back_on_partial_write(svc, fake_pdf, registry, monkeypatch):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    original = registry.register_extracted
    calls = []

    def flaky(chassis, *args, **kwargs):
        calls.append(chassis)
        if len(calls) == 3:
            raise OSError("disque plein")
        return original(chassis, *args, **kwargs)

    monkeypatch.setattr(registry, "register_extracted", flaky)
    with pytest.raises(OSError):
        svc.declare(OP, d)
    assert registry.get_all_extracted() == []
    assert status(svc, d) == "brouillon"


# ------------------------------------------------------------------ retour en brouillon
def test_revert_to_draft_admin_only_and_frees_chassis(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    with pytest.raises(PermissionError):
        svc.revert_to_draft(OP, d)
    assert status(svc, d) == "declare"
    # un VIN réattribué entre-temps à un autre RFCV n'est pas retiré
    registry.register_extracted(VINS[0], "autre.pdf", "RCSA6000001", overwrite=True)
    svc.revert_to_draft(ADMIN, d)
    assert status(svc, d) == "brouillon"
    left = registry.get_all_extracted()
    assert [(e["chassis_number"], e["rfcv_number"]) for e in left] == [(VINS[0], "RCSA6000001")]
    assert gen(svc, d) == 2             # de nouveau modifiable


# ------------------------------------------------------------------ journal et liste
def test_events_logged(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    svc.revert_to_draft(ADMIN, d)
    assert actions(svc, d) == ["creation", "generation", "declaration", "retour_brouillon"]
    rows = svc.conn.execute("SELECT email, detail, at FROM events WHERE dossier_id = ? ORDER BY id",
                            (d,)).fetchall()
    assert [r["email"] for r in rows] == [OP.email, OP.email, OP.email, ADMIN.email]
    assert all(r["at"] for r in rows)


def test_list_and_search(svc, fake_pdf):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    b = svc.create(OP, "b.pdf", pdf_bytes(OTHER_TEXT.replace("LK1PCJL85T1050418", "ZZZ00000000000001")))
    gen(svc, a)
    rows = svc.list(None)
    assert [r["id"] for r in rows] == [b, a]
    ra = rows[1]
    assert ra["nb_articles"] == 3 and ra["fob_total"] == 100000 and ra["devise"] == "XOF"
    assert rows[0]["nb_articles"] is None
    assert set(ra) >= {"id", "rfcv_number", "filename", "status", "created_by", "created_at",
                       "declared_at", "error", "nb_articles", "fob_total", "devise"}
    assert [r["id"] for r in svc.list("6099999")] == [a]
    assert [r["id"] for r in svc.list("rcsa 6088888")] == [b]
    assert [r["id"] for r in svc.list("lk1pcjl85t1050418")] == [a]
    assert svc.list("ZZZ00000000000001") == []          # b jamais généré
    gen(svc, b)
    assert [r["id"] for r in svc.list("ZZZ00000000000001")] == [b]
