"""
Tests unitaires pour la distinction des codes de document châssis
Code 6022: Motos (HS 8711)
Code 6122: Tricycles et autres véhicules
"""
import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from hs_code_rules import HSCodeAnalyzer


class TestChassisDocumentCode:
    """Tests pour get_chassis_document_code()"""

    def test_motorcycle_hs_code_8711(self):
        """Code HS 8711 → code document 6022 (motos)"""
        result = HSCodeAnalyzer.get_chassis_document_code('87112090', 'MOTORCYCLE')
        assert result == '6022'

    def test_motorcycle_hs_code_8711_with_dots(self):
        """Code HS 8711 avec points → code document 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code('8711.20.90.00', 'MOTORCYCLE YAMAHA')
        assert result == '6022'

    def test_tricycle_hs_code_8704(self):
        """Code HS 8704 (tricycle) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87042110', 'TRICYCLE AP150ZH')
        assert result == '6122'

    def test_car_hs_code_8703(self):
        """Code HS 8703 (voiture) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87032310', 'CAR TOYOTA')
        assert result == '6122'

    def test_truck_hs_code_8704(self):
        """Code HS 8704 (camion) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87043190', 'TRUCK ISUZU')
        assert result == '6122'

    def test_tractor_hs_code_8701(self):
        """Code HS 8701 (tracteur) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87011000', 'TRACTOR MASSEY FERGUSON')
        assert result == '6122'

    def test_bus_hs_code_8702(self):
        """Code HS 8702 (bus) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87021090', 'BUS MERCEDES')
        assert result == '6122'

    def test_bulldozer_hs_code_8429(self):
        """Code HS 8429 (bulldozer) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('84294100', 'BULLDOZER CATERPILLAR')
        assert result == '6122'

    def test_trailer_hs_code_8716(self):
        """Code HS 8716 (remorque) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87163100', 'TRAILER')
        assert result == '6122'

    def test_forklift_hs_code_8427(self):
        """Code HS 8427 (chariot) → code document 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('84272090', 'FORKLIFT')
        assert result == '6122'

    def test_fallback_motorcycle_keyword(self):
        """Fallback: mot-clé MOTORCYCLE sans code HS → 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'MOTORCYCLE HONDA CBR')
        assert result == '6022'

    def test_fallback_moto_keyword(self):
        """Fallback: mot-clé MOTO sans code HS → 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'MOTO YAMAHA YZF-R6')
        assert result == '6022'

    def test_fallback_scooter_keyword(self):
        """Fallback: mot-clé SCOOTER sans code HS → 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'SCOOTER VESPA')
        assert result == '6022'

    def test_fallback_motocycle_keyword(self):
        """Fallback: mot-clé MOTOCYCLE (variante orthographique) → 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'MOTOCYCLE KAWASAKI')
        assert result == '6022'

    def test_fallback_tricycle_without_hs(self):
        """Fallback: TRICYCLE sans code HS → 6122 (défaut)"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'TRICYCLE AP150ZK-20')
        assert result == '6122'

    def test_fallback_truck_without_hs(self):
        """Fallback: TRUCK sans code HS → 6122 (défaut)"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'TRUCK VOLVO FH16')
        assert result == '6122'

    def test_fallback_car_without_hs(self):
        """Fallback: CAR sans code HS → 6122 (défaut)"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'CAR BMW X5')
        assert result == '6122'

    def test_default_when_no_info(self):
        """Aucune info → 6122 (défaut pour véhicules)"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, '')
        assert result == '6122'

    def test_non_vehicle_hs_code(self):
        """Code HS non-véhicule (ex: électronique) → 6122 par défaut"""
        result = HSCodeAnalyzer.get_chassis_document_code('85171200', 'SMARTPHONE SAMSUNG')
        assert result == '6122'

    def test_hs_priority_over_keyword(self):
        """Code HS prioritaire sur mots-clés: HS 8704 + "MOTO" → 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code('87042110', 'TRICYCLE MOTO')
        assert result == '6122'

    def test_motorcycle_mixed_case(self):
        """Mot-clé MOTO en minuscule → détection 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'moto honda wave 125')
        assert result == '6022'

    def test_scooter_in_sentence(self):
        """Mot-clé SCOOTER dans phrase → détection 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(None, 'Electric scooter XIAOMI MI3')
        assert result == '6022'

    def test_hs_8711_various_formats(self):
        """Code HS 8711 différents formats → tous 6022"""
        formats = [
            '8711',
            '87110000',
            '8711.00.00',
            '8711.20.90.00',
            '8711 30 19 00'
        ]
        for hs_format in formats:
            result = HSCodeAnalyzer.get_chassis_document_code(hs_format, 'VEHICLE')
            assert result == '6022', f"Failed for format: {hs_format}"

    def test_real_world_motorcycle_description(self):
        """Description réelle de moto → 6022"""
        result = HSCodeAnalyzer.get_chassis_document_code(
            '87112090',
            'MOTORCYCLE LRFPCJLDIS0F18969'
        )
        assert result == '6022'

    def test_real_world_tricycle_description(self):
        """Description réelle de tricycle → 6122"""
        result = HSCodeAnalyzer.get_chassis_document_code(
            '87042110',
            'TRICYCLE AP150ZH-20 LLCLHJL03SP420331'
        )
        assert result == '6122'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
