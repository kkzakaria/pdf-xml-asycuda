"""
Dossiers sans châssis : règles relevées sur les déclarations Karta 31476 et 32722 (marchandise
générale, lignes RFCV de même code SH regroupées en un article).

  - case 22 : FOB de chaque LIGNE RFCV arrondi à l'unité supérieure AVANT le regroupement
    (31476, 6309 : ⌈681,50⌉ + ⌈507,50⌉ + ⌈725⌉ = 1 915, et non ⌈1 914⌉ = 1 914) ;
  - fret et assurance répartis au prorata du FOB LIGNE par LIGNE (plus grand reste), puis
    sommés par article (32722, 6309 : 358 + 391 = 749 USD) ; montants nationaux arrondis par
    ligne puis sommés ;
  - poids brut / net : parts égales par ligne RFCV, reste sur la première ligne
    (31476 : 18 000 kg / 7 lignes -> 2 571, première 2 574) ; case 41 (QA) = poids net ;
  - colis : somme des quantités des lignes de l'article, si elles totalisent la case 24 ;
  - case 44 « <facture> DU <date> » : premier article seulement ;
  - Total_cost = round(fret total × taux) + assurance ; Total_CIF = round(FOB total × taux) + Total_cost.

Textes RFCV fictifs.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_ecarts_karta_31917 import LEGACY_TEXT
from test_rfcv_format_2026 import generate_xml, parse_text

from chassis_registry import ChassisRegistry

RATE = 604.922

LINES = """1 30,00 U O CN USED MATTRESS 9404.90.00.00 1 000,00 1 500,00
2 60,00 U O CN USED BAGS( THIRD CHOICE) 6309.00.00.00 400,50 600,00
3 70,00 U O CN USED SHOES( THIRD CHOICE) 6309.00.00.00 300,50 450,00
4 40,00 U O CN USED VOLTAGE REGULATOR 8504.40.90.00 900,00 1 350,00
Sous-total Page 1 de Page 1 2 601,00 3 900,00
TOTAL GÉNÉRAL TOUTES PAGES 2 601,00 3 900,00"""


def goods_text(lines: str = LINES, packages: int = 200, loading: str = "CNNSA") -> str:
    """RFCV historique fictif sans châssis : 4 lignes, dont deux de code SH 6309."""
    head, _, rest = LEGACY_TEXT.partition("1 49,00 U N CN")
    tail = rest[rest.index("27. Remarques"):]
    return (head.replace("1 000,00 1 100,00", "902,00 1 003,00")       # poids net / brut
                .replace("1 000,00 200,00", "2 601,00 1 000,00")       # FOB / fret
                .replace("50 PACKAGES", f"{packages} PACKAGES")
                .replace("Lieu de chargement: CNNSA", f"Lieu de chargement: {loading}")
            + lines + "\n" + tail)


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


@pytest.fixture
def data(registry, tmp_path):
    return parse_text(goods_text(), registry, tmp_path, register_chassis=False, taux_douane=RATE)


def by_hs(data):
    return {i.tarification.hscode.commodity_code[:4]: i for i in data.items}


def test_lines_grouped_by_hs_code(data):
    assert [i.tarification.hscode.commodity_code[:4] for i in data.items] == ["9404", "6309", "8504"]


def test_fob_rounded_per_rfcv_line_before_grouping(data):
    # ⌈400,50⌉ + ⌈300,50⌉ = 401 + 301 = 702 (arrondi après regroupement : ⌈701⌉ = 701)
    assert [i.tarification.item_price for i in data.items] == [1000.0, 702.0, 900.0]
    assert data.valuation.total_invoice == 2602.0


def test_fob_exact_keeps_cents(registry, tmp_path):
    d = parse_text(goods_text(), registry, tmp_path, register_chassis=False, taux_douane=RATE, fob_exact=True)
    assert [i.tarification.item_price for i in d.items] == [1000.0, 701.0, 900.0]


def test_freight_distributed_per_line_then_summed(data):
    # lignes (FOB 1000, 401, 301, 900 / 2602) : 384,32 154,11 115,68 345,89 -> 384 154 116 346
    freight = [i.valuation_item.external_freight.amount_foreign for i in data.items]
    assert freight == [384.0, 270.0, 346.0]
    assert sum(freight) == 1000


def test_national_amounts_rounded_per_line(data):
    vi = by_hs(data)["6309"].valuation_item
    assert vi.invoice.amount_national == round(401 * RATE) + round(301 * RATE)
    assert vi.external_freight.amount_national == round(154 * RATE) + round(116 * RATE)


def test_insurance_distributed_per_line(data):
    insurance = [i.valuation_item.insurance.amount_national for i in data.items]
    assert sum(insurance) == data.valuation.insurance.amount_national


def test_weights_equal_per_line_remainder_on_first(data):
    # 1 003 kg / 4 lignes = 250 reste 3 ; 902 / 4 = 225 reste 2
    assert [i.valuation_item.gross_weight for i in data.items] == [253.0, 500.0, 250.0]
    assert [i.valuation_item.net_weight for i in data.items] == [227.0, 450.0, 225.0]
    # case 41 : unité d'apurement = poids net de l'article
    assert [i.tarification.supplementary_units[0].quantity for i in data.items] == [227, 450, 225]


def test_packages_from_rfcv_line_quantities(data):
    assert [i.packages.number_of_packages for i in data.items] == [30.0, 130.0, 40.0]


def test_packages_on_first_article_when_quantities_do_not_match(registry, tmp_path):
    d = parse_text(goods_text(packages=150), registry, tmp_path, register_chassis=False, taux_douane=RATE)
    assert [i.packages.number_of_packages for i in d.items] == [150.0, 0.0, 0.0]


def test_invoice_free_text_on_first_article_only(data):
    assert [i.free_text_1 for i in data.items] == ["FAC-TEST-001 DU 13/10/2026", None, None]
    # document joint 0007 FACTURE conservé sur tous les articles, comme Karta
    assert all("0007" in [d.code for d in i.attached_documents] for i in data.items)


def test_totals_from_global_amounts(data):
    insurance = data.valuation.insurance.amount_national
    cost = round(1000 * RATE) + insurance
    assert data.valuation.total_cost == cost
    assert data.value_details == cost
    assert data.valuation.total_cif == round(2602 * RATE) + cost


def test_xml_items(data):
    root = generate_xml(data)
    item = root.findall("Item")[1]
    assert item.findtext("Packages/Number_of_packages") == "130"
    assert item.findtext("Tarification/Item_price") == "702.0"
    assert item.findtext("Valuation_item/Weight_itm/Gross_weight_itm") == "500"
    assert root.findtext("General_information/Value_details") == f"{data.value_details}"


def test_loading_place_tianjin_xingang(registry, tmp_path):
    d = parse_text(goods_text(loading="CNTXG"), registry, tmp_path, register_chassis=False, taux_douane=RATE)
    assert d.transport.loading_place_name == "TIANJINXINGANG"


def test_dossier_with_chassis_keeps_weights_prorata_fob(registry, tmp_path):
    # 31917 fictif (ventilateur + moto avec châssis) : poids au prorata du FOB (800 / 200)
    d = parse_text(LEGACY_TEXT, registry, tmp_path, register_chassis=False, taux_douane=596.302)
    assert sorted(i.valuation_item.gross_weight for i in d.items) == [220.0, 880.0]
