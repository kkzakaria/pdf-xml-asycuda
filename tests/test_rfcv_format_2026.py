"""
Tests du format RFCV 2026 (texte pdfplumber des RFCV générés actuels) et des champs
calculés attendus par ASYCUDA.

Références : XML de production 28923 / 28928 et export ASYCUDA réel 28926
(voir claudedocs/ANALYSE_28926_ECARTS_ASYCUDA.md).
"""
import sys
import xml.etree.ElementTree as ET  # XML produit par le test lui-même, pas de source externe
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import rfcv_format_2026 as fmt
from asycuda_enrichment import distribute_evenly, format_value_item, to_asycuda_date
from chassis_registry import ChassisRegistry
from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator

SAMPLE_PDF = Path(__file__).resolve().parents[1] / "OT_M_2026_08746_BL_2026_07362_RFCV_v1.pdf"

# Extrait au format « article sur trois lignes » (désignation / données / VIN), comme les
# RFCV de motos dont la désignation porte le châssis.
MULTILINE_TEXT = """RFCV
Page 2
4. No RFCV 5. Date RFCV 6. Livraison
1. Nom et Adresse de l'Importateur Code: 1234567X
RCSA6099999 03/11/2026
7. No FDI/DAI 8. Date FDI/DAI
SOCIETE TEST
260200000 30/10/2026
9. Pays de provenance 10. Mode de paiement
BP 1 BOUAKE (VILLE)
Togo Paiement sur compte
2. Nom et Adresse de l'Exportateur 11. Poids Total Net (Kg) 12. Poids Total Brut (Kg)
30.00 35.00
EXPORTATEUR TEST 13. No Facture 14. Date Facture 15. INCOTERM
FAC-001 24/09/2026 CFR
LOME 16. Code devise 17. Taux de Change 18. Total
Togo XOF 1.00 100,000.00
3. Détails Transport 19. Total FOB 20. Fret
100,000.00 3,000.00
No. (LTA/Connaissement/CMR) Mode de transport :
28N-9999 Transport par route 21. Assurance 22. Charges 23. Total Customs
No. (Maison Airway Bill/HBL) No. (Vol/Voyage/Transport 150.00 0.00 103,150.00
TG 0001 BT 24. Colisage, Nombre et Designation des marchandises
Date de Transporteur ID : 3 - Colis ("package")
29/10/2026 TRANSPORTEUR TEST
No. de LCL 0 Lieu de chargement : TGLFW MOTO (TEST)
No. de FCL 0 Lieu de transbordement
Lieu de déchargement :
CIABJ
25. Conteneurs
26. Articles
A Quantité U M P O U Description des marchandises M E Code SH Valeur FOB en Valeur taxable dans
C E R I I
MOTO - HAOJUE -
1 1.0 UNITE TG N 1 8711209900 33,333.34
LC6XCH1G7T1519802
MOTO - HAOJUE -
2 1.0 UNITE TG N 1 8711209900 33,333.33
LC6XCH1G7T1519489
MOTO - SANYA -
3 1.0 UNITE TG N 1 8711209900 33,333.33
LK1PCJL85T1050418
Sous -total P1 100,000.00 0.00
TOTAL GENERAL TOUTES PAGES 100,000.00 0.00
27. Remarques
"""


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


def parse_text(text, registry, tmp_path, **kwargs):
    """Parse un texte RFCV sans PDF (extracteur remplacé)."""
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
        return RFCVParser(str(tmp_path / "rfcv.pdf"), registry=registry, **kwargs).parse()
    finally:
        rfcv_parser.PDFExtractor = original


def generate_xml(rfcv_data):
    gen = XMLGenerator(rfcv_data)
    gen.generate()
    return ET.fromstring(ET.tostring(gen.root))


# --------------------------------------------------------------- utilitaires
class TestHelpers:
    def test_asycuda_date(self):
        assert to_asycuda_date("27/07/2026") == "7/27/26"
        assert to_asycuda_date("03/11/2026") == "11/3/26"
        assert to_asycuda_date(None) is None

    def test_value_item_format(self):
        assert format_value_item(83012, 491) == "83,012+0+491+0-0"

    def test_distribute_evenly_like_production(self):
        # 28928 : 423 colis / 35 articles -> 3 × 13 puis 32 × 12
        parts = distribute_evenly(423, 35)
        assert parts[:3] == [13, 13, 13] and set(parts[3:]) == {12} and sum(parts) == 423
        # 28923 : 1039 / 105 -> 94 × 10 puis 11 × 9
        parts = distribute_evenly(1039, 105)
        assert parts.count(10) == 94 and parts.count(9) == 11 and sum(parts) == 1039


