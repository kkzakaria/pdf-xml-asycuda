"""Cycle d'un dossier : brouillon, génération, déclaration, retour en brouillon."""
import json
import sqlite3
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


def test_declare_after_crash_with_own_chassis_registered(svc, fake_pdf, registry):
    """VIN déjà dans le registre sous le RFCV du dossier (crash, CLI) : pas de blocage."""
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    for vin in VINS:
        registry.register_extracted(vin, "a.pdf", "RCSA6099999")
    gen(svc, d)
    summary = latest_summary(svc, d)
    assert not any(a["bloquante"] for a in summary["alertes"])
    assert alert_codes(summary)["chassis_meme_rfcv"]["bloquante"] is False
    svc.declare(OP, d)
    assert status(svc, d) == "declare"
    assert {e["rfcv_number"] for e in registry.get_all_extracted()} == {"RCSA6099999"}


def test_declare_still_blocked_by_chassis_of_other_rfcv(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    registry.register_extracted(VINS[0], "b.pdf", "RCSA6088888")
    gen(svc, d)
    assert alert_codes(latest_summary(svc, d))["chassis_declares"]["bloquante"] is True
    with pytest.raises(DeclarationRefusee):
        svc.declare(OP, d)
    assert status(svc, d) == "brouillon"


NO_RFCV_TEXT = MULTILINE_TEXT.replace("RCSA6099999", "XXXA6099999")


def test_declare_refused_without_rfcv_number(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(NO_RFCV_TEXT))
    assert svc.get(d)["rfcv_number"] in (None, "")
    gen(svc, d)
    summary = latest_summary(svc, d)
    assert summary["vins"] == VINS and not summary["rfcv_number"]
    with pytest.raises(DeclarationRefusee) as exc:
        svc.declare(OP, d)
    assert "N° RFCV illisible" in str(exc.value)
    assert status(svc, d) == "brouillon"
    assert registry.get_all_extracted() == []
    assert "declaration_refusee" in actions(svc, d)


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
    # case 22 arrondie à l'unité par défaut : 3 × 33 334 (FOB attestés 33 333,34 / 33 333,33)
    assert ra["nb_articles"] == 3 and ra["fob_total"] == 100002 and ra["devise"] == "XOF"
    assert rows[0]["nb_articles"] is None
    assert set(ra) >= {"id", "rfcv_number", "filename", "status", "created_by", "created_at",
                       "declared_at", "error", "nb_articles", "fob_total", "devise"}
    assert [r["id"] for r in svc.list("6099999")] == [a]
    assert [r["id"] for r in svc.list("rcsa 6088888")] == [b]
    assert [r["id"] for r in svc.list("lk1pcjl85t1050418")] == [a]
    assert svc.list("ZZZ00000000000001") == []          # b jamais généré
    gen(svc, b)
    assert [r["id"] for r in svc.list("ZZZ00000000000001")] == [b]


# ------------------------------------------------------------------ corrections (revue, tour 1)
def test_failed_create_leaves_no_folder_and_next_create_works(svc, fake_pdf, tmp_path, monkeypatch):
    original = svc._event

    def boom(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(svc, "_event", boom)
    with pytest.raises(sqlite3.OperationalError):
        svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    root = tmp_path / "webapp" / "dossiers"
    assert list(root.iterdir()) == []
    assert svc.conn.execute("SELECT COUNT(*) FROM dossiers").fetchone()[0] == 0
    monkeypatch.setattr(svc, "_event", original)
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    assert Path(svc.get(d)["pdf_path"]).read_bytes() == pdf_bytes(MULTILINE_TEXT)


def test_create_sets_aside_orphan_folder(svc, fake_pdf, tmp_path):
    root = tmp_path / "webapp" / "dossiers"
    (root / "1").mkdir(parents=True)
    (root / "1" / "ancien.pdf").write_bytes(b"%PDF ancien")
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    assert d == 1
    assert sorted(p.name for p in (root / "1").iterdir()) == ["a.pdf"]
    orphans = [p for p in root.iterdir() if p.name.startswith("1.orphelin-")]
    assert len(orphans) == 1 and (orphans[0] / "ancien.pdf").read_bytes() == b"%PDF ancien"


def test_one_rfcv_one_declaration(svc, fake_pdf, registry):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    b = svc.create(OP, "a-bis.pdf", pdf_bytes(MULTILINE_TEXT))   # même RFCV déposé deux fois
    gen(svc, a)
    gen(svc, b)
    svc.declare(OP, a)
    with pytest.raises(DeclarationRefusee) as exc:
        svc.declare(OP, b)
    assert f"dossier {a}" in str(exc.value) and "RCSA6099999" in str(exc.value)
    assert status(svc, b) == "brouillon"
    svc.revert_to_draft(ADMIN, a)
    assert registry.get_all_extracted() == []
    svc.declare(OP, b)
    assert status(svc, b) == "declare"
    assert {e["chassis_number"] for e in registry.get_all_extracted()} == set(VINS)
    assert {e["filename"] for e in registry.get_all_extracted()} == {"a-bis.pdf"}


# ------------------------------------------------------------------ revue finale
def _other_writer_can_write(svc):
    """Un autre écrivain obtient le verrou d'écriture immédiatement (aucune attente)."""
    other = sqlite3.connect(svc.settings.db_path, timeout=0)
    try:
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        other.close()


def test_create_reads_pdf_outside_write_transaction(svc, fake_pdf, monkeypatch):
    import webapp.dossiers as dossiers_mod
    original = dossiers_mod._pdf_text
    seen = []

    def spy(path):
        seen.append((svc.conn.in_transaction, _other_writer_can_write(svc)))
        return original(path)

    monkeypatch.setattr(dossiers_mod, "_pdf_text", spy)
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    assert seen == [(False, True)]
    row = svc.get(d)
    assert row["rfcv_number"] == "RCSA6099999"
    assert Path(row["pdf_path"]).read_bytes() == pdf_bytes(MULTILINE_TEXT)
    assert Path(row["pdf_path"]).parent.name == str(d)
    staging = Path(svc.settings.data_dir) / "depots-en-cours"
    assert not staging.exists() or list(staging.iterdir()) == []


def test_generate_retries_when_generation_folder_taken(svc, fake_pdf, monkeypatch):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    original = svc._next_n
    calls = []

    def racing(dossier_id, folder):
        n = original(dossier_id, folder)
        if not calls:                    # une requête concurrente prend gen-1 juste après
            (folder / f"gen-{n}").mkdir(parents=True)
        calls.append(n)
        return n

    monkeypatch.setattr(svc, "_next_n", racing)
    assert gen(svc, d) == 2
    assert calls == [1, 2]


def test_generation_discarded_if_declared_meanwhile(svc, fake_pdf, tmp_path, monkeypatch):
    import webapp.dossiers as dossiers_mod
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    assert gen(svc, d) == 1
    original = dossiers_mod.generate_drafts

    def slow(*args, **kwargs):
        result = original(*args, **kwargs)
        other = sqlite3.connect(svc.settings.db_path)     # déclaration concurrente
        other.execute("UPDATE dossiers SET status = 'declare' WHERE id = ?", (d,))
        other.commit()
        other.close()
        return result

    monkeypatch.setattr(dossiers_mod, "generate_drafts", slow)
    assert gen(svc, d) is None
    assert [g["n"] for g in svc.generations(d)] == [1]
    assert not (tmp_path / "webapp" / "dossiers" / str(d) / "gen-2").exists()
    assert "déclaré" in svc.get(d)["error"]
    assert "generation_abandonnee" in actions(svc, d)


def test_declare_records_declared_n_and_revert_clears_it(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    gen(svc, d)
    svc.declare(OP, d)
    assert svc.get(d)["declared_n"] == 2
    svc.revert_to_draft(ADMIN, d)
    assert svc.get(d)["declared_n"] is None


def test_declare_refused_after_failed_generation(svc, fake_pdf):
    from generation import Amount
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    assert gen(svc, d, assurance_mode="imposee", assurance=None) is None
    with pytest.raises(DeclarationRefusee, match="dernière génération a échoué"):
        svc.declare(OP, d)
    assert status(svc, d) == "brouillon"
    assert gen(svc, d, assurance_mode="imposee", assurance=Amount(93, True)) == 2
    svc.declare(OP, d)


# ------------------------------------------------------------------ abandon
def test_abandon_by_creator_or_admin_only_from_draft(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    with pytest.raises(PermissionError):
        svc.abandon(User("autre@karta.ci", False), d)
    assert status(svc, d) == "brouillon"
    svc.abandon(OP, d)
    assert status(svc, d) == "abandonne"
    assert actions(svc, d)[-1] == "abandon"
    with pytest.raises(DossierFige):
        svc.abandon(OP, d)
    with pytest.raises(DossierFige):
        gen(svc, d)
    with pytest.raises(DossierFige):
        svc.declare(OP, d)
    # un administrateur peut abandonner le brouillon d'un autre ; un dossier déclaré, non
    d2 = svc.create(OP, "b.pdf", pdf_bytes(OTHER_TEXT))
    svc.abandon(ADMIN, d2)
    assert status(svc, d2) == "abandonne"
    d3 = svc.create(OP, "c.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d3)
    svc.declare(OP, d3)
    with pytest.raises(DossierFige):
        svc.abandon(ADMIN, d3)
    assert status(svc, d3) == "declare"


def test_reopen_admin_only(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    with pytest.raises(ValueError):
        svc.reopen(ADMIN, d)                        # pas abandonné
    svc.abandon(OP, d)
    with pytest.raises(PermissionError):
        svc.reopen(OP, d)
    svc.reopen(ADMIN, d)
    assert status(svc, d) == "brouillon"
    assert actions(svc, d)[-2:] == ["abandon", "reouverture"]
    assert gen(svc, d) == 1


def test_abandoned_draft_excluded_from_other_draft_alert_but_listed(svc, fake_pdf):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    b = svc.create(OP, "b.pdf", pdf_bytes(MULTILINE_TEXT))     # dépôt en double
    gen(svc, a)
    gen(svc, b)
    assert "chassis_autre_brouillon" in alert_codes(latest_summary(svc, b))
    svc.abandon(OP, a)
    gen(svc, b)
    assert "chassis_autre_brouillon" not in alert_codes(latest_summary(svc, b))
    assert {r["id"]: r["status"] for r in svc.list("6099999")} == {a: "abandonne", b: "brouillon"}


# ------------------------------------------------------------------ annulation : réparation
def test_cancel_rfcv_repairs_after_registry_only_cancel(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    registry.cancel_rfcv("RCSA6099999", "éclaté")        # base SQLite non validée (panne)
    assert status(svc, d) == "declare"
    assert svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté") == []
    assert status(svc, d) == "annule"
    with pytest.raises(ValueError, match="aucun châssis"):
        svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté")   # plus rien à réparer
    with pytest.raises(ValueError, match="aucun châssis"):
        svc.cancel_rfcv(ADMIN, "RCSA6012345", "inconnu")


def test_restore_rfcv_repairs_after_registry_only_restore(svc, fake_pdf, registry):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté")
    registry.restore_rfcv("RCSA6099999")                  # base SQLite non validée (panne)
    assert status(svc, d) == "annule"
    result = svc.restore_rfcv(ADMIN, "RCSA6099999")
    assert result["dossiers_restaures"] == [d]
    assert status(svc, d) == "declare"
    with pytest.raises(ValueError, match="aucun châssis annulé"):
        svc.restore_rfcv(ADMIN, "RCSA6099999")


def test_cancel_rfcv_rolls_back_sqlite_on_failure(svc, fake_pdf, registry, monkeypatch):
    a = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, a)
    svc.declare(OP, a)
    original = svc._event

    def boom(dossier_id, *args, **kwargs):
        if dossier_id is None:
            raise sqlite3.OperationalError("database is locked")
        return original(dossier_id, *args, **kwargs)

    monkeypatch.setattr(svc, "_event", boom)
    with pytest.raises(sqlite3.OperationalError):
        svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté")
    assert not svc.conn.in_transaction
    assert status(svc, a) == "declare"
    monkeypatch.setattr(svc, "_event", original)
    svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté")       # reprise : réparation
    assert status(svc, a) == "annule"


# ------------------------------------------------------------------ historique
def test_events_listing(svc, fake_pdf):
    d = svc.create(OP, "a.pdf", pdf_bytes(MULTILINE_TEXT))
    gen(svc, d)
    svc.declare(OP, d)
    svc.cancel_rfcv(ADMIN, "RCSA6099999", "éclaté")
    events = svc.events(d)
    assert [e["action"] for e in events] == ["rfcv_annule", "declaration", "generation", "creation"]
    assert set(events[0]) >= {"at", "email", "action", "detail"}
    globaux = svc.recent_events()
    assert [e["action"] for e in globaux] == ["rfcv_annule"]
    assert "6099999" in globaux[0]["detail"]
