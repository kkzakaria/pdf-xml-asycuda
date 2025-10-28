"""
Tests unitaires pour la détection et extraction des numéros de châssis
"""
import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from hs_code_rules import HSCodeAnalyzer
from rfcv_parser import RFCVParser


class TestHSCodeAnalyzer:
    """Tests pour l'analyseur de codes HS"""

    def test_chassis_required_8701_tractor(self):
        """Test: Code HS 8701 (tracteur) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('87010000', '')
        assert result['required'] is True
        assert result['confidence'] == 1.0
        assert result['source'] == 'hs_code'
        assert 'Tracteur' in result['category']

    def test_chassis_required_8703_car(self):
        """Test: Code HS 8703 (voiture) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('87030000', '')
        assert result['required'] is True
        assert result['confidence'] == 1.0

    def test_chassis_required_8704_truck_tricycle(self):
        """Test: Code HS 8704 (camion/tricycle) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('87043119', '')
        assert result['required'] is True
        assert 'marchandises' in result['category'].lower()

    def test_chassis_required_8711_motorcycle(self):
        """Test: Code HS 8711 (moto) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('87112091', '')
        assert result['required'] is True

    def test_chassis_required_8427_forklift(self):
        """Test: Code HS 8427 (chariot manutention) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('84270000', '')
        assert result['required'] is True
        assert 'Chariot' in result['category']

    def test_chassis_required_8429_bulldozer(self):
        """Test: Code HS 8429 (engin travaux publics) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('84290000', '')
        assert result['required'] is True
        assert 'travaux' in result['category'].lower()

    def test_chassis_required_8716_trailer(self):
        """Test: Code HS 8716 (remorque) nécessite châssis"""
        result = HSCodeAnalyzer.requires_chassis('87160000', '')
        assert result['required'] is True
        assert 'Remorque' in result['category']

    def test_no_chassis_required_2803_chemical(self):
        """Test: Code HS 2803 (produit chimique) ne nécessite PAS de châssis"""
        result = HSCodeAnalyzer.requires_chassis('28030000', 'CARBON BLACK')
        assert result['required'] is False
        assert result['confidence'] == 1.0
        assert result['source'] == 'hs_code'

    def test_no_chassis_required_8517_electronics(self):
        """Test: Code HS 8517 (électronique) ne nécessite PAS de châssis"""
        result = HSCodeAnalyzer.requires_chassis('85171200', 'SMARTPHONE')
        assert result['required'] is False

    def test_fallback_keywords_motorcycle(self):
        """Test: Détection par mot-clé MOTORCYCLE si code HS absent"""
        result = HSCodeAnalyzer.requires_chassis(None, 'MOTORCYCLE HONDA')
        assert result['required'] is True
        assert result['confidence'] == 0.7
        assert result['source'] == 'keywords'

    def test_fallback_keywords_tricycle(self):
        """Test: Détection par mot-clé TRICYCLE si code HS absent"""
        result = HSCodeAnalyzer.requires_chassis('', 'TRICYCLE AP150ZH-20')
        assert result['required'] is True
        assert 'TRICYCLE' in result['category']

    def test_no_detection_no_code_no_keywords(self):
        """Test: Aucune détection sans code HS ni mots-clés"""
        result = HSCodeAnalyzer.requires_chassis(None, 'POUDRE NOIRE')
        assert result['required'] is False
        assert result['source'] == 'none'


class TestChassisExtraction:
    """Tests pour l'extraction de numéros de châssis"""

    def test_extract_tricycle_chassis_13chars(self):
        """Test: Extraction châssis tricycle (13 caractères)"""
        parser = RFCVParser.__new__(RFCVParser)  # Créer instance sans __init__
        chassis = parser._extract_chassis_number("TRICYCLE AP150ZH-20 LLCLHJL03SP420331")
        assert chassis == "LLCLHJL03SP420331"
        assert len(chassis) == 17

    def test_extract_motorcycle_vin_17chars(self):
        """Test: Extraction VIN moto (17 caractères)"""
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number("MOTORCYCLE LRFPCJLDIS0F18969")
        assert chassis == "LRFPCJLDIS0F18969"
        assert len(chassis) == 17

    def test_extract_chassis_with_prefix_ch(self):
        """Test: Extraction avec préfixe CH:"""
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number("MOTO CH: ABC123DEF456GHI")
        assert chassis == "ABC123DEF456GHI"

    def test_extract_chassis_with_prefix_vin(self):
        """Test: Extraction avec préfixe VIN:"""
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number("VEHICLE VIN:WBAPH9105WP123456")
        assert chassis == "WBAPH9105WP123456"

    def test_no_extraction_no_chassis(self):
        """Test: Aucun châssis si absent de la description"""
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number("CARBON BLACK POWDER")
        assert chassis is None

    def test_no_extraction_too_short(self):
        """Test: Rejet si trop court (<13 caractères)"""
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number("MOTO ABC123")
        assert chassis is None

    def test_extraction_filters_hs_code(self):
        """Test: Filtrage des faux positifs (codes HS)"""
        parser = RFCVParser.__new__(RFCVParser)
        # 87043119 a des lettres ET chiffres mais est un code HS
        # Notre validation devrait accepter car il a lettres + chiffres
        chassis = parser._extract_chassis_number("TRICYCLE 87043119 LLCLHJL03SP420331")
        # Devrait extraire le châssis, pas le code HS
        assert chassis == "LLCLHJL03SP420331"


class TestIntegrationChassisDetection:
    """Tests d'intégration pour la détection complète"""

    def test_integration_tricycle_with_chassis(self):
        """Test: Tricycle avec code HS 8704 et châssis détecté"""
        hs_code = '87043119'
        description = 'TRICYCLE AP150ZH-20 LLCLHJL03SP420331'

        # Analyse HS
        chassis_info = HSCodeAnalyzer.requires_chassis(hs_code, description)
        assert chassis_info['required'] is True

        # Extraction
        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number(description)
        assert chassis == 'LLCLHJL03SP420331'

    def test_integration_motorcycle_with_chassis(self):
        """Test: Moto avec code HS 8711 et VIN"""
        hs_code = '87112091'
        description = 'MOTORCYCLE FENGHAO LRFPCJLDIS0F18969'

        chassis_info = HSCodeAnalyzer.requires_chassis(hs_code, description)
        assert chassis_info['required'] is True

        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number(description)
        assert chassis == 'LRFPCJLDIS0F18969'

    def test_integration_carbon_no_chassis(self):
        """Test: Produit chimique sans châssis"""
        hs_code = '28030000'
        description = 'CARBON BLACK POWDER'

        chassis_info = HSCodeAnalyzer.requires_chassis(hs_code, description)
        assert chassis_info['required'] is False

        parser = RFCVParser.__new__(RFCVParser)
        chassis = parser._extract_chassis_number(description)
        assert chassis is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
