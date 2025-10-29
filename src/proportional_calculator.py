"""
Module de calcul de répartition proportionnelle pour RFCV → XML ASYCUDA

Ce module implémente l'algorithme du reste le plus grand (Largest Remainder Method)
pour répartir les totaux globaux (FRET, ASSURANCE, POIDS) sur les articles individuels
proportionnellement à leur FOB, tout en garantissant que:
    sum(valeurs_articles) == total_global (exactement)

Auteur: SuperZ AI
Date: 2025-01-28
"""

import math
from typing import List, Optional, Tuple

# Support both relative and absolute imports
try:
    from .models import RFCVData, Item, CurrencyAmount, ValuationItem
except ImportError:
    from models import RFCVData, Item, CurrencyAmount, ValuationItem


class ProportionalCalculator:
    """
    Calculateur de répartition proportionnelle pour données RFCV.

    Applique la méthode du reste le plus grand pour distribuer les totaux globaux
    (FRET, ASSURANCE, POIDS BRUT, POIDS NET) sur les articles individuels.
    """

    def __init__(self):
        """Initialise le calculateur."""
        pass

    def distribute_proportionally(
        self,
        total_amount: float,
        item_fobs: List[float],
        fob_total: float
    ) -> List[int]:
        """
        Répartit un total sur des articles proportionnellement à leur FOB.

        Utilise l'algorithme du reste le plus grand pour garantir que
        la somme des valeurs réparties égale exactement le total global.

        Algorithme en 5 étapes:
        1. Règle de trois: valeur_i = (total × FOB_i) / FOB_total
        2. Arrondir à l'inférieur: floor(valeur_i)
        3. Calculer parties décimales: valeur_i - floor(valeur_i)
        4. Calculer unités manquantes: total - sum(floor)
        5. Distribuer unités aux articles avec plus grandes décimales

        Args:
            total_amount: Montant total à répartir (ex: 2000.00 USD)
            item_fobs: Liste des FOB de chaque article (ex: [362.39, 362.39, ...])
            fob_total: FOB total de tous les articles (ex: 12683.65 USD)

        Returns:
            Liste des valeurs entières réparties (ex: [57, 57, ..., 58])
            Garantie: sum(résultat) == int(round(total_amount))

        Raises:
            ValueError: Si fob_total est 0 ou si les listes sont vides

        Exemple:
            >>> calculator = ProportionalCalculator()
            >>> fobs = [362.39] * 35
            >>> fret_articles = calculator.distribute_proportionally(
            ...     total_amount=2000.00,
            ...     item_fobs=fobs,
            ...     fob_total=12683.65
            ... )
            >>> sum(fret_articles)
            2000
        """
        # Validation des entrées
        if fob_total == 0:
            raise ValueError("FOB total ne peut pas être zéro")

        if not item_fobs:
            raise ValueError("La liste des FOB articles ne peut pas être vide")

        if total_amount == 0:
            # Si le total est 0, distribuer 0 partout
            return [0] * len(item_fobs)

        # Étape 1: Règle de trois pour valeurs exactes (précision maximale)
        exact_values = [
            (total_amount * fob) / fob_total
            for fob in item_fobs
        ]

        # Étape 2: Arrondir à l'inférieur
        floor_values = [math.floor(v) for v in exact_values]

        # Étape 3: Calculer parties décimales
        decimal_parts = [v - math.floor(v) for v in exact_values]

        # Étape 4: Calculer unités manquantes pour atteindre le total
        sum_floor = sum(floor_values)
        target_total = int(round(total_amount))
        missing_units = target_total - sum_floor

        # Étape 5: Distribuer les unités manquantes aux articles ayant
        # les plus grandes parties décimales
        if missing_units > 0:
            # Créer liste d'indices triés par partie décimale décroissante
            # En cas d'égalité, garder l'ordre original (stable)
            sorted_indices = sorted(
                range(len(decimal_parts)),
                key=lambda i: decimal_parts[i],
                reverse=True
            )

            # Ajouter +1 aux N premiers articles (N = missing_units)
            for i in range(min(missing_units, len(floor_values))):
                idx = sorted_indices[i]
                floor_values[idx] += 1

        return floor_values

    def _create_currency_amount(
        self,
        amount: float,
        currency_code: str,
        currency_rate: Optional[float] = None
    ) -> CurrencyAmount:
        """
        Crée un objet CurrencyAmount selon la devise.

        Args:
            amount: Montant à stocker
            currency_code: Code devise (USD, EUR, XOF, etc.)
            currency_rate: Taux de change (optionnel)

        Returns:
            CurrencyAmount avec les bons champs remplis
        """
        if currency_code == "XOF":
            # Monnaie nationale (XOF)
            # Pour ASYCUDA: XOF nécessite le même montant dans amount_national ET amount_foreign
            return CurrencyAmount(
                amount_national=amount,
                amount_foreign=amount,  # Même valeur pour XOF (taux de change = 1)
                currency_code=currency_code,
                currency_name="Franc CFA",
                currency_rate=1.0
            )
        else:
            # Devise étrangère (USD, EUR, etc.)
            return CurrencyAmount(
                amount_national=None,
                amount_foreign=amount,
                currency_code=currency_code,
                currency_name=None,  # Sera rempli par le système
                currency_rate=currency_rate
            )

    def apply_to_rfcv(self, rfcv_data: RFCVData) -> RFCVData:
        """
        Applique les calculs de répartition proportionnelle à toutes les données RFCV.

        Pour chaque article, calcule:
        - FRET: réparti selon FOB (devise RFCV section 16)
        - ASSURANCE: réparti selon FOB (toujours en XOF)
        - POIDS BRUT: réparti selon FOB (entiers en KG)
        - POIDS NET: réparti selon FOB (entiers en KG)

        Règles de gestion:
        - Si un total global est None/manquant, ne pas calculer (garder None)
        - FOB et FRET: utiliser la devise de la RFCV (section 16)
        - ASSURANCE: toujours en XOF (monnaie nationale)
        - POIDS: toujours en entiers (KG)

        Args:
            rfcv_data: Données RFCV avec totaux globaux extraits

        Returns:
            RFCVData enrichi avec valeurs calculées pour chaque article

        Exemple:
            >>> calculator = ProportionalCalculator()
            >>> rfcv_enrichi = calculator.apply_to_rfcv(rfcv_data)
            >>> # Vérifier cohérence
            >>> sum(item.valuation_item.gross_weight for item in rfcv_enrichi.items)
            22797  # == rfcv_enrichi.valuation.gross_weight
        """
        # Vérifier que les données nécessaires sont présentes
        if not rfcv_data.items:
            # Pas d'articles, rien à faire
            return rfcv_data

        if not rfcv_data.valuation:
            # Pas de valorisation globale, rien à faire
            return rfcv_data

        # Extraire les FOB de chaque article
        item_fobs = []
        for item in rfcv_data.items:
            if item.tarification and item.tarification.item_price is not None:
                item_fobs.append(item.tarification.item_price)
            else:
                # Article sans FOB, utiliser 0
                item_fobs.append(0.0)

        # Calculer FOB total depuis les articles
        fob_total = sum(item_fobs)

        if fob_total == 0:
            # Impossible de répartir si FOB total est 0
            return rfcv_data

        # Extraire la devise de la RFCV (pour FOB et FRET)
        # La devise est stockée dans financial.currency_code ou valuation.invoice.currency_code
        currency_code = "USD"  # Valeur par défaut
        currency_rate = None

        if rfcv_data.financial and rfcv_data.financial.currency_code:
            currency_code = rfcv_data.financial.currency_code
            currency_rate = rfcv_data.financial.exchange_rate
        elif rfcv_data.valuation.invoice and rfcv_data.valuation.invoice.currency_code:
            currency_code = rfcv_data.valuation.invoice.currency_code
            currency_rate = rfcv_data.valuation.invoice.currency_rate

        # === RÉPARTITION FRET (external_freight) ===
        if (rfcv_data.valuation.external_freight and
            rfcv_data.valuation.external_freight.amount_foreign is not None):

            fret_total = rfcv_data.valuation.external_freight.amount_foreign
            fret_articles = self.distribute_proportionally(
                total_amount=fret_total,
                item_fobs=item_fobs,
                fob_total=fob_total
            )

            # Affecter aux articles
            for i, item in enumerate(rfcv_data.items):
                if not item.valuation_item:
                    item.valuation_item = ValuationItem()

                item.valuation_item.external_freight = self._create_currency_amount(
                    amount=float(fret_articles[i]),
                    currency_code=currency_code,
                    currency_rate=currency_rate
                )

        # === RÉPARTITION ASSURANCE (insurance) ===
        # Toujours en XOF (monnaie nationale)
        if (rfcv_data.valuation.insurance and
            rfcv_data.valuation.insurance.amount_national is not None):

            assurance_total = rfcv_data.valuation.insurance.amount_national
            assurance_articles = self.distribute_proportionally(
                total_amount=assurance_total,
                item_fobs=item_fobs,
                fob_total=fob_total
            )

            # Affecter aux articles
            for i, item in enumerate(rfcv_data.items):
                if not item.valuation_item:
                    item.valuation_item = ValuationItem()

                item.valuation_item.insurance = self._create_currency_amount(
                    amount=float(assurance_articles[i]),
                    currency_code="XOF",
                    currency_rate=1.0
                )

        # === RÉPARTITION POIDS BRUT (gross_weight) ===
        if rfcv_data.valuation.gross_weight is not None:
            poids_brut_total = rfcv_data.valuation.gross_weight
            poids_brut_articles = self.distribute_proportionally(
                total_amount=poids_brut_total,
                item_fobs=item_fobs,
                fob_total=fob_total
            )

            # Affecter aux articles
            for i, item in enumerate(rfcv_data.items):
                if not item.valuation_item:
                    item.valuation_item = ValuationItem()

                item.valuation_item.gross_weight = float(poids_brut_articles[i])

        # === RÉPARTITION POIDS NET (net_weight) ===
        if rfcv_data.valuation.net_weight is not None:
            poids_net_total = rfcv_data.valuation.net_weight
            poids_net_articles = self.distribute_proportionally(
                total_amount=poids_net_total,
                item_fobs=item_fobs,
                fob_total=fob_total
            )

            # Affecter aux articles
            for i, item in enumerate(rfcv_data.items):
                if not item.valuation_item:
                    item.valuation_item = ValuationItem()

                item.valuation_item.net_weight = float(poids_net_articles[i])

        return rfcv_data
