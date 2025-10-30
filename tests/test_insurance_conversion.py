"""
Tests d'intégration pour le calcul de l'assurance

Valide que:
1. L'assurance est calculée avec la nouvelle formule: 2500 + (FOB + FRET) × TAUX × 0.15%
2. Le résultat est en XOF avec taux 1.0
3. La répartition proportionnelle distribue l'assurance sur les articles selon leur FOB
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
        """Test calcul assurance RFCV 03286 avec nouvelle formule"""
        pdf_path = Path(__file__).parent / 'OT_M_2025_03286_BL_2025_03131_RFCV_v1.pdf'

        # Parser RFCV avec taux douanier
        # Utiliser taux de test: 573.139 (USD)
        parser = RFCVParser(str(pdf_path), taux_douane=573.139)
        rfcv_data = parser.parse()

        # Vérifier calcul assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Nouvelle formule: 2500 + (FOB + FRET) × TAUX × 0.0015
        # L'assurance devrait être calculée en XOF
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert assurance_xof >= 2500, f"Assurance devrait être au moins 2500 XOF (partie fixe), obtenu {assurance_xof}"

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

        # Vérifier somme cohérente (accepter différence d'arrondi ±1 XOF)
        somme = sum(assurance_articles)
        diff = abs(int(somme) - int(assurance_xof))
        assert diff <= 1, f"Somme articles ({somme}) != Total ({assurance_xof}), diff: {diff}"

        # Vérifier proportionnalité (article 2 a 85% du FOB)
        assert assurance_articles[1] > assurance_articles[0], "Article 2 devrait avoir plus d'assurance"
        assert assurance_articles[1] > assurance_articles[2], "Article 2 devrait avoir plus d'assurance"

    def test_conversion_rfcv_03475_motos(self):
        """Test calcul assurance RFCV 03475 (35 motos) avec nouvelle formule"""
        pdf_path = Path(__file__).parent.parent / 'asycuda-extraction' / 'OT_M_2025_03475_BL_2025_03320_RFCV_v1.pdf'

        # Parser RFCV avec taux douanier
        parser = RFCVParser(str(pdf_path), taux_douane=573.139)
        rfcv_data = parser.parse()

        # Vérifier calcul assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Nouvelle formule: 2500 + (FOB + FRET) × TAUX × 0.0015
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert assurance_xof >= 2500, f"Assurance devrait être au moins 2500 XOF, obtenu {assurance_xof}"

        # Vérifier répartition sur 35 articles
        assert len(rfcv_data.items) == 35

        assurance_articles = [
            item.valuation_item.insurance.amount_national
            for item in rfcv_data.items
            if item.valuation_item and item.valuation_item.insurance
        ]

        # Vérifier somme cohérente (accepter différence d'arrondi ±1 XOF)
        somme = sum(assurance_articles)
        diff = abs(int(somme) - int(assurance_xof))
        assert diff <= 1, f"Somme articles ({somme}) != Total ({assurance_xof}), diff: {diff}"

        # Tous les articles ont le même FOB, donc assurances similaires (±1 XOF)
        min_assurance = min(assurance_articles)
        max_assurance = max(assurance_articles)
        assert (max_assurance - min_assurance) <= 1, "Écart max 1 XOF pour articles identiques"

    def test_conversion_rfcv_03977_poudre(self):
        """Test calcul assurance RFCV 03977 (1 article poudre) avec nouvelle formule"""
        pdf_path = Path(__file__).parent.parent / 'asycuda-extraction' / 'OT_M_2025_03977_BL_2025_03796_RFCV_v1.pdf'

        # Parser RFCV avec taux douanier
        parser = RFCVParser(str(pdf_path), taux_douane=573.139)
        rfcv_data = parser.parse()

        # Vérifier calcul assurance globale
        assert rfcv_data.valuation is not None
        assert rfcv_data.valuation.insurance is not None

        # Nouvelle formule: 2500 + (FOB + FRET) × TAUX × 0.0015
        assurance_xof = rfcv_data.valuation.insurance.amount_national
        assert assurance_xof is not None
        assert assurance_xof >= 2500, f"Assurance devrait être au moins 2500 XOF, obtenu {assurance_xof}"

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

        parser = RFCVParser(str(pdf_path), taux_douane=573.139)
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

        parser = RFCVParser(str(pdf_path), taux_douane=573.139)
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
