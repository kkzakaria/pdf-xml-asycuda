"""
Pages de l'application web (provisoire : remplacé par les gabarits de la tâche 8).
"""
from html import escape

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from .auth import User, current_user

# Toutes les routes de la webapp exigent un utilisateur (garde Access ou mode
# développement) ; sans configuration d'accès elles répondent 503.
router = APIRouter(include_in_schema=False, dependencies=[Depends(current_user)])


@router.get("/", response_class=HTMLResponse)
async def accueil(user: User = Depends(current_user)):
    return HTMLResponse(
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<title>Génération</title></head><body>"
        f"<p>Connecté : {escape(user.email)}</p></body></html>"
    )
