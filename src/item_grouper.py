"""
Module de regroupement d'articles par code HS
Regroupe les articles sans châssis ayant le même code HS en un seul article

Règles de regroupement :
- Les articles avec numéro de châssis ne sont JAMAIS regroupés
- Les articles sans châssis avec le même code HS attesté sont regroupés
- Seul le PREMIER article du PREMIER groupe aura comme quantité le nombre de colis total (section 24)
- Tous les autres articles auront une quantité de 0
- La quantité est modifiée dans SupplementaryUnit.quantity

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
    from .models import Item, Package, SupplementaryUnit
except ImportError:
    from models import Item, Package, SupplementaryUnit

logger = logging.getLogger(__name__)


def group_items_by_hs_code(items: List[Item], total_packages: Optional[float] = None) -> List[Item]:
    """
    Regroupe les articles sans châssis par code HS attesté complet.

    Workflow :
    1. Séparer les articles avec châssis (non regroupables) et sans châssis (regroupables)
    2. Regrouper les articles sans châssis par code HS complet (commodity_code)
    3. Garder un article par groupe
    4. Le premier article du premier groupe : quantité = total_packages
    5. Tous les autres articles : quantité = 0
    6. Recombiner les deux listes (avec châssis + regroupés)

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

    if not has_actual_grouping:
        logger.info("Tous les codes HS sont différents → aucun regroupement nécessaire")
        # Pas de regroupement : retourner tous les articles sans modification
        final_items = items_with_chassis + items_without_chassis
        logger.info(f"Résultat : {len(items)} articles → {len(final_items)} articles (inchangé)")
        return final_items

    logger.info("Regroupement effectif détecté → application des règles de quantité")

    # Étape 3 : Créer un article représentatif par groupe
    grouped_items = []
    is_first_group = True

    for hs_code, group_items in groups.items():
        if not group_items:
            continue

        # Prendre le premier article comme représentant du groupe
        representative = group_items[0]
        num_items_in_group = len(group_items)

        # Mettre la quantité selon la règle :
        # - Premier article du premier groupe : quantité = total_packages (si fourni)
        # - Tous les autres : quantité = 0 (si total_packages fourni)
        # - Si total_packages est None : ne pas modifier les quantités
        if total_packages is not None:
            if is_first_group:
                _set_item_quantity(representative, total_packages)
                logger.info(f"  Groupe HS {hs_code} (PREMIER): {num_items_in_group} articles → 1 article "
                           f"(quantité = {total_packages})")
                is_first_group = False
            else:
                _set_item_quantity(representative, 0.0)
                if num_items_in_group > 1:
                    logger.info(f"  Groupe HS {hs_code}: {num_items_in_group} articles → 1 article (quantité = 0)")
                else:
                    logger.debug(f"  Groupe HS {hs_code}: 1 article (quantité = 0)")
        else:
            # total_packages non fourni : ne pas modifier les quantités
            if num_items_in_group > 1:
                logger.info(f"  Groupe HS {hs_code}: {num_items_in_group} articles → 1 article (quantité inchangée)")
            else:
                logger.debug(f"  Groupe HS {hs_code}: 1 article (quantité inchangée)")

        grouped_items.append(representative)

    # Étape 4 : Recombiner les deux listes
    # Articles avec châssis en premier, puis articles regroupés
    final_items = items_with_chassis + grouped_items

    logger.info(f"Résultat regroupement : {len(items)} articles → {len(final_items)} articles finaux")

    return final_items


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

    La quantité est stockée dans item.tarification.supplementary_units[0].quantity

    Args:
        item: Article à modifier
        quantity: Nouvelle quantité (ex: nombre de colis)
    """
    if not item.tarification:
        return

    if not item.tarification.supplementary_units:
        # Créer un SupplementaryUnit si inexistant
        item.tarification.supplementary_units = [
            SupplementaryUnit(
                code='QA',
                name='Unité d\'apurement',
                quantity=quantity
            )
        ]
    else:
        # Modifier la quantité du premier SupplementaryUnit
        item.tarification.supplementary_units[0].quantity = quantity
