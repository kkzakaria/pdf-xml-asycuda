"""
Module de regroupement d'articles par code HS
Regroupe les articles sans châssis ayant le même code HS en un seul article

Règles de regroupement :
- Les articles avec numéro de châssis ne sont JAMAIS regroupés
- Les articles sans châssis avec le même code HS attesté sont regroupés
- L'article regroupé porte la somme des valeurs de ses lignes (FOB, fret, assurance, poids),
  réparties AVANT le regroupement, ligne par ligne, comme Karta
- Colis (Packages/Number_of_packages) : dossier sans châssis dont les quantités des lignes RFCV
  totalisent les colis (section 24) -> somme des quantités des lignes de l'article ; sinon,
  regroupement effectif -> total sur le premier article, 0 sur les autres

Le code HS utilisé pour le regroupement est le "Code SH Attesté" extrait de la
section "26. Articles" du RFCV (ex: "8703.23.19.00" → "87032319")

Le nombre de colis provient de la section "24. Colisage, nombre et désignation des marchandises"

Auteur: SuperZ AI
Date: 2025-01-31
"""

import logging
from typing import List, Dict, Optional
from collections import defaultdict

# Support both relative and absolute imports
try:
    from .models import Item, Package, SupplementaryUnit, CurrencyAmount
except ImportError:
    from models import Item, Package, SupplementaryUnit, CurrencyAmount

logger = logging.getLogger(__name__)


def group_items_by_hs_code(items: List[Item], total_packages: Optional[float] = None) -> List[Item]:
    """
    Regroupe les articles sans châssis par code HS attesté complet.

    Workflow :
    1. Séparer les articles avec châssis (non regroupables) et sans châssis (regroupables)
    2. Regrouper les articles sans châssis par code HS complet (commodity_code)
    3. Garder un article par groupe, portant la somme des valeurs du groupe
    4. Colis : quantités des lignes RFCV si elles totalisent total_packages (sans châssis),
       sinon total sur le premier article du premier groupe et 0 ailleurs
    5. Recombiner les deux listes (avec châssis + regroupés)

    Args:
        items: Liste d'articles extraits du RFCV
        total_packages: Nombre total de colis (section 24)

    Returns:
        Liste d'articles après regroupement

    Exemple:
        Entrée : 35 articles sans châssis, total_packages=35 (section 24)
        - 10 articles HS 8703.23.19.00 → 1 article (quantité = 35) ← PREMIER
        - 15 articles HS 8704.21.10.00 → 1 article (quantité = 0)
        - 10 articles HS 8711.20.90.00 → 1 article (quantité = 0)
        Sortie : 3 articles

        Si un article a un châssis détecté, il est conservé tel quel (pas de regroupement)
    """
    if not items:
        return items

    # Étape 1 : Séparer articles avec et sans châssis
    items_with_chassis = []
    items_without_chassis = []

    for item in items:
        has_chassis = _has_chassis_number(item)

        if has_chassis:
            items_with_chassis.append(item)
        else:
            items_without_chassis.append(item)

    logger.info(f"Regroupement d'articles : {len(items_with_chassis)} avec châssis, "
                f"{len(items_without_chassis)} sans châssis")

    # Si aucun article sans châssis, pas de regroupement nécessaire
    if not items_without_chassis:
        logger.info("Aucun article sans châssis → pas de regroupement")
        return items

    # Étape 2 : Regrouper les articles sans châssis par code HS complet
    groups: Dict[str, List[Item]] = defaultdict(list)

    for item in items_without_chassis:
        hs_code_full = _extract_hs_code_full(item)

        # Si pas de code HS valide, créer un groupe unique pour cet article
        if not hs_code_full:
            # Utiliser un identifiant unique pour éviter de regrouper avec d'autres articles sans HS
            unique_key = f"NO_HS_{id(item)}"
            groups[unique_key].append(item)
            logger.warning(f"Article sans code HS valide → groupe isolé {unique_key}")
        else:
            groups[hs_code_full].append(item)

    logger.info(f"Regroupement en {len(groups)} groupes par code HS")

    # Vérifier si un regroupement réel a lieu (au moins un groupe avec 2+ articles)
    has_actual_grouping = any(len(group_items) > 1 for group_items in groups.values())

    # Étape 3 : un article représentatif par groupe, portant les valeurs de tout le groupe
    # (FOB, fret, assurance, poids, quantités : sinon seul le premier article serait déclaré)
    grouped_items = []
    for hs_code, group_items in groups.items():
        representative = group_items[0]
        if len(group_items) > 1:
            _sum_group_values(representative, group_items)
            logger.info(f"  Groupe HS {hs_code}: {len(group_items)} articles → 1 article")
        grouped_items.append(representative)

    # Étape 4 : colis (case 31)
    # - dossier sans châssis dont les quantités des lignes RFCV totalisent les colis (case 24) :
    #   chaque article reçoit la somme des quantités de ses lignes, comme Karta
    #   (31476 : 9404 = 35, 9403 = 70 + 49, 6309 = 94 + 70 + 100) ;
    # - sinon, regroupement effectif : total sur le premier article, 0 ailleurs ;
    # - sinon : quantités inchangées (réparties par l'enrichissement ASYCUDA).
    if total_packages is not None:
        if not items_with_chassis and _quantities_match(grouped_items, total_packages):
            for item in grouped_items:
                _set_item_quantity(item, item.rfcv_quantity)
            logger.info("Colis par article = quantités des lignes RFCV")
        elif has_actual_grouping:
            for index, item in enumerate(grouped_items):
                _set_item_quantity(item, total_packages if index == 0 else 0.0)

    # Étape 5 : articles avec châssis en premier, puis articles regroupés
    final_items = items_with_chassis + grouped_items
    logger.info(f"Résultat regroupement : {len(items)} articles → {len(final_items)} articles finaux")
    return final_items


