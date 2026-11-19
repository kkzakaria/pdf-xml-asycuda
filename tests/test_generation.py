"""generate() en brouillon et résumé structuré d'une génération."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT, parse_text

from chassis_registry import ChassisRegistry
from company_profile import CompanyProfile
from corps_generator import generate_corps
from generation import Amount, GenerationSettings, generate
from generation_summary import Alert, Summary, summarize
from xml_generator import XMLGenerator

SAMPLE_PDF = ROOT / "OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf"
VIN1 = "LC6XCH1G7T1519802"


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


@pytest.fixture
def fake_pdf(monkeypatch, tmp_path):
    """Remplace l'extracteur PDF : generate() lit MULTILINE_TEXT (ou le texte fixé)."""
    import rfcv_parser

    state = {"text": MULTILINE_TEXT}

    class FakeExtractor:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return state["text"]

        def extract_all_tables(self):
            return []

    monkeypatch.setattr(rfcv_parser, "PDFExtractor", FakeExtractor)
    state["path"] = tmp_path / "rfcv.pdf"
    return state


def corps_of(rfcv_data):
    gen = XMLGenerator(rfcv_data)
    gen.generate()
    return generate_corps(gen.root, xml_name="test.xml")


def build(registry, tmp_path, **kwargs):
    """(données finales, référence, corps) à partir de MULTILINE_TEXT."""
    ref = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0)
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0, **kwargs)
    return data, ref


def codes(summary):
    return {a.code: a for a in summary.alertes}


# ------------------------------------------------------------------ generate()
@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
def test_generate_matches_cli_output_with_imposed_values(tmp_path, monkeypatch):
    """Spéc. §5.7 : mêmes réglages (FOB uniforme, fret et assurance imposés, désignation) en CLI."""
    import converter
    import rfcv_parser

    cli_registry = ChassisRegistry(str(tmp_path / "cli.db"))
    monkeypatch.setattr(rfcv_parser, "get_registry", lambda: cli_registry)
    cli_xml = tmp_path / "cli" / "dossier.xml"
    assert converter.convert_pdf_to_xml(str(SAMPLE_PDF), str(cli_xml), taux_douane=576.42, corps=True,
                                        fob_revise=12345.5, fob_mode="uniforme", fret_impose=987.25,
                                        assurance_imposee=45678, designation="MOTO", banque="SGBC")

    registry = ChassisRegistry(str(tmp_path / "web.db"))
    settings = GenerationSettings(taux_douane=576.42, fob_revise=Amount(12345.5), fob_mode="uniforme",
                                  fret=Amount(987.25), assurance_mode="imposee", assurance=Amount(45678),
                                  designation="MOTO", banque="SGBC")
    res = generate(SAMPLE_PDF, settings, tmp_path / "web", "dossier", registry)
    assert res.xml_path.read_bytes() == cli_xml.read_bytes()
    assert res.corps_path.read_bytes() == (cli_xml.parent / "corps_dossier.txt").read_bytes()
    assert b"MOTO" in res.xml_path.read_bytes()
    assert res.summary.cases["Fcx_28b"] == "SGBC"                 # --banque sans profil
    assert res.summary.fret_total == pytest.approx(987.25)
    assert res.summary.assurance_total == pytest.approx(45678)


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
def test_generate_matches_cli_output(tmp_path, monkeypatch):
    import converter
    import rfcv_parser

    cli_registry = ChassisRegistry(str(tmp_path / "cli.db"))
    monkeypatch.setattr(rfcv_parser, "get_registry", lambda: cli_registry)
    cli_xml = tmp_path / "cli" / "dossier.xml"
    assert converter.convert_pdf_to_xml(str(SAMPLE_PDF), str(cli_xml), taux_douane=576.42,
                                        takikro=True, disp=True, corps=True)

    registry = ChassisRegistry(str(tmp_path / "web.db"))
    settings = GenerationSettings(taux_douane=576.42, takikro=True, disp=True)
    res = generate(SAMPLE_PDF, settings, tmp_path / "web", "dossier", registry)

    assert res.xml_path == tmp_path / "web" / "dossier.xml"
    assert res.corps_path == tmp_path / "web" / "corps_dossier.txt"
    assert res.xml_path.read_bytes() == cli_xml.read_bytes()
    assert res.corps_path.read_bytes() == (cli_xml.parent / "corps_dossier.txt").read_bytes()
    assert registry.get_all_extracted() == []
    assert res.summary.cases["Fcx_Aa"] == "CITKK"
    assert res.summary.cases["Fcx_28b"] == "DISP"
    assert res.summary.nb_articles == 1  # articles sans châssis regroupés
    # désignation brute « MOTORCYCLE » : alerte non bloquante
    assert codes(res.summary)["designation"].bloquante is False


