"""
Case 22 : FOB arrondi par défaut à l'unité de la devise, comme les déclarations de production
Karta (en attendant une décision de la direction) ; --fob-exact rétablit le montant exact.

Règle relevée sur les déclarations de production (voir CLAUDE.md) :
  - arrondi À L'UNITÉ SUPÉRIEURE (plafond), article par article
    (31287 : 68,01 USD par article -> 69 ; 31917 : 9 569,67 -> 9 570) ;
  - total case 22 = Σ des articles arrondis (31287 : 215 × 69 = 14 835, et non ⌈14 622,15⌉) ;
  - montants nationaux, assurance par formule, CIF et valeur statistique recalculés sur les
    montants arrondis ; montants entiers inchangés.

Textes RFCV fictifs.
"""
import math
import sys
from pathlib import Path
from xml.etree.ElementTree import tostring  # XML produit par le test lui-même

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_ecarts_karta_31917 import LEGACY_TEXT
from test_rfcv_format_2026 import MULTILINE_TEXT, generate_xml, parse_text

from chassis_registry import ChassisRegistry
from rfcv_parser import RFCVParser

RATE = 596.302


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


def legacy_text(fob1: str, fob2: str, total: str) -> str:
    """RFCV historique fictif (USD), deux articles de codes SH différents (non regroupés)."""
    return (LEGACY_TEXT
            .replace("1 000,00 200,00", f"{total} 200,00")
            .replace("8414.90.10.00 800,00 962,40", f"8414.90.10.00 {fob1} 962,40")
            .replace("8711.20.90.00 200,00 240,60", f"8711.20.90.00 {fob2} 240,60"))


def prices(data):
    return [i.tarification.item_price for i in data.items]


def formula(fob, freight, rate):
    return math.ceil(2500 + (fob + freight) * rate * 0.0015)


# ------------------------------------------------------------------ règle d'arrondi
@pytest.mark.parametrize("value, expected", [
    (68.01, 69.0),        # 31287 : plafond, pas l'entier le plus proche (68)
    (9569.67, 9570.0),    # 31917
    (10.5, 11.0),
    (10.49, 11.0),
    (43101.0, 43101.0),   # entier inchangé
    (0.0, 0.0),
    (33333.34, 33334.0),
])
def test_round_up_to_unit(value, expected):
    assert RFCVParser._fob_unit(value) == expected


def test_round_up_ignores_float_noise():
    # 0,1 + 0,2 = 0,30000000000000004 : 0,30 au centime, arrondi à 1 ; 3,0000000001 reste 3
    assert RFCVParser._fob_unit(0.1 + 0.2) == 1.0
    assert RFCVParser._fob_unit(3.0000000001) == 3.0


# ------------------------------------------------------------------ format historique
def test_legacy_fractional_articles_rounded_up_total_is_sum(registry, tmp_path):
    # 800,01 + 199,99 = 1 000,00 (case 19) -> 801 + 200 = 1 001 (Σ articles, comme 31287)
    data = parse_text(legacy_text("800,01", "199,99", "1 000,00"), registry, tmp_path,
                      register_chassis=False, taux_douane=RATE)
    assert sorted(prices(data)) == [200.0, 801.0]
    val = data.valuation
    assert val.total_invoice == 1001.0
    assert val.invoice.amount_foreign == 1001.0
    assert val.invoice.amount_national == round(1001 * RATE)
    # assurance par formule recalculée sur le FOB arrondi
    assert val.insurance.amount_national == formula(1001, 200, RATE)
    for item in data.items:
        p = item.tarification.item_price
        vi = item.valuation_item
        assert vi.invoice.amount_foreign == p
        assert vi.invoice.amount_national == round(p * RATE)
        assert vi.total_cif == vi.invoice.amount_national + vi.total_cost
        assert vi.statistical_value == vi.total_cif
    assert val.total_cif == sum(i.valuation_item.total_cif for i in data.items)


