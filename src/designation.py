"""
Désignation courte des articles RFCV (case 31 et description marchandise).

Exemple : le texte RFCV "TRICYLE-APSONIC-" devient "TRICYCLE".
"""
import re
from typing import Optional

from models import RFCVData


def suggest_designation(raw: Optional[str]) -> Optional[str]:
    """
    Propose une désignation courte à partir du texte RFCV brut.

    Retourne None si le texte est vide, déjà propre ("MOTO" ou "TRICYCLE")
    ou non reconnu.
    """
    if not raw:
        return None
    mots = [m for m in re.split(r"[\s\-]+", raw.upper()) if m]
    if not mots:
        return None
    premier = mots[0]
    if premier.startswith("TRICY"):
        return None if mots == ["TRICYCLE"] else "TRICYCLE"
    if premier == "MOTORCYCLE" or (premier == "MOTO" and len(mots) > 1):
        return "MOTO"
    return None


def apply_designation(rfcv_data: RFCVData, designation: str) -> int:
    """
    Applique la désignation à tous les articles (goods_description, et packages.marks1
    lorsque packages est renseigné).

    Retourne le nombre d'articles dont marks1 ou goods_description a effectivement changé.
    """
    modifies = 0
    for item in rfcv_data.items:
        changed = item.goods_description != designation
        item.goods_description = designation
        if item.packages is not None and item.packages.marks1 != designation:
            item.packages.marks1 = designation
            changed = True
        if changed:
            modifies += 1
    return modifies
