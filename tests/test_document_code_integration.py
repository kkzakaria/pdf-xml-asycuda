"""
Tests d'intégration pour vérifier les codes de document dans le XML généré
Code 6022: Motos (HS 8711)
Code 6122: Tricycles et autres véhicules
"""
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from models import (
    RFCVData, Item, Package, Tarification, HSCode,
    Property, Identification
)
from xml_generator import XMLGenerator


class TestDocumentCodeInXML:
    """Tests d'intégration pour vérifier les codes de document dans le XML"""

    def create_minimal_rfcv(self):
        """Crée une structure RFCV minimale pour les tests"""
        return RFCVData(
            property=Property(
                total_packages=10,
                package_type='PK',
                date_of_declaration='1/26/25'
            ),
            identification=Identification(
                customs_office_code='CIAB1',
                customs_office_name='ABIDJAN-PORT'
            ),
            items=[]
        )

    def create_vehicle_item(self, hs_code: str, description: str, chassis: str):
        """Crée un article véhicule avec châssis"""
        return Item(
            tarification=Tarification(
                hscode=HSCode(commodity_code=hs_code)
            ),
            goods_description=description,
            packages=Package(
                chassis_number=chassis,
                number_of_packages=1,
                marks1=description
            )
        )

    def test_motorcycle_generates_code_6022(self):
        """Moto (HS 8711) → Code document 6022"""
        # Créer RFCV avec moto
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87112090',
                'MOTORCYCLE YAMAHA YZF-R6',
                'LRFPCJLDIS0F18969'
            )
        ]

        # Générer XML
        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        # Vérifications
        assert '6022' in xml_str, "Code document 6022 absent pour moto"
        assert '6122' not in xml_str, "Code document 6122 présent à tort pour moto"
        assert 'CHASSIS MOTOS' in xml_str, "Nom document MOTOS absent"
        assert 'LRFPCJLDIS0F18969' in xml_str, "Numéro châssis absent"

    def test_tricycle_generates_code_6122(self):
        """Tricycle (HS 8704) → Code document 6122"""
        # Créer RFCV avec tricycle
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87042110',
                'TRICYCLE AP150ZH-20',
                'LLCLHJL03SP420331'
            )
        ]

        # Générer XML
        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        # Vérifications
        assert '6122' in xml_str, "Code document 6122 absent pour tricycle"
        assert '6022' not in xml_str, "Code document 6022 présent à tort pour tricycle"
        assert 'CHASSIS VEHICULES' in xml_str, "Nom document VEHICULES absent"
        assert 'LLCLHJL03SP420331' in xml_str, "Numéro châssis absent"

    def test_car_generates_code_6122(self):
        """Voiture (HS 8703) → Code document 6122"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87032310',
                'CAR TOYOTA COROLLA',
                '2T1BURHE8KC123456'
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        assert '6122' in xml_str
        assert 'CHASSIS VEHICULES' in xml_str
        assert '2T1BURHE8KC123456' in xml_str

    def test_mixed_vehicles_different_codes(self):
        """Mélange motos et tricycles → Codes 6022 et 6122"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87112090',
                'MOTORCYCLE HONDA CBR',
                'MOTO001234567ABC'
            ),
            self.create_vehicle_item(
                '87042110',
                'TRICYCLE AP150ZK',
                'TRIC987654321XYZ'
            ),
            self.create_vehicle_item(
                '87112090',
                'SCOOTER VESPA',
                'SCOO456789012DEF'
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        # Vérifier présence des deux codes
        assert '6022' in xml_str, "Code 6022 (motos) absent"
        assert '6122' in xml_str, "Code 6122 (tricycles) absent"

        # Vérifier les deux noms de document
        assert 'CHASSIS MOTOS' in xml_str
        assert 'CHASSIS VEHICULES' in xml_str

        # Vérifier tous les châssis
        assert 'MOTO001234567ABC' in xml_str
        assert 'TRIC987654321XYZ' in xml_str
        assert 'SCOO456789012DEF' in xml_str

    def test_motorcycle_fallback_no_hs_code(self):
        """Moto sans code HS (fallback mots-clés) → Code 6022"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            Item(
                tarification=None,  # Pas de tarification = pas de code HS
                goods_description='MOTORCYCLE KAWASAKI NINJA',
                packages=Package(
                    chassis_number='KAWASAKI123456789',
                    number_of_packages=1,
                    marks1='MOTORCYCLE KAWASAKI NINJA'
                )
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        assert '6022' in xml_str, "Code 6022 absent (fallback mots-clés)"
        assert 'CHASSIS MOTOS' in xml_str

    def test_truck_generates_code_6122(self):
        """Camion (HS 8704) → Code document 6122"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87043190',
                'TRUCK ISUZU NPR',
                '4NUZT13A681234567'
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        assert '6122' in xml_str
        assert 'CHASSIS VEHICULES' in xml_str

    def test_tractor_generates_code_6122(self):
        """Tracteur (HS 8701) → Code document 6122"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87011000',
                'TRACTOR MASSEY FERGUSON',
                'MF1234567890ABC'
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()
        xml_str = ET.tostring(xml_root, encoding='unicode')

        assert '6122' in xml_str
        assert 'CHASSIS VEHICULES' in xml_str

    def test_xml_structure_motorcycle(self):
        """Vérifier structure complète XML pour moto"""
        rfcv = self.create_minimal_rfcv()
        rfcv.items = [
            self.create_vehicle_item(
                '87113019',
                'MOTORCYCLE SUZUKI',
                'SUZUKI123456789AB'
            )
        ]

        generator = XMLGenerator(rfcv)
        xml_root = generator.generate()

        # Parser le XML
        items = xml_root.findall('.//Item')
        assert len(items) == 1, "Devrait avoir 1 article"

        # Trouver le document châssis
        chassis_docs = items[0].findall('.//Attached_documents')
        chassis_doc = None
        for doc in chassis_docs:
            code = doc.find('Attached_document_code')
            if code is not None and code.text == '6022':
                chassis_doc = doc
                break

        assert chassis_doc is not None, "Document châssis 6022 non trouvé"

        # Vérifier les champs du document
        doc_name = chassis_doc.find('Attached_document_name')
        assert doc_name is not None and doc_name.text == 'CHASSIS MOTOS'

        doc_ref = chassis_doc.find('Attached_document_reference')
        assert doc_ref is not None and doc_ref.text == 'SUZUKI123456789AB'

        doc_rule = chassis_doc.find('Attached_document_from_rule')
        assert doc_rule is not None and doc_rule.text == '1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
