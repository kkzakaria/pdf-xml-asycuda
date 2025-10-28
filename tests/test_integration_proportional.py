"""
Tests d'intégration bout-en-bout pour le calcul proportionnel

Teste le pipeline complet:
1. Extraction PDF (pdf_extractor.py)
2. Parsing RFCV (rfcv_parser.py)
3. Calcul proportionnel (proportional_calculator.py)
4. Vérification cohérence totaux

Auteur: SuperZ AI
Date: 2025-01-28
"""

import pytest
import sys
from pathlib import Path

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from rfcv_parser import RFCVParser
from models import RFCVData


class TestIntegrationProportional:
    """Tests d'intégration du pipeline complet avec calcul proportionnel"""

    @pytest.fixture
    def rfcv_test_path(self):
        """Retourne le chemin vers la RFCV de test"""
        # RFCV de test: OT_M_2025_03475 avec 35 articles identiques
        test_pdf = Path(__file__).parent.parent / 'asycuda-extraction' / 'OT_M_2025_03475_BL_2025_03320_RFCV_v1.pdf'
        if test_pdf.exists():
            return str(test_pdf)
        else:
            pytest.skip(f"RFCV de test non disponible: {test_pdf}")

    def test_pipeline_complet(self, rfcv_test_path):
        """Test du pipeline complet: PDF → Parsing → Calcul proportionnel"""
        # Parse la RFCV (inclut automatiquement le calcul proportionnel)
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Vérifications de base
        assert rfcv_data is not None
        assert rfcv_data.valuation is not None
        assert len(rfcv_data.items) > 0

        # Vérifier que les totaux globaux ont été extraits
        assert rfcv_data.valuation.gross_weight is not None, "Poids brut total non extrait"
        assert rfcv_data.valuation.net_weight is not None, "Poids net total non extrait"
        assert rfcv_data.valuation.external_freight is not None, "FRET total non extrait"
        assert rfcv_data.valuation.insurance is not None, "ASSURANCE totale non extraite"

        # Vérifier que les articles ont des valeurs calculées
        for item in rfcv_data.items:
            assert item.valuation_item is not None, "ValuationItem manquant"
            assert item.valuation_item.external_freight is not None, "FRET article non calculé"
            assert item.valuation_item.insurance is not None, "ASSURANCE article non calculée"
            assert item.valuation_item.gross_weight is not None, "POIDS BRUT article non calculé"
            assert item.valuation_item.net_weight is not None, "POIDS NET article non calculé"

    def test_coherence_fret(self, rfcv_test_path):
        """Vérifie que sum(FRET_articles) == FRET_total"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Total global
        fret_total = rfcv_data.valuation.external_freight.amount_foreign

        # Somme des articles
        fret_articles_sum = sum(
            item.valuation_item.external_freight.amount_foreign
            for item in rfcv_data.items
        )

        # Vérifier cohérence exacte
        assert fret_articles_sum == fret_total, (
            f"Incohérence FRET: sum(articles)={fret_articles_sum} != total={fret_total}"
        )

    def test_coherence_assurance(self, rfcv_test_path):
        """Vérifie que sum(ASSURANCE_articles) == ASSURANCE_total"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Total global (en XOF)
        assurance_total = rfcv_data.valuation.insurance.amount_national

        # Somme des articles
        assurance_articles_sum = sum(
            item.valuation_item.insurance.amount_national
            for item in rfcv_data.items
        )

        # Arrondir au entier le plus proche (car sum peut avoir des arrondis)
        assurance_total_rounded = round(assurance_total)
        assurance_sum_rounded = round(assurance_articles_sum)

        # Vérifier cohérence exacte
        assert assurance_sum_rounded == assurance_total_rounded, (
            f"Incohérence ASSURANCE: sum(articles)={assurance_sum_rounded} != total={assurance_total_rounded}"
        )

    def test_coherence_poids_brut(self, rfcv_test_path):
        """Vérifie que sum(POIDS_BRUT_articles) == POIDS_BRUT_total"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Total global
        poids_brut_total = rfcv_data.valuation.gross_weight

        # Somme des articles
        poids_brut_articles_sum = sum(
            item.valuation_item.gross_weight
            for item in rfcv_data.items
        )

        # Vérifier cohérence exacte
        assert poids_brut_articles_sum == poids_brut_total, (
            f"Incohérence POIDS BRUT: sum(articles)={poids_brut_articles_sum} != total={poids_brut_total}"
        )

    def test_coherence_poids_net(self, rfcv_test_path):
        """Vérifie que sum(POIDS_NET_articles) == POIDS_NET_total"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Total global
        poids_net_total = rfcv_data.valuation.net_weight

        # Somme des articles
        poids_net_articles_sum = sum(
            item.valuation_item.net_weight
            for item in rfcv_data.items
        )

        # Vérifier cohérence exacte
        assert poids_net_articles_sum == poids_net_total, (
            f"Incohérence POIDS NET: sum(articles)={poids_net_articles_sum} != total={poids_net_total}"
        )

    def test_devises_correctes(self, rfcv_test_path):
        """Vérifie que les devises sont correctes (FOB/FRET dans devise RFCV, ASSURANCE en XOF)"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Récupérer la devise de la RFCV
        currency_code = rfcv_data.financial.currency_code

        # Vérifier FRET
        assert rfcv_data.valuation.external_freight.currency_code == currency_code, (
            f"Devise FRET incorrecte: {rfcv_data.valuation.external_freight.currency_code} != {currency_code}"
        )

        # Vérifier ASSURANCE (doit être XOF)
        assert rfcv_data.valuation.insurance.currency_code == 'XOF', (
            f"Devise ASSURANCE incorrecte: {rfcv_data.valuation.insurance.currency_code} != XOF"
        )

        # Vérifier devises des articles
        for i, item in enumerate(rfcv_data.items):
            # FRET article
            assert item.valuation_item.external_freight.currency_code == currency_code, (
                f"Article {i+1}: Devise FRET incorrecte"
            )

            # ASSURANCE article (toujours XOF)
            assert item.valuation_item.insurance.currency_code == 'XOF', (
                f"Article {i+1}: Devise ASSURANCE incorrecte"
            )

    def test_valeurs_positives(self, rfcv_test_path):
        """Vérifie que toutes les valeurs calculées sont positives ou nulles"""
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        for i, item in enumerate(rfcv_data.items):
            # FRET
            fret = item.valuation_item.external_freight.amount_foreign
            assert fret >= 0, f"Article {i+1}: FRET négatif ({fret})"

            # ASSURANCE
            assurance = item.valuation_item.insurance.amount_national
            assert assurance >= 0, f"Article {i+1}: ASSURANCE négative ({assurance})"

            # POIDS BRUT
            poids_brut = item.valuation_item.gross_weight
            assert poids_brut >= 0, f"Article {i+1}: POIDS BRUT négatif ({poids_brut})"

            # POIDS NET
            poids_net = item.valuation_item.net_weight
            assert poids_net >= 0, f"Article {i+1}: POIDS NET négatif ({poids_net})"

    def test_distribution_equilibree(self, rfcv_test_path):
        """
        Vérifie que la distribution est équilibrée pour articles identiques

        Pour 35 articles identiques (FOB = 362.39 USD chacun):
        - FRET: 30 articles à 57, 5 articles à 58
        - POIDS BRUT: majorité 651, quelques 652
        - POIDS NET: majorité 635, quelques 636
        """
        parser = RFCVParser(rfcv_test_path)
        rfcv_data = parser.parse()

        # Extraire les valeurs FRET de tous les articles
        fret_values = [
            item.valuation_item.external_freight.amount_foreign
            for item in rfcv_data.items
        ]

        # Vérifier que les valeurs sont proches (différence max de 1)
        min_fret = min(fret_values)
        max_fret = max(fret_values)
        assert max_fret - min_fret <= 1, (
            f"Distribution FRET déséquilibrée: min={min_fret}, max={max_fret}"
        )

        # Même vérification pour poids brut
        poids_brut_values = [
            item.valuation_item.gross_weight
            for item in rfcv_data.items
        ]
        min_brut = min(poids_brut_values)
        max_brut = max(poids_brut_values)
        assert max_brut - min_brut <= 1, (
            f"Distribution POIDS BRUT déséquilibrée: min={min_brut}, max={max_brut}"
        )

    def test_cas_valeurs_manquantes(self):
        """Teste le cas où certains totaux globaux sont manquants"""
        # Créer RFCVData avec valeurs partielles
        from models import RFCVData, Valuation, Financial, Item, Tarification, ValuationItem, CurrencyAmount
        from proportional_calculator import ProportionalCalculator

        rfcv_data = RFCVData()
        rfcv_data.financial = Financial(currency_code='USD', exchange_rate=575.78)

        # Valuation avec seulement gross_weight (autres à None)
        rfcv_data.valuation = Valuation(
            gross_weight=1000.0,
            net_weight=None,
            external_freight=None,
            insurance=None
        )

        # 3 articles
        for i in range(3):
            item = Item()
            item.tarification = Tarification(item_price=100.0)
            item.valuation_item = ValuationItem()
            rfcv_data.items.append(item)

        # Appliquer calculs
        calculator = ProportionalCalculator()
        result = calculator.apply_to_rfcv(rfcv_data)

        # Vérifier que seul gross_weight a été calculé
        for item in result.items:
            assert item.valuation_item.gross_weight is not None, "Poids brut devrait être calculé"
            assert item.valuation_item.net_weight is None, "Poids net devrait rester None"
            assert item.valuation_item.external_freight is None, "FRET devrait rester None"
            assert item.valuation_item.insurance is None, "ASSURANCE devrait rester None"


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v", "--tb=short"])