def test_generate_never_writes_registry(registry, fake_pdf, tmp_path):
    settings = GenerationSettings(taux_douane=1.0, fob_revise=Amount(150000), fob_mode="uniforme")
    res = generate(fake_pdf["path"], settings, tmp_path / "out", "d1", registry)
    assert res.xml_path.exists() and res.corps_path.exists()
    assert registry.get_all_extracted() == []
    assert registry.get_all_generated() == []
    assert res.summary.vins == [VIN1, "LC6XCH1G7T1519489", "LK1PCJL85T1050418"]
    assert res.summary.nb_vin == 3


def test_settings_roundtrip_dict():
    s = GenerationSettings(
        taux_douane=576.42, profile=CompanyProfile(bureau_code="CIAB6", declarant_nom="KARTA"),
        dossier="123", manifeste="M1", nationalite_transport="TG", rapport_paiement="25P2003J",
        takikro=True, disp=True, banque="SGBC", fob_revise=Amount(5400, True), fob_mode="uniforme",
        fret=Amount(2000, True), assurance_mode="imposee", assurance=Amount(93, True), designation="MOTO")
    d = json.loads(json.dumps(s.to_dict()))
    assert GenerationSettings.from_dict(d) == s
    assert GenerationSettings.from_dict(GenerationSettings(taux_douane=1.0).to_dict()) == \
        GenerationSettings(taux_douane=1.0)


def test_per_article_amounts(registry, fake_pdf, tmp_path):
    settings = GenerationSettings(taux_douane=1.0, assurance_mode="imposee", assurance=Amount(93, True),
                                  fret=Amount(2000, True))
    s = generate(fake_pdf["path"], settings, tmp_path / "out", "d", registry).summary
    assert s.assurance_total == 279
    assert s.fret_total == 6000
    assert s.valeurs_articles["assurance"] == [(93.0, 3)]
    assert s.valeurs_articles["fret"] == [(2000.0, 3)]


def test_imposee_without_amount_is_error(registry, fake_pdf, tmp_path):
    with pytest.raises(ValueError):
        generate(fake_pdf["path"], GenerationSettings(taux_douane=1.0, assurance_mode="imposee"),
                 tmp_path / "out", "d", registry)


def test_generate_applies_designation(registry, fake_pdf, tmp_path):
    settings = GenerationSettings(taux_douane=1.0, designation="TRICYCLE")
    res = generate(fake_pdf["path"], settings, tmp_path / "out", "d", registry)
    assert res.summary.designation == "TRICYCLE"
    assert "ITEM.1.Ftx_31b1=TRICYCLE" in res.corps_path.read_text(encoding="utf-8")


def test_summary_json_roundtrip(registry, fake_pdf, tmp_path):
    settings = GenerationSettings(taux_douane=1.0, fob_revise=Amount(150000))
    s = generate(fake_pdf["path"], settings, tmp_path / "out", "d", registry).summary
    assert s.alertes  # fob_heterogene au moins
    assert Summary.from_dict(json.loads(json.dumps(s.to_dict()))) == s


# ------------------------------------------------------------------ summarize()
def test_summary_totals_and_cases(registry, tmp_path):
    data, ref = build(registry, tmp_path)
    s = summarize(data, ref, corps_of(data), [], {}, None)
    assert s.rfcv_number == "RCSA6099999"
    assert (s.nb_articles, s.nb_vin, s.colis) == (3, 3, 3)
    assert s.fob_total == 100000 and s.fret_total == 3000
    assert s.valeurs_articles["fob"] == [(33333.33, 2), (33333.34, 1)]
    assert s.poids_brut == 35 and s.poids_net == 30
    assert s.cases["Fcx_31f"] == "CT"
    assert set(s.cases) == {"Fcx_Aa", "Fcx_29a", "Fcx_10", "Fcx_18b", "Fcx_28b", "Fcx_31f", "Fld_40"}
    assert s.codes_sh == ["87112099"]
    assert s.ecarts == [] and s.alertes == []