# --------------------------------------------------------------- lecture texte
class TestFormatDetection:
    def test_multiline_text_detected(self):
        assert fmt.is_format_2026(MULTILINE_TEXT)

    def test_legacy_text_not_detected(self):
        assert not fmt.is_format_2026("19. Total Valeur FOB attestée 20. Fret Attesté\n26. Articles")


class TestMultilineItems:
    def test_header(self):
        h = fmt.parse_header(MULTILINE_TEXT)
        assert h["rfcv_number"] == "RCSA6099999"
        assert h["fdi_number"] == "260200000" and h["fdi_date"] == "30/10/2026"
        assert h["currency_code"] == "XOF" and h["exchange_rate"] == 1.0
        assert h["fob"] == 100000.0 and h["freight"] == 3000.0 and h["insurance"] == 150.0
        assert h["bill_of_lading"] == "28N-9999"
        assert h["transport_mode_code"] == "3"
        assert h["loading_place"] == "TGLFW" and h["loading_place_name"] == "LOME"
        assert h["total_packages"] == 3

    def test_items_with_vin_on_third_line(self):
        items, subtotals, problems = fmt.parse_items(MULTILINE_TEXT)
        assert problems == []
        assert [i["n"] for i in items] == [1, 2, 3]
        assert items[0]["description"] == "MOTO - HAOJUE - LC6XCH1G7T1519802"
        assert items[2]["description"] == "MOTO - SANYA - LK1PCJL85T1050418"
        assert round(sum(i["fob"] for i in items), 2) == subtotals[1] == 100000.0


