"""Tests du profil société (constantes de déclaration absentes du RFCV)."""
import sys
import xml.etree.ElementTree as ET  # XML produit par le test lui-même
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from company_profile import CompanyProfile, apply_profile, load_profile
from models import Financial, Identification, RFCVData, Trader, TransportInfo
from xml_generator import XMLGenerator

PROFILE_FILE = Path(__file__).resolve().parents[1] / "profils" / "karta-transit.ini"


def make_data(deferred=None):
    return RFCVData(
        identification=Identification(customs_office_code="CIAB1", customs_office_name="ABIDJAN-PORT"),
        financial=Financial(deferred_payment_ref=deferred),
        transport=TransportInfo(),
        declarant=Trader(),
    )


class TestLoadProfile:
    def test_sample_profile(self):
        p = load_profile(str(PROFILE_FILE))
        assert p.bureau_code == "CIAB6" and p.bureau_nom == "ABJ GUICHET UNIQUE"
        assert p.declarant_code == "00537M"
        assert p.reference_prefixe == "KARTA"   # commentaire en fin de ligne retiré
        assert p.compte == "2600537M"
        assert p.emplacement == "AIRE"

    def test_comments_empty_values_and_newline(self, tmp_path):
        f = tmp_path / "p.ini"
        f.write_text("# entête\n\nbureau_code=CIAB6   # bureau\nbanque_code=\n"
                     "declarant_nom=Ligne 1\\nLigne 2\n", encoding="utf-8")
        p = load_profile(str(f))
        assert p.bureau_code == "CIAB6"
        assert p.banque_code is None
        assert p.declarant_nom == "Ligne 1\nLigne 2"

    def test_unknown_key_rejected(self, tmp_path):
        f = tmp_path / "p.ini"
        f.write_text("bureau_cod=CIAB6\n", encoding="utf-8")
        with pytest.raises(ValueError, match="clé inconnue"):
            load_profile(str(f))


class TestApplyProfile:
    def test_all_fields(self):
        d = apply_profile(make_data(), load_profile(str(PROFILE_FILE)), dossier="31287",
                          manifeste="CIAB1 2026 7065", nationalite_transport="LR")
        assert d.identification.customs_office_code == "CIAB6"
        assert d.identification.manifest_reference == "CIAB1 2026 7065"
        assert d.declarant.code == "00537M"
        assert d.declarant.reference == "KARTA31287"
        assert d.financial.bank.code == "BDU1"
        assert d.financial.deferred_payment_ref == "2600537M"
        assert d.transport.goods_location == "AIRE"
        assert d.transport.vessel_nationality == "LR"

    def test_payment_report_has_priority(self):
        d = apply_profile(make_data(deferred="25P2003J"), CompanyProfile(compte="2600537M"))
        assert d.financial.deferred_payment_ref == "25P2003J"

    def test_without_profile_keeps_defaults(self):
        d = apply_profile(make_data(), None, dossier="31287")
        assert d.identification.customs_office_code == "CIAB1"
        assert d.declarant.reference == "31287"

    def test_xml_output(self):
        d = apply_profile(make_data(), load_profile(str(PROFILE_FILE)), dossier="31287",
                          manifeste="CIAB1 2026 7065", nationalite_transport="LR")
        gen = XMLGenerator(d)
        gen.generate()
        root = ET.fromstring(ET.tostring(gen.root))
        assert root.findtext("Identification/Office_segment/Customs_clearance_office_code") == "CIAB6"
        assert root.findtext("Identification/Manifest_reference_number") == "CIAB1 2026 7065"
        assert root.findtext("Declarant/Declarant_name") == (
            "KARTA Transit\nAbidjan, Treichville avenue 21 rue 68 - 05 BP 1256 Abidjan 05")
        assert root.findtext("Declarant/Reference/Number") == "KARTA31287"
        assert root.findtext("Financial/Bank/Code") == "BDU1"
        assert root.findtext("Financial/Deffered_payment_reference") == "2600537M"
        assert root.findtext("Transport/Location_of_goods") == "AIRE"
        assert root.findtext("Transport/Means_of_transport/Departure_arrival_information/Nationality") == "LR"

    def test_xml_nulls_without_profile(self):
        gen = XMLGenerator(make_data())
        gen.generate()
        root = ET.fromstring(ET.tostring(gen.root))
        assert root.find("Identification/Manifest_reference_number/null") is not None
        assert root.find("Transport/Location_of_goods/null") is not None