def test_summary_mixed_fob_alert(registry, tmp_path):
    data, ref = build(registry, tmp_path, fob_revise=150000)
    a = codes(summarize(data, ref, corps_of(data), [], {}, None))["fob_heterogene"]
    assert a.bloquante is False and "prorata" in a.message
    data, ref = build(registry, tmp_path)  # sans révision : pas d'alerte
    assert "fob_heterogene" not in codes(summarize(data, ref, corps_of(data), [], {}, None))


def test_summary_conflict_alert_is_blocking(registry, tmp_path):
    data, ref = build(registry, tmp_path)
    conflicts = [{"chassis_number": VIN1, "first_seen_date": "2026-11-01", "first_filename": "a.pdf",
                  "first_rfcv_number": "RCSA6000001"},
                 {"chassis_number": "LK1PCJL85T1050418", "first_seen_date": "2026-11-01",
                  "first_filename": "a.pdf", "first_rfcv_number": "RCSA6000001"}]
    a = codes(summarize(data, ref, corps_of(data), conflicts, {}, None))["chassis_declares"]
    assert a.bloquante is True
    assert "RCSA6000001" in a.message and "2" in a.message


def test_summary_other_draft_alert(registry, tmp_path):
    data, ref = build(registry, tmp_path)
    other = {"Dossier 6014621": {VIN1, "AUTREVIN"}, "Dossier 9": {"XXX"}}
    a = codes(summarize(data, ref, corps_of(data), [], other, None))["chassis_autre_brouillon"]
    assert a.bloquante is False
    assert "Dossier 6014621" in a.message and "Dossier 9" not in a.message and "1" in a.message


def test_summary_colis_and_sum_alerts(registry, tmp_path):
    data, ref = build(registry, tmp_path)
    data.items[0].tarification.item_price += 10
    data.property.total_packages = 0
    al = codes(summarize(data, ref, corps_of(data), [], {}, None))
    assert al["somme_articles"].bloquante is True
    assert al["colis_zero"].bloquante is False


def test_summary_designation_and_hs_alerts(registry, tmp_path):
    data, ref = build(registry, tmp_path)
    for it in data.items:
        it.packages.marks1 = "TRICYLE-APSONIC-"
    al = codes(summarize(data, ref, corps_of(data), [], {}, {("MOTO", "87112099")}))
    assert "TRICYCLE" in al["designation"].message and al["designation"].bloquante is False
    assert al["code_sh_inhabituel"].bloquante is False
    # registre vide (None) : pas d'alerte de code SH
    assert "code_sh_inhabituel" not in codes(summarize(data, ref, corps_of(data), [], {}, None))


def test_summary_ecarts(registry, tmp_path):
    data, ref = build(registry, tmp_path, fob_revise=150000, assurance_imposee=5000)
    from designation import apply_designation
    apply_designation(data, "TRICYCLE")
    ecarts = summarize(data, ref, corps_of(data), [], {}, None).ecarts
    assert len(ecarts) == 3
    assert any("FOB" in e and "100 000 → 150 000" in e for e in ecarts)
    assert any("ssurance" in e and "→ 5 000" in e for e in ecarts)
    assert any("MOTO → TRICYCLE" in e for e in ecarts)


def test_alert_dict_roundtrip():
    a = Alert("colis_zero", "msg", False)
    assert Alert.from_dict(a.to_dict()) == a


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
def test_fret_per_article_in_rfcv_currency(registry, tmp_path):
    # taux ≠ 1 : le fret par article reste dans la devise du RFCV (USD), comme la saisie
    settings = GenerationSettings(taux_douane=576.42, fret=Amount(2000, True))
    s = generate(SAMPLE_PDF, settings, tmp_path / "out", "d", registry).summary
    assert s.devise == "USD"
    assert s.fret_total == 2000 * s.nb_articles
    assert s.valeurs_articles["fret"] == [(2000.0, s.nb_articles)]
    assert s.valeurs_articles["fob"] == [(12683.65, 1)]


