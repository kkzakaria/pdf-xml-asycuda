"""
Présentation d'un dossier : pastille de statut et barre d'étapes (fonctions pures).

Ordre de priorité des étapes (spécification de la refonte) : déclaré > annulé / abandonné >
dernière tentative en échec > aucune génération > alerte bloquante > génération à vérifier.
"""
from dataclasses import dataclass

LIBELLES_ETAPES = ("RFCV déposé", "Réglages et génération", "Vérification", "Déclaré dans SYDAM")


@dataclass(frozen=True)
class Etape:
    numero: int
    libelle: str
    etat: str          # fait | actif | erreur | a_faire | inactif


def statut_affiche(status: str, has_generation: bool, error: str | None) -> tuple[str, str]:
    """(code de pastille, libellé) : un brouillon est « Généré » ou « Échec » selon sa dernière génération."""
    if status == "declare":
        return "declare", "Déclaré"
    if status == "annule":
        return "annule", "Annulé"
    if status == "abandonne":
        return "abandonne", "Abandonné"
    if error:
        return "echec", "Échec"
    if has_generation:
        return "genere", "Généré"
    return "brouillon", "Brouillon"


def etapes_dossier(status: str, has_generation: bool, error: str | None, bloquante: bool) -> list[Etape]:
    """Les 4 étapes du dossier et leur état."""
    if status == "declare":
        etats = ("fait", "fait", "fait", "fait")
    elif status in ("annule", "abandonne"):
        etats = ("fait", "inactif", "inactif", "inactif")
    elif error:
        etats = ("fait", "erreur", "a_faire", "a_faire")
    elif not has_generation:
        etats = ("fait", "actif", "a_faire", "a_faire")
    elif bloquante:
        etats = ("fait", "fait", "erreur", "a_faire")
    else:
        etats = ("fait", "fait", "actif", "a_faire")
    return [Etape(i + 1, libelle, etat) for i, (libelle, etat) in enumerate(zip(LIBELLES_ETAPES, etats))]
