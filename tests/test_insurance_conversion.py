"""
Tests d'intégration pour la conversion devise de l'assurance

Valide que:
1. L'assurance section 21 est extraite en devise étrangère (section 16)
2. Elle est multipliée par le taux de change (section 17)
3. La répartition proportionnelle utilise la valeur convertie en XOF
"""
import pytest
import sys
from pathlib import Path

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rfcv_parser import RFCVParser


class TestInsuranceConversion:
    """Tests de conversion devise de l'assurance"""

    def test_conversion_rfcv_03286(self):
        """Test conversion assurance RFCV 03286"""
        pdf_path = Path(__file__).parent / 'OT_M_2025_03286_BL_2025_03131_RFCV_v1.pdf'

        # Parser RFCV
        parser = RFCVParser(str(pdf_path))
        rfcv_data = parser.parse()

        # Vérifier extraction assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Valeurs attendues:
        # - Assurance section 21: 67.32 USD
        # - Taux section 17: 566.67
        # - Assurance XOF: 67.32 × 566.67 = 38,148.22 XOF
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert 38140 <= assurance_xof <= 38160, f"Attendu ~38,148 XOF, obtenu {assurance_xof}"

        # Vérifier que c'est en XOF
        assert rfcv_data.valuation.insurance.currency_code == 'XOF'
        assert rfcv_data.valuation.insurance.currency_rate == 1.0

        # Vérifier répartition sur articles
        assert len(rfcv_data.items) == 3

        assurance_articles = [
            item.valuation_item.insurance.amount_national
            for item in rfcv_data.items
            if item.valuation_item and item.valuation_item.insurance
        ]

        # Vérifier somme cohérente
        somme = sum(assurance_articles)
        assert int(somme) == int(assurance_xof), f"Somme articles ({somme}) != Total ({assurance_xof})"

        # Vérifier proportionnalité (article 2 a 85% du FOB)
        assert assurance_articles[1] > assurance_articles[0], "Article 2 devrait avoir plus d'assurance"
        assert assurance_articles[1] > assurance_articles[2], "Article 2 devrait avoir plus d'assurance"

    def test_conversion_rfcv_03475_motos(self):
        """Test conversion assurance RFCV 03475 (35 motos)"""
        pdf_path = Path(__file__).parent.parent / 'asycuda-extraction' / 'OT_M_2025_03475_BL_2025_03320_RFCV_v1.pdf'

        # Parser RFCV
        parser = RFCVParser(str(pdf_path))
        rfcv_data = parser.parse()

        # Vérifier extraction assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Valeurs attendues:
        # - Assurance section 21: 44.05 USD
        # - Taux section 17: 567.27
        # - Assurance XOF: 44.05 × 567.27 = 24,988.24 XOF
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert 24980 <= assurance_xof <= 25000, f"Attendu ~24,988 XOF, obtenu {assurance_xof}"

        # Vérifier répartition sur 35 articles
        assert len(rfcv_data.items) == 35

        assurance_articles = [
            item.valuation_item.insurance.amount_national
            for item in rfcv_data.items
            if item.valuation_item and item.valuation_item.insurance
        ]

        # Vérifier somme cohérente
        somme = sum(assurance_articles)
        assert int(somme) == int(assurance_xof), f"Somme articles ({somme}) != Total ({assurance_xof})"

        # Tous les articles ont le même FOB, donc assurances similaires (±1 XOF)
        min_assurance = min(assurance_articles)
        max_assurance = max(assurance_articles)
        assert (max_assurance - min_assurance) <= 1, "Écart max 1 XOF pour articles identiques"

    def test_conversion_rfcv_03977_poudre(self):
        """Test conversion assurance RFCV 03977 (1 article poudre)"""
        pdf_path = Path(__file__).parent.parent / 'asycuda-extraction' / 'OT_M_2025_03977_BL_2025_03796_RFCV_v1.pdf'

        # Parser RFCV
        parser = RFCVParser(str(pdf_path))
        rfcv_data = parser.parse()

        # Vérifier extraction assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Valeurs attendues:
        # - Assurance section 21: 57.36 USD
        # - Taux section 17: 575.7807
        # - Assurance XOF: 57.36 × 575.7807 = 33,026.78 XOF
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert 33020 <= assurance_xof <= 33035, f"Attendu ~33,027 XOF, obtenu {assurance_xof}"

        # Vérifier répartition sur 1 article
        assert len(rfcv_data.items) == 1

        # L'article unique devrait avoir toute l'assurance
        item1 = rfcv_data.items[0]
        assert item1.valuation_item is not None
        assert item1.valuation_item.insurance is not None

        assurance_article = item1.valuation_item.insurance.amount_national
        # Accepter différence d'arrondi ±1 XOF (méthode du reste le plus grand)
        diff = abs(assurance_article - assurance_xof)
        assert diff <= 1, f"Article unique doit avoir toute l'assurance (diff: {diff} XOF)"


class TestInsuranceFormats:
    """Tests des formats XOF (amount_national = amount_foreign)"""

    def test_format_xof_assurance_globale(self):
        """Test format XOF pour assurance globale"""
        pdf_path = Path(__file__).parent / 'OT_M_2025_03286_BL_2025_03131_RFCV_v1.pdf'

        parser = RFCVParser(str(pdf_path))
        rfcv_data = parser.parse()

        insurance = rfcv_data.valuation.insurance
        assert insurance is not None

        # Pour XOF: amount_national doit égaler amount_foreign
        assert insurance.amount_national == insurance.amount_foreign
        assert insurance.currency_code == 'XOF'
        assert insurance.currency_rate == 1.0

    def test_format_xof_assurance_articles(self):
        """Test format XOF pour assurance par article"""
        pdf_path = Path(__file__).parent / 'OT_M_2025_03286_BL_2025_03131_RFCV_v1.pdf'

        parser = RFCVParser(str(pdf_path))
        rfcv_data = parser.parse()

        for idx, item in enumerate(rfcv_data.items, 1):
            assert item.valuation_item is not None
            assert item.valuation_item.insurance is not None

            insurance = item.valuation_item.insurance

            # Pour XOF: amount_national doit égaler amount_foreign
            assert insurance.amount_national == insurance.amount_foreign, \
                f"Article {idx}: amount_national != amount_foreign"
            assert insurance.currency_code == 'XOF'
            assert insurance.currency_rate == 1.0


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v", "--tb=short"])
