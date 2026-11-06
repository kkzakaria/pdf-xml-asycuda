"""
Routes profils société : liste des profils disponibles sur le serveur.
"""
from dataclasses import asdict

from fastapi import APIRouter, Depends

from ..core.declaration_options import list_profiles, resolve_profile
from ..core.security import verify_api_key

router = APIRouter(prefix="/api/v1/profils", tags=["Profils"])


@router.get(
    "",
    summary="Lister les profils société",
    description="Profils utilisables dans le champ `profil` des conversions (fichiers *.ini de API_PROFILES_DIR).",
    dependencies=[Depends(verify_api_key)],
)
async def get_profiles():
    return {"profils": [{"nom": name, **asdict(resolve_profile(name))} for name in list_profiles()]}
