"""
Options de déclaration communes aux routes de conversion : profil société, données du
dossier et mode de calcul de l'assurance.

Les profils sont des fichiers du serveur (settings.profiles_dir, ex. profils/karta-transit.ini),
désignés par leur nom : le client ne transmet ni fichier ni chemin.
"""
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Form, HTTPException, status

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from company_profile import CompanyProfile, load_profile

from .config import settings

PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
INSURANCE_MODES = ("formule", "rfcv")

PROFIL_DESCRIPTION = ("Nom du profil société du serveur (ex: karta-transit), voir GET /api/v1/profils. "
                      "Remplit bureau, déclarant, banque, compte, emplacement. Optionnel.")
ASSURANCE_DESCRIPTION = ("Calcul de l'assurance : 'formule' (défaut, ceiling(2500 + (FOB+FRET) × taux × 0,15 %)) "
                         "ou 'rfcv' (assurance attestée en case 21 × taux douanier)")


def profiles_dir() -> Path:
    return Path(settings.profiles_dir)


def list_profiles() -> list[str]:
    directory = profiles_dir()
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.ini") if PROFILE_NAME.match(p.stem))


def resolve_profile(name: str | None) -> CompanyProfile | None:
    """Charge un profil par son nom ; HTTP 400 si le nom est invalide, inconnu ou le fichier mal formé."""
    if not name:
        return None
    if not PROFILE_NAME.match(name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Nom de profil invalide : {name!r} (lettres, chiffres, '-' et '_')")
    path = profiles_dir() / f"{name}.ini"
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Profil inconnu : {name!r}. Profils disponibles : {', '.join(list_profiles()) or 'aucun'}")
    try:
        return load_profile(str(path))
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Profil {name!r} illisible : {e}") from e


def _check_insurance(mode: str) -> str:
    if mode not in INSURANCE_MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"assurance invalide : {mode!r} (attendu : {' ou '.join(INSURANCE_MODES)})")
    return mode


@dataclass
class DeclarationOptions:
    """Options d'une conversion unitaire."""
    profile: CompanyProfile | None = None
    insurance_mode: str = "formule"
    dossier: str | None = None
    manifeste: str | None = None
    nationalite_transport: str | None = None

    def service_kwargs(self) -> dict[str, Any]:
        return {"profile": self.profile, "insurance_mode": self.insurance_mode, "dossier": self.dossier,
                "manifeste": self.manifeste, "nationalite_transport": self.nationalite_transport}


async def declaration_options(
    profil: str | None = Form(None, description=PROFIL_DESCRIPTION),
    dossier: str | None = Form(None, description="N° de dossier : référence déclarant = préfixe du profil + n° (ex: 31287 -> KARTA31287)"),
    manifeste: str | None = Form(None, description="Référence du manifeste (ex: CIAB1 2026 7065)"),
    nationalite_transport: str | None = Form(None, description="Nationalité du moyen de transport, code pays (ex: LR)"),
    assurance: str = Form("formule", description=ASSURANCE_DESCRIPTION),
) -> DeclarationOptions:
    return DeclarationOptions(
        profile=resolve_profile(profil),
        insurance_mode=_check_insurance(assurance),
        dossier=dossier or None,
        manifeste=manifeste or None,
        nationalite_transport=nationalite_transport or None,
    )


@dataclass
class BatchDeclarationOptions:
    """Options d'un batch : profil et assurance communs, données de dossier par fichier."""
    profile: CompanyProfile | None = None
    insurance_mode: str = "formule"
    dossiers: list[str | None] = field(default_factory=list)
    manifestes: list[str | None] = field(default_factory=list)
    nationalites_transport: list[str | None] = field(default_factory=list)

    def check_lengths(self, n_files: int) -> None:
        for name in ("dossiers", "manifestes", "nationalites_transport"):
            values = getattr(self, name)
            if values and len(values) != n_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Le nombre de {name} ({len(values)}) doit correspondre au nombre de fichiers ({n_files}) ou être vide")

    def service_kwargs(self) -> dict[str, Any]:
        return {"profile": self.profile, "insurance_mode": self.insurance_mode, "dossiers": self.dossiers,
                "manifestes": self.manifestes, "nationalites_transport": self.nationalites_transport}


def _json_list(raw: str | None, name: str) -> list[str | None]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Format {name} invalide : {e}") from e
    if not isinstance(values, list) or not all(v is None or isinstance(v, (str, int)) for v in values):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"{name} doit être une liste JSON de chaînes ou null")
    return [str(v) if v is not None else None for v in values]


async def batch_declaration_options(
    profil: str | None = Form(None, description=PROFIL_DESCRIPTION + " Commun à tous les fichiers."),
    dossiers: str | None = Form(None, description='Liste JSON des n° de dossier, un par fichier ou null (ex: ["31287", null])'),
    manifestes: str | None = Form(None, description='Liste JSON des manifestes, un par fichier ou null'),
    nationalites_transport: str | None = Form(None, description='Liste JSON des nationalités du transport, un par fichier ou null'),
    assurance: str = Form("formule", description=ASSURANCE_DESCRIPTION + " Commun à tous les fichiers."),
) -> BatchDeclarationOptions:
    return BatchDeclarationOptions(
        profile=resolve_profile(profil),
        insurance_mode=_check_insurance(assurance),
        dossiers=_json_list(dossiers, "dossiers"),
        manifestes=_json_list(manifestes, "manifestes"),
        nationalites_transport=_json_list(nationalites_transport, "nationalites_transport"),
    )
