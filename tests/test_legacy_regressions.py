"""Format RFCV historique : régressions relevées sur le dossier rfcv (03/11/2026)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from item_grouper import group_items_by_hs_code
from models import HSCode, Item, Package, Tarification, ValuationItem
from rfcv_parser import RFCVParser

ITEM_PATTERN_SECTION = (
    "PLASTIC DISPOSABLE LIGHTERS ART NO.DY-066(50 PCS/BOX,20\n"
    "1 4 000,00 U N CN BOXES/CARTON) 9613.10.00.00 14 600,00 18 558,02\n"
    "2 20,00 U N CN LIGHTERS 9613.10.00.00 2 068,00 2 628,63\n"
)


def item(hs, fob, taxable):
    return Item(tarification=Tarification(hscode=HSCode(commodity_code=hs), item_price=fob),
                valuation_item=ValuationItem(total_cost=fob, total_cif=taxable), packages=Package())


def test_grouped_line_carries_group_value_and_packages():
    items = [item("33072000", 3900.0, 5209.18), item("33072000", 1039.5, 1388.45), item("33072000", 2309.0, 3084.10)]
    result = group_items_by_hs_code(items, total_packages=1812)
    assert len(result) == 1
    assert result[0].tarification.item_price == 7248.5
    assert result[0].valuation_item.total_cif == 9681.73
    assert result[0].packages.number_of_packages == 1812.0


def test_item_pattern_anchored_and_description_continued():
    import re
    parser = RFCVParser.__new__(RFCVParser)
    pattern = (r'(?m)^(\d+) +([\d ]+,\d{2}) +(\w+) +(\w+) +(\w+) +(.*?) +(\d{4}\.\d{2}\.\d{2}\.\d{2})'
               r' +([\d ]+,\d{2}) +([\d ]+,\d{2})')
    matches = list(re.finditer(pattern, ITEM_PATTERN_SECTION))
    assert [m.group(1) for m in matches] == ["1", "2"]          # pas « 20 » de la ligne précédente
    assert parser._parse_number(matches[0].group(2)) == 4000.0
    assert parser._legacy_description(ITEM_PATTERN_SECTION, matches[0], pattern) == (
        "PLASTIC DISPOSABLE LIGHTERS ART NO.DY-066(50 PCS/BOX,20 BOXES/CARTON)")
    assert parser._legacy_description(ITEM_PATTERN_SECTION, matches[1], pattern) == "LIGHTERS"


def test_legacy_country_codes():
    parser = RFCVParser.__new__(RFCVParser)
    for provenance, code in [("Togo", "TG"), ("Oman", "OM"), ("Chine", "CN"), ("Somalie", None)]:
        parser.text = f"9. Pays de provenance 10. Mode de Paiement\n{provenance} Paiement sur compte bancaire\n"
        assert parser._parse_country().export_country_code == code, provenance
