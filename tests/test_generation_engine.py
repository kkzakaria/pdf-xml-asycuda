"""Moteur de génération : contrôle des châssis sans écriture dans le registre."""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT, parse_text

from chassis_registry import ChassisRegistry
from rfcv_parser import RFCVParser


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


def parse_text_parser(text, registry, tmp_path, **kwargs):
    """Comme parse_text, mais rend le parseur après parse()."""
    import rfcv_parser

    class FakeExtractor:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return text

        def extract_all_tables(self):
            return []

    original = rfcv_parser.PDFExtractor
    rfcv_parser.PDFExtractor = FakeExtractor
    try:
        parser = RFCVParser(str(tmp_path / "rfcv.pdf"), registry=registry, **kwargs)
        parser.parse()
        return parser
    finally:
        rfcv_parser.PDFExtractor = original


def test_check_only_never_writes(registry, tmp_path):
    parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False)
    assert registry.get_all_extracted() == []


def test_check_only_reports_conflicts_instead_of_raising(registry, tmp_path):
    parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=True)  # enregistre
    p = parse_text_parser(MULTILINE_TEXT.replace("RCSA6099999", "RCSA6099998"), registry, tmp_path,
                          register_chassis=False)  # ne lève pas
    assert {c["first_rfcv_number"] for c in p.chassis_conflicts} == {"RCSA6099999"}


def test_fob_uniform(registry, tmp_path):
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, fob_revise=150000, fob_mode="uniforme")
    assert [i.tarification.item_price for i in d.items] == [50000.0, 50000.0, 50000.0]


def test_imposed_freight_and_insurance_per_article_reference_case(registry, tmp_path):
    # cas de référence 6014670 transposé : FOB 5 400, fret 2 000, assurance 93 par article
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0,
                   fob_revise=3 * 5400, fob_mode="uniforme", fret_impose=3 * 2000, assurance_imposee=3 * 93)
    vi = [i.valuation_item for i in d.items]
    assert [v.external_freight.amount_national for v in vi] == [2000.0] * 3
    assert [v.insurance.amount_national for v in vi] == [93.0] * 3
    assert [v.total_cif for v in vi] == [7493.0] * 3
    assert d.items[0].tarification.value_item == "2,000+0+93+0-0"


def test_imposed_freight_recomputes_formula_insurance(registry, tmp_path):
    # fob_exact : formule sur le FOB attesté 100 000 (arrondi par défaut : tests/test_fob_arrondi.py)
    d = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0, fret_impose=10000,
                   fob_exact=True)
    assert d.valuation.insurance.amount_national == math.ceil(2500 + (100000 + 10000) * 0.0015)


@pytest.mark.parametrize("kw", [{"fob_mode": "x"}, {"fret_impose": 0}, {"assurance_imposee": -1}])
def test_invalid_imposed_params(kw):
    with pytest.raises(ValueError):
        RFCVParser("x.pdf", **kw)
