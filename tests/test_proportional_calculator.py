"""
Tests unitaires pour le module proportional_calculator.py

Teste l'algorithme du reste le plus grand et la répartition proportionnelle.

Auteur: SuperZ AI
Date: 2025-01-28
"""

import pytest
import sys
from pathlib import Path

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from proportional_calculator import ProportionalCalculator
from models import RFCVData, Valuation, Item, ValuationItem, Tarification, CurrencyAmount, Financial


class TestDistributeProportionally:
    """Tests de la méthode distribute_proportionally"""

    def setup_method(self):
        """Initialise un calculateur pour chaque test"""
        self.calculator = ProportionalCalculator()

    def test_articles_identiques_simple(self):
        """Test avec articles identiques - cas simple"""
        # 3 articles à 100 USD, total à répartir: 300 USD
        fob_articles = [100.0, 100.0, 100.0]
        fob_total = 300.0
        total_to_distribute = 300.0

        result = self.calculator.distribute_proportionally(
            total_amount=total_to_distribute,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Chaque article devrait recevoir 100
        assert result == [100, 100, 100]
        assert sum(result) == 300

    def test_methode_du_reste_35_articles(self):
        """
        Test méthode du reste le plus grand - 35 articles identiques.

        Cas réel RFCV OT_M_2025_03475:
        - FOB total: 12683.65 USD
        - FRET total: 2000.00 USD
        - 35 articles à 362.39 USD chacun

        Valeur exacte par article: 57.142857...
        floor(57.142857) = 57
        35 × 57 = 1995 (perte de 5 unités)

        La méthode du reste doit distribuer +1 aux 5 articles ayant
        les plus grandes décimales (0.142857 pour tous → 5 premiers)
        """
        fob_articles = [362.39] * 35
        fob_total = 12683.65
        fret_total = 2000.00

        result = self.calculator.distribute_proportionally(
            total_amount=fret_total,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Vérifier la somme exacte
        assert sum(result) == 2000, f"Somme attendue: 2000, obtenue: {sum(result)}"

        # Compter les valeurs 57 et 58
        count_57 = result.count(57)
        count_58 = result.count(58)

        assert count_57 == 30, f"Attendu 30 articles à 57, obtenu {count_57}"
        assert count_58 == 5, f"Attendu 5 articles à 58, obtenu {count_58}"

    def test_articles_differents(self):
        """Test avec articles de FOB différents"""
        # Articles: 100, 200, 300 USD (total = 600)
        # Répartir 120 USD
        fob_articles = [100.0, 200.0, 300.0]
        fob_total = 600.0
        total_to_distribute = 120.0

        result = self.calculator.distribute_proportionally(
            total_amount=total_to_distribute,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Proportions attendues: 20, 40, 60
        assert result == [20, 40, 60]
        assert sum(result) == 120

    def test_total_zero(self):
        """Test avec total à répartir = 0"""
        fob_articles = [100.0, 200.0, 300.0]
        fob_total = 600.0
        total_to_distribute = 0.0

        result = self.calculator.distribute_proportionally(
            total_amount=total_to_distribute,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        assert result == [0, 0, 0]
        assert sum(result) == 0

    def test_fob_total_zero_raise_error(self):
        """Test que FOB total = 0 lève une erreur"""
        fob_articles = [0.0, 0.0, 0.0]
        fob_total = 0.0
        total_to_distribute = 100.0

        with pytest.raises(ValueError, match="FOB total ne peut pas être zéro"):
            self.calculator.distribute_proportionally(
                total_amount=total_to_distribute,
                item_fobs=fob_articles,
                fob_total=fob_total
            )

    def test_liste_vide_raise_error(self):
        """Test que liste vide lève une erreur"""
        fob_articles = []
        fob_total = 100.0
        total_to_distribute = 100.0

        with pytest.raises(ValueError, match="La liste des FOB articles ne peut pas être vide"):
            self.calculator.distribute_proportionally(
                total_amount=total_to_distribute,
                item_fobs=fob_articles,
                fob_total=fob_total
            )

    def test_poids_brut_exemple_reel(self):
        """Test répartition poids brut - exemple réel RFCV"""
        # 35 articles, poids brut total: 22797 KG
        fob_articles = [362.39] * 35
        fob_total = 12683.65
        poids_brut_total = 22797.0

        result = self.calculator.distribute_proportionally(
            total_amount=poids_brut_total,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Vérifier somme exacte
        assert sum(result) == 22797

        # Valeur exacte: 651.342857...
        # Majorité devrait être 651, quelques-uns 652
        assert 651 in result
        assert 652 in result

    def test_poids_net_exemple_reel(self):
        """Test répartition poids net - exemple réel RFCV"""
        # 35 articles, poids net total: 22227 KG
        fob_articles = [362.39] * 35
        fob_total = 12683.65
        poids_net_total = 22227.0

        result = self.calculator.distribute_proportionally(
            total_amount=poids_net_total,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Vérifier somme exacte
        assert sum(result) == 22227

        # Valeur exacte: 635.057143...
        # Majorité devrait être 635, quelques-uns 636
        assert 635 in result
        assert 636 in result

    def test_assurance_exemple_reel(self):
        """Test répartition assurance - exemple réel RFCV"""
        # 35 articles, assurance totale: 44.05 XOF
        fob_articles = [362.39] * 35
        fob_total = 12683.65
        assurance_total = 44.05

        result = self.calculator.distribute_proportionally(
            total_amount=assurance_total,
            item_fobs=fob_articles,
            fob_total=fob_total
        )

        # Vérifier somme exacte
        assert sum(result) == 44

        # Valeur exacte: 1.258571...
        # Majorité devrait être 1, quelques-uns 2
        assert 1 in result
        assert 2 in result


class TestCurrencyAmount:
    """Tests de création des objets CurrencyAmount"""

    def setup_method(self):
        """Initialise un calculateur pour chaque test"""
        self.calculator = ProportionalCalculator()

    def test_create_currency_amount_xof(self):
        """Test création CurrencyAmount en XOF (monnaie nationale)"""
        result = self.calculator._create_currency_amount(
            amount=100.0,
            currency_code="XOF"
        )

        assert result.amount_national == 100.0
        # Pour XOF: amount_foreign doit être égal à amount_national (format ASYCUDA)
        assert result.amount_foreign == 100.0
        assert result.currency_code == "XOF"
        assert result.currency_name == "Franc CFA"
        assert result.currency_rate == 1.0

    def test_create_currency_amount_usd(self):
        """Test création CurrencyAmount en USD (devise étrangère)"""
        result = self.calculator._create_currency_amount(
            amount=57.0,
            currency_code="USD",
            currency_rate=575.78
        )

        assert result.amount_national is None
        assert result.amount_foreign == 57.0
        assert result.currency_code == "USD"
        assert result.currency_rate == 575.78

    def test_create_currency_amount_eur(self):
        """Test création CurrencyAmount en EUR (devise étrangère)"""
        result = self.calculator._create_currency_amount(
            amount=50.0,
            currency_code="EUR",
            currency_rate=655.96
        )

        assert result.amount_national is None
        assert result.amount_foreign == 50.0
        assert result.currency_code == "EUR"


class TestApplyToRFCV:
    """Tests de la méthode apply_to_rfcv"""

    def setup_method(self):
        """Initialise un calculateur et des données de test"""
        self.calculator = ProportionalCalculator()

    def test_apply_to_rfcv_complet(self):
        """Test application complète sur RFCVData avec tous les totaux"""
        # Créer RFCVData avec totaux globaux
        rfcv_data = RFCVData()

        rfcv_data.financial = Financial(
            currency_code="USD",
            exchange_rate=575.78
        )

        rfcv_data.valuation = Valuation(
            gross_weight=22797.0,
            net_weight=22227.0,
            external_freight=CurrencyAmount(
                amount_foreign=2000.0,
                currency_code="USD",
                currency_rate=575.78
            ),
            insurance=CurrencyAmount(
                amount_national=44.05,
                currency_code="XOF",
                currency_rate=1.0
            )
        )

        # Créer 35 articles identiques
        for i in range(35):
            item = Item()
            item.tarification = Tarification(item_price=362.39)
            item.valuation_item = ValuationItem()
            rfcv_data.items.append(item)

        # Appliquer les calculs
        result = self.calculator.apply_to_rfcv(rfcv_data)

        # Vérifier que les calculs ont été appliqués
        assert len(result.items) == 35

        # Vérifier FRET
        fret_articles = [
            item.valuation_item.external_freight.amount_foreign
            for item in result.items
        ]
        assert sum(fret_articles) == 2000.0
        assert all(57 <= f <= 58 for f in fret_articles)

        # Vérifier ASSURANCE (en XOF)
        assurance_articles = [
            item.valuation_item.insurance.amount_national
            for item in result.items
        ]
        assert sum(assurance_articles) == 44.0
        assert all(1 <= a <= 2 for a in assurance_articles)

        # Vérifier POIDS BRUT
        poids_brut_articles = [
            item.valuation_item.gross_weight
            for item in result.items
        ]
        assert sum(poids_brut_articles) == 22797.0
        assert all(651 <= p <= 652 for p in poids_brut_articles)

        # Vérifier POIDS NET
        poids_net_articles = [
            item.valuation_item.net_weight
            for item in result.items
        ]
        assert sum(poids_net_articles) == 22227.0
        assert all(635 <= p <= 636 for p in poids_net_articles)

    def test_apply_to_rfcv_valeurs_manquantes(self):
        """Test avec valeurs globales manquantes (None)"""
        rfcv_data = RFCVData()

        rfcv_data.financial = Financial(currency_code="USD")

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

        # Appliquer les calculs
        result = self.calculator.apply_to_rfcv(rfcv_data)

        # Vérifier que seul gross_weight a été calculé
        for item in result.items:
            assert item.valuation_item.gross_weight is not None
            assert item.valuation_item.net_weight is None
            assert item.valuation_item.external_freight is None
            assert item.valuation_item.insurance is None

    def test_apply_to_rfcv_sans_articles(self):
        """Test avec RFCVData sans articles"""
        rfcv_data = RFCVData()
        rfcv_data.valuation = Valuation(gross_weight=1000.0)
        rfcv_data.items = []

        # Ne devrait pas planter
        result = self.calculator.apply_to_rfcv(rfcv_data)
        assert len(result.items) == 0

    def test_apply_to_rfcv_devise_eur(self):
        """Test avec devise EUR au lieu de USD"""
        rfcv_data = RFCVData()

        rfcv_data.financial = Financial(
            currency_code="EUR",
            exchange_rate=655.96
        )

        rfcv_data.valuation = Valuation(
            external_freight=CurrencyAmount(
                amount_foreign=1000.0,
                currency_code="EUR",
                currency_rate=655.96
            )
        )

        # 2 articles
        for i in range(2):
            item = Item()
            item.tarification = Tarification(item_price=500.0)
            item.valuation_item = ValuationItem()
            rfcv_data.items.append(item)

        # Appliquer les calculs
        result = self.calculator.apply_to_rfcv(rfcv_data)

        # Vérifier que la devise EUR est utilisée
        for item in result.items:
            assert item.valuation_item.external_freight.currency_code == "EUR"
            assert item.valuation_item.external_freight.amount_foreign == 500.0


if __name__ == "__main__":
    # Exécuter les tests
    pytest.main([__file__, "-v", "--tb=short"])