def test_generate_requires_registry(fake_pdf, tmp_path):
    with pytest.raises(ValueError, match="egistre"):
        generate(fake_pdf["path"], GenerationSettings(taux_douane=1.0), tmp_path / "out", "d", None)


def test_summary_from_dict_tolerates_unknown_and_missing_keys():
    s = Summary.from_dict({"rfcv_number": "RCSA1", "nb_articles": 2, "champ_futur": 1})
    assert s.rfcv_number == "RCSA1" and s.nb_articles == 2
    assert s.devise is None and s.alertes == [] and s.valeurs_articles == {}


# ------------------------------------------------------------------ CLI (spéc. §5.7)
def _run_cli(monkeypatch, *argv):
    import converter
    monkeypatch.setattr(sys, "argv", ["converter.py", *argv])
    with pytest.raises(SystemExit) as exc:
        converter.main()
    return exc.value.code


def test_cli_passes_new_settings(monkeypatch, tmp_path):
    import converter
    seen = {}
    monkeypatch.setattr(converter, "convert_pdf_to_xml", lambda *a, **kw: seen.update(kw) or True)
    code = _run_cli(monkeypatch, "a.pdf", "--taux-douane", "596.302", "--fob-revise", "1000",
                    "--fob-mode", "uniforme", "--fret-impose", "250.5", "--assurance-imposee", "30000",
                    "--designation", "TRICYCLE")
    assert code == 0
    assert (seen["fob_revise"], seen["fob_mode"], seen["fret_impose"], seen["assurance_imposee"],
            seen["designation"]) == (1000.0, "uniforme", 250.5, 30000.0, "TRICYCLE")


@pytest.mark.parametrize("option", [["--fob-mode", "uniforme"], ["--fret-impose", "10"],
                                    ["--assurance-imposee", "10"], ["--designation", "MOTO"]])
def test_cli_batch_rejects_single_file_settings(monkeypatch, tmp_path, capsys, option):
    import converter
    monkeypatch.setattr(converter, "BatchProcessor", lambda *a, **kw: pytest.fail("batch lancé"))
    assert _run_cli(monkeypatch, "a.pdf", "b.pdf", "--taux-douane", "596.302", *option) == 1
    assert "propres à un fichier" in capsys.readouterr().err


def test_cli_fob_mode_requires_fob_revise_and_positive_amounts(monkeypatch, capsys):
    import converter
    monkeypatch.setattr(converter, "convert_pdf_to_xml", lambda *a, **kw: pytest.fail("conversion lancée"))
    assert _run_cli(monkeypatch, "a.pdf", "--taux-douane", "1", "--fob-mode", "uniforme") == 1
    assert "--fob-revise" in capsys.readouterr().err
    assert _run_cli(monkeypatch, "a.pdf", "--taux-douane", "1", "--fret-impose", "0") == 1
    assert "strictement positif" in capsys.readouterr().err


def test_chassis_of_same_rfcv_not_blocking(registry, fake_pdf, tmp_path):
    """VIN déjà enregistrés sous le RFCV généré (reprise) : note informative, pas de blocage."""
    registry.register_extracted(VIN1, "a.pdf", "6099999")           # même RFCV, autre écriture
    registry.register_extracted("LC6XCH1G7T1519489", "a.pdf", "RCSA6099999")
    res = generate(fake_pdf["path"], GenerationSettings(taux_douane=1.0), tmp_path / "out", "d", registry)
    alertes = codes(res.summary)
    assert "chassis_declares" not in alertes
    assert alertes["chassis_meme_rfcv"].bloquante is False
    assert "2 châssis" in alertes["chassis_meme_rfcv"].message
    assert not any(a.bloquante for a in res.summary.alertes if a.code.startswith("chassis"))


def test_chassis_of_other_rfcv_still_blocking(registry, fake_pdf, tmp_path):
    registry.register_extracted(VIN1, "a.pdf", "RCSA6099999")
    registry.register_extracted("LK1PCJL85T1050418", "b.pdf", "RCSA6088888")
    res = generate(fake_pdf["path"], GenerationSettings(taux_douane=1.0), tmp_path / "out", "d", registry)
    alerte = codes(res.summary)["chassis_declares"]
    assert alerte.bloquante is True
    assert alerte.message.startswith("1 châssis") and "RCSA6088888" in alerte.message
    assert "RCSA6099999" not in alerte.message