def _quantities_match(items: List[Item], total_packages: float) -> bool:
    """Vrai si chaque article a une quantité RFCV entière et que leur somme vaut le total des colis."""
    quantities = [i.rfcv_quantity for i in items]
    if not quantities or any(q is None or q < 0 or not float(q).is_integer() for q in quantities):
        return False
    return abs(sum(quantities) - float(total_packages)) < 1e-6


def _sum_values(values: List[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return round(sum(present), 2) if present else None


def _sum_amount(amounts: List[Optional[CurrencyAmount]]) -> Optional[CurrencyAmount]:
    """Somme de montants répartis par ligne (fret, assurance) : devise et taux du premier."""
    present = [a for a in amounts if a is not None]
    if not present:
        return None
    first = present[0]
    return CurrencyAmount(
        amount_national=_sum_values([a.amount_national for a in present]),
        amount_foreign=_sum_values([a.amount_foreign for a in present]),
        currency_code=first.currency_code, currency_name=first.currency_name,
        currency_rate=first.currency_rate)


def _sum_group_values(representative: Item, group_items: List[Item]) -> None:
    """
    Additionne sur l'article retenu les valeurs du groupe : FOB (item_price), coûts / CIF, fret,
    assurance et poids déjà répartis par ligne RFCV, quantités des lignes.
    """
    quantities = [i.rfcv_quantity for i in group_items]
    representative.rfcv_quantity = None if any(q is None for q in quantities) else round(sum(quantities), 6)
    if representative.tarification:
        representative.tarification.item_price = _sum_values(
            [i.tarification.item_price if i.tarification else None for i in group_items])
    if representative.valuation_item:
        representative.valuation_item.total_cost = _sum_values(
            [i.valuation_item.total_cost if i.valuation_item else None for i in group_items])
        representative.valuation_item.total_cif = _sum_values(
            [i.valuation_item.total_cif if i.valuation_item else None for i in group_items])
        vis = [i.valuation_item for i in group_items if i.valuation_item]
        representative.valuation_item.invoice = _sum_amount([v.invoice for v in vis])
        representative.valuation_item.external_freight = _sum_amount([v.external_freight for v in vis])
        representative.valuation_item.insurance = _sum_amount([v.insurance for v in vis])
        representative.valuation_item.gross_weight = _sum_values([v.gross_weight for v in vis])
        representative.valuation_item.net_weight = _sum_values([v.net_weight for v in vis])


def _has_chassis_number(item: Item) -> bool:
    """
    Vérifie si un article possède un numéro de châssis.

    Args:
        item: Article à vérifier

    Returns:
        True si l'article a un châssis, False sinon
    """
    return (
        item.packages is not None
        and item.packages.chassis_number is not None
        and item.packages.chassis_number.strip() != ""
    )


def _extract_hs_code_full(item: Item) -> str:
    """
    Extrait le code HS complet d'un article (Code SH Attesté).

    Le code HS est stocké dans item.tarification.hscode.commodity_code
    (8 chiffres, ex: "87032319" pour le code "8703.23.19.00")

    Args:
        item: Article dont extraire le code HS

    Returns:
        Code HS complet (ex: "87032319") ou None si invalide
    """
    if not item.tarification or not item.tarification.hscode:
        return None

    hs_code = item.tarification.hscode.commodity_code

    if not hs_code or len(hs_code) == 0:
        return None

    # Le code HS est déjà nettoyé (sans points) dans le parser
    # On le retourne tel quel
    return hs_code


def _set_item_quantity(item: Item, quantity: float) -> None:
    """
    Modifie la quantité d'un article.

    La quantité (nombre de colis, case 31) est portée par Packages/Number_of_packages ;
    les unités supplémentaires restent déterminées par ASYCUDA selon le code SH.

    Args:
        item: Article à modifier
        quantity: Nouvelle quantité (ex: nombre de colis)
    """
    if item.packages is None:
        item.packages = Package()
    item.packages.number_of_packages = float(quantity)