def test_legacy_xml_case_22(registry, tmp_path):
    data = parse_text(legacy_text("800,01", "199,99", "1 000,00"), registry, tmp_path,
                      register_chassis=False, taux_douane=RATE)
    root = generate_xml(data)
    assert root.findtext("Valuation/Total/Total_invoice") == "1001.0"
    assert root.findtext("Valuation/Gs_Invoice/Amount_foreign_currency") == "1001.0"
    assert sorted(i.findtext("Tarification/Item_price") for i in root.findall("Item")) == ["200.0", "801.0"]
    assert sorted(i.findtext("Valuation_item/Item_Invoice/Amount_foreign_currency")
                  for i in root.findall("Item")) == ["200.0", "801.0"]


def test_legacy_integers_unchanged(registry, tmp_path):
    exact = parse_text(LEGACY_TEXT, registry, tmp_path, register_chassis=False, taux_douane=RATE,
                       fob_exact=True)
    rounded = parse_text(LEGACY_TEXT, registry, tmp_path, register_chassis=False, taux_douane=RATE)
    assert sorted(prices(rounded)) == [200.0, 800.0]
    assert tostring(generate_xml(rounded)) == tostring(generate_xml(exact))


def test_legacy_fob_exact_keeps_cents(registry, tmp_path):
    data = parse_text(legacy_text("800,01", "199,99", "1 000,00"), registry, tmp_path,
                      register_chassis=False, taux_douane=RATE, fob_exact=True)
    assert sorted(prices(data)) == [199.99, 800.01]
    assert data.valuation.total_invoice == 1000.0
    assert data.valuation.insurance.amount_national == formula(1000, 200, RATE)


# ------------------------------------------------------------------ format 2026
def test_2026_fractional_articles(registry, tmp_path):
    # RFCV XOF : 33 333,34 + 33 333,33 + 33 333,33 -> 3 × 33 334 = 100 002
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0)
    assert prices(data) == [33334.0, 33334.0, 33334.0]
    assert data.valuation.total_invoice == 100002.0
    assert data.valuation.invoice.amount_national == 100002.0
    assert data.valuation.insurance.amount_national == formula(100002, 3000, 1.0)
    assert data.valuation.total_cif == 100002 + 3000 + data.valuation.insurance.amount_national


def test_2026_fob_exact(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_exact=True)
    assert prices(data) == [33333.34, 33333.33, 33333.33]
    assert data.valuation.total_invoice == 100000.0


def test_attested_insurance_kept(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      insurance_mode="rfcv")
    assert data.valuation.insurance.amount_national == 150         # case 21, pas la formule


def test_imposed_insurance_kept(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      assurance_imposee=999)
    assert data.valuation.insurance.amount_national == 999


# ------------------------------------------------------------------ après révision du FOB
def test_revision_uniform_integer_unchanged(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=3 * 43101, fob_mode="uniforme")
    assert prices(data) == [43101.0] * 3
    assert data.valuation.total_invoice == 3 * 43101


def test_revision_prorata_distributed_in_units(registry, tmp_path):
    # arrondi actif : répartition en unités entières (plus grand reste), Σ = total révisé exact
    # (au centime puis plafond, on obtenait 50 001 + 50 000 + 50 000 = 150 001)
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=150000)
    assert all(p == int(p) for p in prices(data))
    assert sum(prices(data)) == 150000
    assert data.valuation.total_invoice == 150000.0
    assert data.valuation.insurance.amount_national == formula(150000, 3000, 1.0)


def test_revision_prorata_units_odd_total(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=100001)
    assert all(p == int(p) for p in prices(data))
    assert sum(prices(data)) == 100001
    assert data.valuation.total_invoice == 100001.0


def test_revision_uniform_units_not_divisible(registry, tmp_path):
    # 100 000 / 3 : au centime 33 333,34 + 33 333,33 × 2 -> plafond 33 334 × 3 = 100 002
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=100000, fob_mode="uniforme")
    assert prices(data) == [33334.0, 33333.0, 33333.0]
    assert data.valuation.total_invoice == 100000.0


def test_revision_total_with_cents_rounded_up_first(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=100000.40, fob_mode="uniforme")
    assert prices(data) == [33334.0, 33334.0, 33333.0]
    assert data.valuation.total_invoice == 100001.0


def test_revision_uniform_fob_exact_keeps_cents(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=100000, fob_mode="uniforme", fob_exact=True)
    assert prices(data) == [33333.34, 33333.33, 33333.33]
    assert data.valuation.total_invoice == 100000


