"""
Format RFCV historique : écarts relevés en comparant une déclaration de production (dossier
31917, marchandise générale sans châssis) avec la sortie du convertisseur.

Texte RFCV fictif, même mise en page que le texte pdfplumber d'un RFCV historique.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_rfcv_format_2026 import MULTILINE_TEXT, generate_xml, parse_text

from chassis_registry import ChassisRegistry
from rfcv_parser import RFCVParser

VIN = "LZSPCJLG5P1234567"

LEGACY_TEXT = f"""Ce Rapport Final de Classification et de Valeur a été émis à la demande de la Republique de Côte d'Ivoire.
PAGE 1 de 1
1. Nom et Adresse de l'Importateur Code : 1234567Z 4. No. RFCV 5. Date RFCV 6. Livraison
SOCIETE FICTIVE RCS26999999 03/11/2026 TOT
7. No. FDI/DAI 8. Date FDI/DAI
BP 1 BOUAKE (VILLE) - 260100000 28/10/2026
9. Pays de provenance 10. Mode de Paiement
Chine Paiement sur compte bancaire
2. Nom et Adresse de l'Exportateur 11. Poids Total NET (KG) 12. Poids Total BRUT (KG)
EXPORTATEUR FICTIF LTD 1 000,00 1 100,00
13. No. Facture 14. Date Facture 15. INCOTERM
Rue fictive 1
FAC-TEST-001 13/10/2026 CFR
VILLE 16. Code Devise 17. Taux de Change 18. Total Facture
Chine USD 596,3022 1 200,00
19. Total Valeur FOB attestée 20. Fret Attesté
3. Détails Transport
1 000,00 200,00
No. (LTA/Connaissement/CMR): Mode de Transport:
21. Assurance Attestée 22. Charges Attestées 23. Valeur CIF Attestée
123456789 Transport maritime
3,00 1 203,00
No. (Maison Airway Bill/HBL): No. (Vol/Voyage/Transport routier):
24. Colisage, nombre et désignation des marchandises
001W
50 PACKAGES
Date de (LTA/Connaissement/CMR): Transporteur ID:
18/10/2026 NAVIRE FICTIF
No. de LCL: 0
No. de FCL: 1 Lieu de chargement: CNNSA
Lieu de transbordement:
Lieu de déchargement: CIABJ
26. Conteneurs
N No. Conteneur Type Taille No. Scellé N No. Conteneur Type Taille No. Scellé
1 ABCU1234567 Conteneur 40' High cube 40' SEAL-0001
26. Articles
A Quantité U M U P O Description des marchandises Code SH Valeur FOB Attestée Valeur taxable dans
1 49,00 U N CN STANDING FAN PARTS 8414.90.10.00 800,00 962,40
2 1,00 U N CN MOTORCYCLE {VIN} 8711.20.90.00 200,00 240,60
Sous-total Page 1 de Page 1 1 000,00 1 203,00
TOTAL GÉNÉRAL TOUTES PAGES 1 000,00 1 203,00
27. Remarques
"""


@pytest.fixture
def registry(tmp_path):
    return ChassisRegistry(str(tmp_path / "registry.db"))


@pytest.fixture
def legacy(registry, tmp_path):
    data = parse_text(LEGACY_TEXT, registry, tmp_path, register_chassis=False, taux_douane=596.302)
    return data, generate_xml(data)


def items_by_hs(data):
    return {i.tarification.hscode.commodity_code[:4]: i for i in data.items}


def xml_items_by_hs(root):
    return {i.findtext("Tarification/HScode/Commodity_code")[:4]: i for i in root.findall("Item")}


def test_legacy_sample_is_legacy_format(legacy):
    data, _ = legacy
    assert len(data.items) == 2


# 1. Mode de paiement : le pays de provenance (colonne voisine) n'est pas collé ; libellé SYDAM
def test_mode_of_payment_without_country(legacy):
    data, root = legacy
    assert data.financial.mode_of_payment == "COMPTE DE PAIEMENT"
    assert root.findtext("Financial/Mode_of_payment") == "COMPTE DE PAIEMENT"


def test_mode_of_payment_other_mode_kept_without_country():
    parser = RFCVParser.__new__(RFCVParser)
    parser.rapport_paiement = None
    parser.text = "9. Pays de provenance 10. Mode de Paiement\nChine Lettre de crédit\n"
    assert parser._parse_financial().mode_of_payment == "Lettre de crédit"
    parser.text = "9. Pays de provenance 10. Mode de Paiement\nTogo Paiement sur compte bancaire\n"
    assert parser._parse_financial().mode_of_payment == "COMPTE DE PAIEMENT"


# 2. Case 27 : lieu de chargement (UN/LOCODE) et son nom
def test_place_of_loading(legacy):
    _, root = legacy
    assert root.findtext("Transport/Place_of_loading/Code") == "CNNSA"
    assert root.findtext("Transport/Place_of_loading/Name") == "NANSHA"


def test_place_of_loading_unknown_code_has_no_name():
    parser = RFCVParser.__new__(RFCVParser)
    parser.text = "No. de FCL: 1 Lieu de chargement: XXZZZ\nLieu de transbordement:\n"
    t = parser._parse_transport()
    assert t.loading_place_code == "XXZZZ" and t.loading_place_name is None
    # champ vide : rien inventé (pas de lecture sur la ligne suivante)
    parser.text = "No. de FCL: 1 Lieu de chargement:\nLieu de transbordement:\n"
    t = parser._parse_transport()
    assert t.loading_place_code is None and t.loading_place_name is None


# 3. Case 41 : unité d'apurement QA = poids net de l'article sans châssis ; véhicules inchangés
def test_supplementary_unit_net_weight_for_goods_without_chassis(legacy):
    data, root = legacy
    goods = items_by_hs(data)["8414"]
    assert goods.valuation_item.net_weight == 800.0
    units = goods.tarification.supplementary_units
    assert [(u.code, u.name) for u in units] == [("QA", "Unité d'apurement")]
    unit = xml_items_by_hs(root)["8414"].find("Tarification/Supplementary_unit")
    assert unit.findtext("Suppplementary_unit_code") == "QA"
    assert unit.findtext("Suppplementary_unit_name") == "Unité d'apurement"
    assert unit.findtext("Suppplementary_unit_quantity") == "800"


def test_supplementary_unit_unchanged_for_vehicle(legacy):
    data, root = legacy
    moto = items_by_hs(data)["8711"]
    assert [(u.code, u.quantity) for u in moto.tarification.supplementary_units] == [("QA", 1.0), ("40", 1.0)]
    unit = xml_items_by_hs(root)["8711"].find("Tarification/Supplementary_unit")
    assert unit.findtext("Suppplementary_unit_quantity") == "1.0"


def test_supplementary_unit_decimal_net_weight_kept():
    from models import Item, Package, RFCVData, Tarification, ValuationItem
    data = RFCVData(items=[Item(packages=Package(), tarification=Tarification(),
                                valuation_item=ValuationItem(net_weight=12.5)),
                           Item(packages=Package(), tarification=Tarification(),
                                valuation_item=ValuationItem(net_weight=None))])
    RFCVParser._add_clearance_unit_by_weight(data)
    assert data.items[0].tarification.supplementary_units[0].quantity == 12.5
    assert data.items[1].tarification.supplementary_units == []  # pas de poids : rien inventé


# 4. Case 44 : « <facture> DU <date> » pour les articles sans châssis, châssis inchangé sinon
def test_free_text_invoice_for_goods_and_chassis_for_vehicle(legacy):
    data, root = legacy
    assert items_by_hs(data)["8414"].free_text_1 == "FAC-TEST-001 DU 13/10/2026"
    assert items_by_hs(data)["8711"].free_text_1 == f"CH: {VIN}"
    xml_items = xml_items_by_hs(root)
    assert xml_items["8414"].findtext("Free_text_1") == "FAC-TEST-001 DU 13/10/2026"
    assert xml_items["8711"].findtext("Free_text_1") == f"CH: {VIN}"


# 5. Nature des colis : nom de la nomenclature SYDAM, pas le libellé du RFCV
def test_package_type_nomenclature_name(legacy):
    data, root = legacy
    assert root.findtext("Property/Nbers/Package_type") == 'Colis ("package")'
    assert {i.packages.kind_code for i in data.items} == {"PK"}


# Format 2026 : règles communes (unité QA au poids net, case 44) sans toucher aux motos
def test_format_2026_vehicles_unchanged(registry, tmp_path):
    data = parse_text(MULTILINE_TEXT, registry, tmp_path, register_chassis=False, taux_douane=1.0)
    for item in data.items:
        if item.packages.chassis_number:
            assert item.free_text_1 == f"CH: {item.packages.chassis_number}"
            assert [u.quantity for u in item.tarification.supplementary_units] == [1.0, 1.0]
