"""
Routes corps SYDAM : XML ASYCUDA -> corps.txt (fichier d'écriture de l'agent SYDAM).

- GET  /api/v1/corps/{file_id} : corps d'un XML produit par une conversion
- POST /api/v1/corps           : corps d'un XML envoyé (ex. export du client ASYCUDA)
"""
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse

from ..core.config import settings
from ..core.rate_limit import RateLimits, limiter
from ..core.security import verify_api_key
from ..services.corps_service import CorpsError, corps_service
from .files import validate_file_id

router = APIRouter(prefix="/api/v1/corps", tags=["Corps SYDAM"])
logger = logging.getLogger(__name__)

HTTP_422 = 422  # constante numérique : le nom diffère selon la version de Starlette


def _corps_response(result, xml_stem: str) -> PlainTextResponse:
    xml_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", xml_stem)[:200]   # nom sûr pour Content-Disposition
    headers = {
        "Content-Disposition": f'attachment; filename="corps_{xml_stem}.txt"',
        "X-Corps-Items": str(result.n_items),
        "X-Corps-Missing": ",".join(result.missing),
    }
    return PlainTextResponse(result.content, media_type="text/plain; charset=utf-8", headers=headers)


@router.get(
    "/{file_id}",
    response_class=PlainTextResponse,
    summary="Corps SYDAM d'un XML converti",
    description=("Génère le corps SYDAM (corps_<nom>.txt) d'un XML produit par une conversion. "
                 "`file_id` = `output_file` de la réponse de conversion, avec ou sans `.xml`. "
                 "En-têtes : `X-Corps-Items` (nombre d'articles), `X-Corps-Missing` (champs généraux sans valeur)."),
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(RateLimits.DOWNLOAD)
async def corps_from_output(request: Request, file_id: str):
    safe_file_id = validate_file_id(file_id, request)
    if not safe_file_id.endswith(".xml"):
        safe_file_id = f"{safe_file_id}.xml"
    try:
        result, stem = corps_service.from_output(safe_file_id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Accès refusé: chemin en dehors du répertoire autorisé")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Fichier {safe_file_id} introuvable")
    except CorpsError as e:
        raise HTTPException(status_code=HTTP_422, detail=str(e)) from e
    logger.info("Corps SYDAM: file=%s, items=%d", safe_file_id, result.n_items)
    return _corps_response(result, stem)


@router.post(
    "",
    response_class=PlainTextResponse,
    summary="Corps SYDAM d'un XML envoyé",
    description=("Génère le corps SYDAM d'un XML ASYCUDA envoyé (produit par ce service ou exporté du client). "
                 "Mêmes en-têtes que GET /api/v1/corps/{file_id}."),
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(RateLimits.UPLOAD_SINGLE)
async def corps_from_upload(request: Request, file: UploadFile = File(..., description="Fichier XML ASYCUDA")):
    name = file.filename or "declaration.xml"
    if Path(name).suffix.lower() != ".xml":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier .xml attendu")
    data = await file.read(settings.max_upload_size + 1)
    if len(data) > settings.max_upload_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Fichier trop volumineux (max {settings.max_upload_size // (1024 * 1024)} Mo)")
    try:
        result, stem = corps_service.from_bytes(data, name)
    except CorpsError as e:
        raise HTTPException(status_code=HTTP_422, detail=str(e)) from e
    logger.info("Corps SYDAM (upload): file=%s, items=%d", name, result.n_items)
    return _corps_response(result, stem)