def test_revision_prorata_fob_exact(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                      fob_revise=150000, fob_exact=True)
    assert prices(data) == [50000.01, 50000.0, 49999.99]
    assert data.valuation.total_invoice == 150000


# ------------------------------------------------------------------ réglages, CLI, batch
def test_settings_fob_exact_roundtrip():
    from generation import GenerationSettings
    s = GenerationSettings(taux_douane=1.0, fob_exact=True)
    assert s.to_dict()["fob_exact"] is True
    assert GenerationSettings.from_dict(s.to_dict()) == s
    assert GenerationSettings(taux_douane=1.0).fob_exact is False
    # réglages enregistrés avant l'option : arrondi par défaut
    assert GenerationSettings.from_dict({"taux_douane": 1.0}).fob_exact is False


def _run_cli(monkeypatch, *argv):
    import converter
    monkeypatch.setattr(sys, "argv", ["converter.py", *argv])
    with pytest.raises(SystemExit) as exc:
        converter.main()
    return exc.value.code


@pytest.mark.parametrize("argv, expected", [([], False), (["--fob-exact"], True)])
def test_cli_single_file_fob_exact(monkeypatch, argv, expected):
    import converter
    seen = {}
    monkeypatch.setattr(converter, "convert_pdf_to_xml", lambda *a, **kw: seen.update(kw) or True)
    assert _run_cli(monkeypatch, "a.pdf", "--taux-douane", "596.302", *argv) == 0
    assert seen["fob_exact"] is expected


@pytest.mark.parametrize("argv, expected", [([], False), (["--fob-exact"], True)])
def test_cli_batch_fob_exact(monkeypatch, tmp_path, argv, expected):
    import converter
    seen = {}

    class FakeProcessor:
        def __init__(self, config):
            seen["config"] = config

        def process(self):
            return {"results": [], "success": True}

    monkeypatch.setattr(converter, "BatchProcessor", FakeProcessor)
    assert _run_cli(monkeypatch, "a.pdf", "b.pdf", "--taux-douane", "596.302", *argv) == 0
    assert seen["config"].fob_exact is expected


def test_batch_file_options_fob_exact(tmp_path):
    from batch_processor import BatchConfig, BatchProcessor
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    proc = BatchProcessor(BatchConfig(input_paths=[str(pdf)], fob_exact=True, progress_bar=False))
    assert proc._file_options(pdf)["fob_exact"] is True
    proc = BatchProcessor(BatchConfig(input_paths=[str(pdf)], progress_bar=False))
    assert proc._file_options(pdf)["fob_exact"] is False


def test_webapp_form_fob_exact_checkbox():
    from generation import GenerationSettings
    from webapp.routes import form_to_settings, settings_to_form
    s, errors = form_to_settings({"taux_douane": "596.302", "fob_exact": "1"})
    assert errors == [] and s.fob_exact is True
    assert settings_to_form(s)["fob_exact"] == "1"
    s, _ = form_to_settings({"taux_douane": "596.302"})
    assert s.fob_exact is False
    assert settings_to_form(GenerationSettings(taux_douane=1.0))["fob_exact"] == ""


def test_webapp_settings_template_has_checkbox():
    html = (ROOT / "src" / "webapp" / "templates" / "_reglages.html").read_text(encoding="utf-8")
    assert 'case("fob_exact", "FOB exact (sans arrondi)")' in html


def test_grouped_articles_rounded_after_grouping(registry, tmp_path):
    # même code SH sans châssis : un article déclaré (Σ 800,40 + 199,60 = 1 000,00), arrondi
    # après regroupement (choix : aucun dossier Karta ne départage encore les deux lectures)
    text = (legacy_text("800,40", "199,60", "1 000,00")
            .replace(f"MOTORCYCLE {'LZSPCJLG5P1234567'} 8711.20.90.00", "FAN BLADES 8414.90.10.00"))
    data = parse_text(text, registry, tmp_path, register_chassis=False, taux_douane=RATE)
    assert prices(data) == [1000.0]
    assert data.valuation.total_invoice == 1000.0