# --------------------------------------------------------------- pipeline complet
class TestPipelineWithChassis:
    @pytest.fixture
    def data(self, registry, tmp_path):
        return parse_text(MULTILINE_TEXT, registry, tmp_path, taux_douane=1.0)

    def test_vins_from_rfcv(self, data):
        assert [i.packages.chassis_number for i in data.items] == [
            "LC6XCH1G7T1519802", "LC6XCH1G7T1519489", "LK1PCJL85T1050418"]
        assert data.items[0].free_text_1 == "CH: LC6XCH1G7T1519802"
        assert data.items[0].packages.marks2 == "CH: LC6XCH1G7T1519802"
        # désignation courte et code colis CT, comme les déclarations de production (31287)
        assert data.items[0].goods_description == "MOTO"
        assert data.items[0].packages.marks1 == "MOTO"
        assert data.items[0].packages.kind_code == "CT"

    def test_short_designation(self):
        assert fmt.short_designation("MOTORCYCLE-FENGHAO - LRFXGHLG2T0F24630") == "MOTORCYCLE"
        assert fmt.short_designation("MOTO - HAOJUE - LC6XCH1G7T1519802") == "MOTO"
        assert fmt.short_designation("MOTORCYCLE") == "MOTORCYCLE"

    def test_insurance_formula_by_default(self, data):
        # ceil(2500 + (100 000 + 3 000) × 1 × 0,0015) = 2655, comme les déclarations de production
        assert data.valuation.insurance.amount_national == 2655
        assert sum(i.valuation_item.insurance.amount_national for i in data.items) == 2655

    def test_insurance_attested_option(self, registry, tmp_path):
        d = parse_text(MULTILINE_TEXT, registry, tmp_path, taux_douane=1.0, insurance_mode="rfcv")
        assert d.valuation.insurance.amount_national == 150

    def test_packages_spread_on_chassis_items(self, data):
        assert [i.packages.number_of_packages for i in data.items] == [1.0, 1.0, 1.0]

    def test_computed_values(self, data):
        for item in data.items:
            vi = item.valuation_item
            efr, ins = vi.external_freight.amount_national, vi.insurance.amount_national
            assert vi.total_cost == efr + ins
            assert vi.total_cif == vi.invoice.amount_national + efr + ins
            assert vi.statistical_value == vi.total_cif
            assert item.tarification.value_item == format_value_item(int(efr), int(ins))
        assert data.value_details == 3000 + 2655
        assert data.valuation.total_cost == 5655

    def test_attached_documents_like_real_declarations(self, data):
        assert [d.code for d in data.items[0].attached_documents] == [
            "0007", "0014", "6603", "2500", "2501", "6610", "6122"]
        # 6610 (FDI) sur le premier article uniquement, comme en production
        assert [d.code for d in data.items[1].attached_documents] == [
            "0007", "0014", "6603", "2500", "2501", "6122"]
        assert data.items[0].attached_documents[5].reference == "260200000"
        assert data.items[0].attached_documents[5].from_rule == 0
        docs = {d.code: d for d in data.items[1].attached_documents}
        assert docs["0007"].reference == "FAC-001" and docs["0007"].document_date == "24/09/2026"
        assert docs["0014"].reference == "VD" and docs["6603"].reference == "VD"
        assert docs["2500"].reference == "2"  # n° de ligne RFCV
        assert docs["2501"].reference == "RCSA6099999"
        assert docs["6122"].reference == "LC6XCH1G7T1519489"

    def test_xml_fields(self, data):
        root = generate_xml(data)
        item = root.find("Item")
        refs = {d.findtext("Attached_document_code"): d for d in item.findall("Attached_documents")}
        assert refs["0007"].findtext("Attached_document_reference") == "FAC-001"
        assert refs["0007"].findtext("Attached_document_date") == "9/24/26"
        assert refs["6610"].findtext("Attached_document_from_rule") == "0"
        assert item.findtext("Previous_doc/Summary_declaration") == "28N-9999"
        assert item.findtext("Free_text_1") == "CH: LC6XCH1G7T1519802"
        assert item.findtext("Packages/Number_of_packages") == "1"
        assert item.findtext("Tarification/Value_item")
        assert item.findtext("Valuation_item/Statistical_value")
        assert item.findtext("Valuation_item/item_internal_freight/Amount_national_currency") == "0.0"
        assert root.findtext("General_information/Value_details") == "5655.0"
        assert root.findtext("Transport/Place_of_loading/Code") == "TGLFW"
        assert root.findtext("Transport/Means_of_transport/Border_information/Mode") == "3"
        assert root.findtext("Valuation/Gs_insurance/Amount_national_currency") == "2655.0"


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="PDF d'exemple absent")
class TestSamplePdf:
    """RFCV RCSA6013381 (USD, désignation sur la ligne de données, sans VIN)."""

    @pytest.fixture
    def data(self, registry):
        return RFCVParser(str(SAMPLE_PDF), taux_douane=576.42, registry=registry).parse()

    def test_header_and_items(self, data):
        assert data.identification.rfcv_number == "RCSA6013381"
        assert data.financial.currency_code == "USD" and data.financial.exchange_rate == 576.42
        assert data.transport.bill_of_lading == "ONEYCANG44370500"
        # 35 motos sans châssis, même code SH -> regroupées en un article portant les 215 colis
        assert len(data.items) == 1
        assert data.items[0].packages.number_of_packages is None or data.items[0].tarification

    def test_insurance_formula(self, data):
        assert data.valuation.insurance.amount_national == 16926  # ceil(2500 + 16 683,65 × 576,42 × 0,0015)

    def test_insurance_attested_converted_to_xof(self, registry):
        d = RFCVParser(str(SAMPLE_PDF), taux_douane=576.42, registry=registry, insurance_mode="rfcv").parse()
        assert d.valuation.insurance.amount_national == 28850  # 50,05 USD × 576,42

    def test_customs_rate_used_for_conversion(self, registry):
        # ASYCUDA convertit au taux douanier, pas au taux du RFCV (576,42 ici)
        d = RFCVParser(str(SAMPLE_PDF), taux_douane=573.9681, registry=registry).parse()
        assert d.financial.exchange_rate == 573.9681
        assert d.valuation.external_freight.amount_national == round(4000 * 573.9681)

    def test_freight_national(self, data):
        assert data.valuation.external_freight.amount_national == 2305680.0  # 4 000 USD × 576,42


# --------------------------------------------------------------- régressions (dossier rfcv, 03/11/2026)
MIXED_LAYOUT_ITEMS = """26. Articles
MOTO-HAOJUE -
300 1.0 UNITE TG N 1 8711209900 43,617.12
LC6JCK4P1T0073070
301 1.0 UNITE TG N MOTO-SANYA - LK1PCJL1XT1031110 1 8711209900 43,617.12
302 1.0 UNITE TG N MOTO-SANYA - LK1PCJL19T1031146 1 8711209900 43,617.12
Sous -total P1 130,851.36 0.00
"""


class TestRegressions:
    def test_mixed_layouts_do_not_share_vin(self):
        # Une désignation sur la ligne de données ne récupère pas le VIN de l'article précédent
        items, _, _ = fmt.parse_items(MIXED_LAYOUT_ITEMS)
        assert [i["description"] for i in items] == [
            "MOTO-HAOJUE - LC6JCK4P1T0073070",
            "MOTO-SANYA - LK1PCJL1XT1031110",
            "MOTO-SANYA - LK1PCJL19T1031146",
        ]

    def test_partial_delivery_rfcv_number(self):
        text = MULTILINE_TEXT.replace("RCSA6099999 03/11/2026", "RCSA6099999-P1 03/11/2026")
        assert fmt.parse_header(text)["rfcv_number"] == "RCSA6099999-P1"
