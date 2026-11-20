"""Pastille de statut et barre d'étapes d'un dossier (ordre de priorité de la spécification)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from webapp.presentation import Etape, etapes_dossier, statut_affiche  # noqa: E402


@pytest.mark.parametrize("status, has_generation, error, attendu", [
    ("brouillon", False, None, ("brouillon", "Brouillon")),
    ("brouillon", True, None, ("genere", "Généré")),
    ("brouillon", True, "x", ("echec", "Échec")),
    ("brouillon", False, "x", ("echec", "Échec")),
    ("declare", True, None, ("declare", "Déclaré")),
    ("annule", True, None, ("annule", "Annulé")),
    ("abandonne", False, None, ("abandonne", "Abandonné")),
])
def test_statut_affiche(status, has_generation, error, attendu):
    assert statut_affiche(status, has_generation, error) == attendu


def etats(*args):
    return [e.etat for e in etapes_dossier(*args)]


@pytest.mark.parametrize("args, attendu", [
    (("declare", True, None, False), ["fait", "fait", "fait", "fait"]),
    (("abandonne", True, None, False), ["fait", "inactif", "inactif", "inactif"]),
    (("annule", True, None, False), ["fait", "inactif", "inactif", "inactif"]),
    (("brouillon", True, "erreur", False), ["fait", "erreur", "a_faire", "a_faire"]),
    (("brouillon", False, None, False), ["fait", "actif", "a_faire", "a_faire"]),
    (("brouillon", True, None, True), ["fait", "fait", "erreur", "a_faire"]),
    (("brouillon", True, None, False), ["fait", "fait", "actif", "a_faire"]),
    (("brouillon", True, "erreur", True), ["fait", "erreur", "a_faire", "a_faire"]),   # l'échec l'emporte
])
def test_etapes_ordre_de_priorite(args, attendu):
    assert etats(*args) == attendu


def test_etapes_libelles():
    etapes = etapes_dossier("brouillon", False, None, False)
    assert [(e.numero, e.libelle) for e in etapes] == [
        (1, "RFCV déposé"), (2, "Réglages et génération"), (3, "Vérification"), (4, "Déclaré dans SYDAM")]
    assert isinstance(etapes[0], Etape)
