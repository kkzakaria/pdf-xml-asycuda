"""
Écrans de la webapp (spécification §5.3 à §5.5) : Dossiers, Nouveau, Dossier.

Toutes les routes sont sur `router`, qui exige `current_user` : sans configuration d'accès,
le garde laisse passer les requêtes et c'est cette dépendance qui répond 503.
Les routes qui lisent un PDF ou génèrent sont synchrones (exécutées dans le pool de threads).
"""
from __future__ import annotations

import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chassis_registry import ChassisRegistry, normalize_rfcv  # noqa: E402
from company_profile import load_profile  # noqa: E402
from generation import ASSURANCE_MODES, Amount, GenerationSettings  # noqa: E402
from generation_summary import FOB_MODES, fmt_montant  # noqa: E402

from . import config, db  # noqa: E402
from .auth import User, current_user, require_admin  # noqa: E402
from .dossiers import (RFCV_ILLISIBLE, DeclarationRefusee, DossierFige, DossierIntrouvable,  # noqa: E402
                       DossierService)

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"

_env = Environment(loader=FileSystemLoader(str(HERE / "templates")), autoescape=True,
                   trim_blocks=True, lstrip_blocks=True)
_env.filters["montant"] = lambda x: fmt_montant(x) if x is not None else ""
_env.filters["valeurs"] = lambda vals: ", ".join(f"{n} × {fmt_montant(v)}" for v, n in (vals or []))
_SH_ALERTE = re.compile(r"Code SH (\S+) jamais déclaré pour « (.*) »$", re.S)


def _paire_sh(message: str):
    """(désignation, code SH) d'une alerte « code_sh_inhabituel », sinon None."""
    m = _SH_ALERTE.match(message or "")
    return (m.group(2), m.group(1)) if m else None


_env.filters["paire_sh"] = _paire_sh
templates = Jinja2Templates(env=_env)

STATUTS = {"brouillon": "Brouillon", "declare": "Déclaré", "annule": "Annulé", "abandonne": "Abandonné"}
_env.globals["STATUTS"] = STATUTS
ACTIONS = {"creation": "Dépôt", "generation": "Génération", "generation_echec": "Échec de génération",
           "generation_abandonnee": "Génération abandonnée", "declaration": "Déclaré dans SYDAM",
           "declaration_refusee": "Déclaration refusée", "retour_brouillon": "Remis en brouillon",
           "abandon": "Abandonné", "reouverture": "Rouvert", "rfcv_annule": "RFCV annulé",
           "rfcv_restaure": "RFCV restauré", "code_sh_normal": "Code SH habituel"}
_env.globals["ACTIONS"] = ACTIONS
CASES = [("Fcx_Aa", "Bureau (case A)"), ("Fcx_29a", "Bureau d'entrée / sortie (case 29)"),
         ("Fcx_10", "Case 10"), ("Fcx_18b", "Case 18"), ("Fcx_28b", "Case 28 (banque)"),
         ("Fcx_31f", "Case 31, article 1"), ("Fld_40", "Case 40, article 1")]
ASSURANCE_LIBELLES = {"formule": "Formule (par défaut)", "rfcv": "Attestée par le RFCV (case 21)",
                      "imposee": "Imposée"}
FICHIERS = {"xml": "application/xml", "corps": "text/plain; charset=utf-8", "pdf": "application/pdf"}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def same_origin(request: Request) -> None:
    """
    Protection CSRF : le cookie Access (CF_Authorization) part avec toute requête du
    navigateur, y compris depuis un autre site. Une requête qui modifie l'état est refusée
    si le navigateur la dit inter-sites (Sec-Fetch-Site) ou si son Origin n'est pas l'hôte
    de la requête. Sans aucun des deux en-têtes (curl, tests), elle est acceptée.
    """
    if request.method in SAFE_METHODS:
        return
    refus = HTTPException(status_code=403, detail="Requête refusée : envoyée depuis un autre site")
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise refus
    origin = request.headers.get("origin")
    if origin is not None:
        host = request.headers.get("host", "").lower()
        if not host or urlsplit(origin.strip()).netloc.lower() != host:
            raise refus


# Toutes les routes de la webapp exigent un utilisateur (garde Access ou mode développement)
# et, pour les requêtes qui modifient l'état, la même origine.
router = APIRouter(include_in_schema=False, dependencies=[Depends(current_user), Depends(same_origin)])


# ------------------------------------------------------------------ dépendances
def get_service():
    """Service des dossiers pour une requête : connexion SQLite ouverte puis refermée."""
    settings = config.get_settings()
    conn = db.connect(Path(settings.data_dir) / "webapp.db")
    try:
        db.init(conn)
        yield DossierService(conn, settings, ChassisRegistry(str(settings.registry_path)))
    finally:
        conn.close()


async def form_data(request: Request) -> dict[str, str]:
    """Champs texte du formulaire (lu ici pour que la route reste synchrone)."""
    form = await request.form()
    return {k: v for k, v in form.items() if isinstance(v, str)}


def _get_dossier(svc: DossierService, dossier_id: int) -> dict:
    try:
        return svc.get(dossier_id)
    except DossierIntrouvable:
        raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} introuvable")


# Entrée de menu active selon l'écran
_MENU_ACTIF = {"dossiers.html": "dossiers", "dossier.html": "dossiers", "nouveau.html": "nouveau",
               "chassis.html": "chassis"}


def _render(request: Request, name: str, user: User, status_code: int = 200, headers=None, **context):
    context.update(user=user, active=_MENU_ACTIF.get(name))
    return templates.TemplateResponse(request, name, context, status_code=status_code, headers=headers)


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


# ------------------------------------------------------------------ réglages <-> formulaire
def _profiles() -> dict[str, Path]:
    """Profils société proposés : fichiers .ini du dossier du profil par défaut."""
    folder = Path(config.get_settings().profile_path).parent
    return {p.name: p for p in sorted(folder.glob("*.ini"))} if folder.is_dir() else {}


def _num(x: Optional[float]) -> str:
    if x is None:
        return ""
    return str(int(x)) if float(x) == int(x) else repr(float(x))


def settings_to_form(s: GenerationSettings) -> dict[str, str]:
    """Réglages -> valeurs (texte) du formulaire."""
    profile = ""
    if s.profile is not None:
        for name, path in _profiles().items():
            try:
                if load_profile(str(path)) == s.profile:
                    profile = name
                    break
            except Exception:  # profil illisible : simplement pas proposé comme choix courant
                logger.warning("Profil illisible : %s", path)
    values = {"taux_douane": _num(s.taux_douane), "profile": profile, "fob_mode": s.fob_mode,
              "assurance_mode": s.assurance_mode}
    for key in ("dossier", "manifeste", "nationalite_transport", "rapport_paiement", "designation", "banque"):
        values[key] = getattr(s, key) or ""
    for key in ("takikro", "disp", "fob_exact"):
        values[key] = "1" if getattr(s, key) else ""
    for key in ("fob_revise", "fret", "assurance"):
        amount: Optional[Amount] = getattr(s, key)
        values[key] = _num(amount.value) if amount else ""
        values[f"{key}_par_article"] = "1" if amount and amount.per_article else ""
    return values


def _parse_number(raw: str, label: str, errors: list[str], required=False, positive=False) -> Optional[float]:
    text = (raw or "").strip()
    cleaned = text.replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        if required:
            errors.append(f"{label} : valeur obligatoire")
        return None
    try:
        value = float(cleaned)
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        errors.append(f"{label} : « {text} » n'est pas un nombre valide")
        return None
    if value < 0 or (positive and value == 0):
        errors.append(f"{label} : le montant doit être {'strictement ' if positive else ''}positif")
        return None
    return value


def form_to_settings(values: dict[str, str]) -> tuple[Optional[GenerationSettings], list[str]]:
    """Formulaire -> réglages ; messages d'erreur en français si la saisie est invalide."""
    errors: list[str] = []
    taux = _parse_number(values.get("taux_douane", ""), "Taux douanier", errors, required=True, positive=True)

    def amount(key, label):
        v = _parse_number(values.get(key, ""), label, errors, positive=True)
        return Amount(v, bool(values.get(f"{key}_par_article"))) if v is not None else None

    fob = amount("fob_revise", "FOB révisé")
    fret = amount("fret", "Fret")
    assurance = amount("assurance", "Assurance")
    fob_mode = values.get("fob_mode") or "prorata"
    if fob_mode not in FOB_MODES:
        errors.append("Répartition du FOB : choix invalide")
    assurance_mode = values.get("assurance_mode") or "formule"
    if assurance_mode not in ASSURANCE_MODES:
        errors.append("Assurance : choix invalide")
    elif assurance_mode == "imposee" and assurance is None and not values.get("assurance", "").strip():
        errors.append("Assurance imposée : indiquer le montant de l'assurance (XOF)")

    profile = None
    name = values.get("profile") or ""
    if name:
        path = _profiles().get(name)
        if path is None:
            errors.append(f"Profil société inconnu : {name}")
        else:
            try:
                profile = load_profile(str(path))
            except Exception as exc:
                errors.append(f"Profil société {name} illisible : {exc}")
    if errors:
        return None, errors

    def text(key):
        return (values.get(key) or "").strip() or None

    return GenerationSettings(
        taux_douane=taux, profile=profile, dossier=text("dossier"), manifeste=text("manifeste"),
        nationalite_transport=text("nationalite_transport"), rapport_paiement=text("rapport_paiement"),
        takikro=bool(values.get("takikro")), disp=bool(values.get("disp")), banque=text("banque"),
        fob_revise=fob, fob_mode=fob_mode, fret=fret,
        assurance_mode=assurance_mode, assurance=assurance if assurance_mode == "imposee" else None,
        designation=text("designation"), fob_exact=bool(values.get("fob_exact")),
    ), []


# ------------------------------------------------------------------ contexte d'un dossier
def _dossier_context(svc: DossierService, dossier_id: int, form: Optional[dict] = None,
                     form_errors: Optional[list[str]] = None) -> dict:
    dossier = _get_dossier(svc, dossier_id)
    generations = svc.generations(dossier_id)
    summary = svc.latest_summary(dossier_id)
    fige = dossier["status"] != "brouillon"
    # sans n° RFCV lisible, la déclaration est refusée (voir DossierService._declare)
    rfcv_illisible = summary is not None and not normalize_rfcv(dossier["rfcv_number"] or summary.rfcv_number)
    if form is None and not fige:
        if generations:
            form = settings_to_form(GenerationSettings.from_dict(json.loads(generations[0]["settings_json"])))
        else:
            form = settings_to_form(svc.default_settings(dossier_id))
    return {
        "dossier": dossier, "generations": generations, "summary": summary, "fige": fige,
        "latest": generations[0] if generations else None,
        "rfcv_illisible": RFCV_ILLISIBLE if rfcv_illisible else None,
        "can_declare": (not fige and summary is not None and not summary.bloquante and not dossier["error"]
                        and not rfcv_illisible),
        "can_abandon": dossier["status"] == "brouillon",
        "events": svc.events(dossier_id),
        "form": form or {}, "form_errors": form_errors or [], "profiles": list(_profiles()),
        "fob_modes": FOB_MODES, "assurance_modes": ASSURANCE_LIBELLES, "cases": CASES,
        "devise_unite": f"devise du RFCV : {summary.devise}" if summary and summary.devise else "devise du RFCV",
        "nb_articles": summary.nb_articles if summary else None,
    }


# ------------------------------------------------------------------ Dossiers
@router.get("/", response_class=HTMLResponse)
def dossiers(request: Request, q: str = "", user: User = Depends(current_user),
             svc: DossierService = Depends(get_service)):
    return _render(request, "dossiers.html", user, dossiers=svc.list(q), q=q)


# ------------------------------------------------------------------ Nouveau
@router.get("/nouveau", response_class=HTMLResponse)
def nouveau(request: Request, user: User = Depends(current_user)):
    return _render(request, "nouveau.html", user, created=[], errors=[])


@router.post("/nouveau")
def deposer(request: Request, fichiers: list[UploadFile] = File(default=[]),
            user: User = Depends(current_user), svc: DossierService = Depends(get_service)):
    created, errors = [], []
    for f in fichiers:
        content = f.file.read()
        if not f.filename and not content:
            continue                    # champ envoyé sans fichier
        try:
            created.append((svc.create(user, f.filename or "rfcv.pdf", content), f.filename))
        except ValueError as exc:
            errors.append(str(exc))
        except Exception:
            logger.exception("Dépôt de %s", f.filename)
            errors.append(f"« {f.filename} » : erreur à l'enregistrement")
    if not created and not errors:
        errors.append("Choisir au moins un fichier PDF")
    if errors:
        return _render(request, "nouveau.html", user, status_code=200 if created else 422,
                       created=created, errors=errors)
    return RedirectResponse("/", status_code=303)


# ------------------------------------------------------------------ Dossier
@router.get("/dossiers/{dossier_id}", response_class=HTMLResponse)
def dossier(request: Request, dossier_id: int, user: User = Depends(current_user),
            svc: DossierService = Depends(get_service)):
    return _render(request, "dossier.html", user, **_dossier_context(svc, dossier_id))


@router.post("/dossiers/{dossier_id}/generer")
def generer(request: Request, dossier_id: int, values: dict = Depends(form_data),
            user: User = Depends(current_user), svc: DossierService = Depends(get_service)):
    _get_dossier(svc, dossier_id)
    htmx = _is_htmx(request)
    settings, errors = form_to_settings(values)
    message = None
    if settings is not None:
        try:
            svc.generate(user, dossier_id, settings)
        except DossierFige as exc:
            message = str(exc)
    if errors:
        context = _dossier_context(svc, dossier_id, form=values, form_errors=errors)
        if htmx:
            return _render(request, "_reglages.html", user, headers={"HX-Retarget": "#reglages",
                                                                     "HX-Reswap": "innerHTML"}, **context)
        return _render(request, "dossier.html", user, status_code=422, **context)
    if not htmx:
        if message:
            return _render(request, "dossier.html", user, status_code=409, message=message,
                           **_dossier_context(svc, dossier_id))
        return RedirectResponse(f"/dossiers/{dossier_id}", status_code=303)
    return _render(request, "_recap.html", user, htmx=True, message=message,
                   **_dossier_context(svc, dossier_id, form=values))


@router.post("/dossiers/{dossier_id}/declarer")
def declarer(request: Request, dossier_id: int, user: User = Depends(current_user),
             svc: DossierService = Depends(get_service)):
    _get_dossier(svc, dossier_id)
    try:
        svc.declare(user, dossier_id)
    except DeclarationRefusee as exc:
        return _render(request, "dossier.html", user, status_code=409, message=exc.message,
                       conflicts=exc.conflicts, **_dossier_context(svc, dossier_id))
    except DossierFige as exc:
        return _render(request, "dossier.html", user, status_code=409, message=str(exc),
                       **_dossier_context(svc, dossier_id))
    return RedirectResponse(f"/dossiers/{dossier_id}", status_code=303)


@router.post("/dossiers/{dossier_id}/abandonner")
def abandonner(request: Request, dossier_id: int, user: User = Depends(current_user),
               svc: DossierService = Depends(get_service)):
    _get_dossier(svc, dossier_id)
    try:
        svc.abandon(user, dossier_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except DossierFige as exc:
        return _render(request, "dossier.html", user, status_code=409, message=str(exc),
                       **_dossier_context(svc, dossier_id))
    return RedirectResponse(f"/dossiers/{dossier_id}", status_code=303)


@router.post("/dossiers/{dossier_id}/reouvrir")
def reouvrir(request: Request, dossier_id: int, admin: User = Depends(require_admin),
             svc: DossierService = Depends(get_service)):
    _get_dossier(svc, dossier_id)
    try:
        svc.reopen(admin, dossier_id)
    except ValueError as exc:
        return _render(request, "dossier.html", admin, status_code=409, message=str(exc),
                       **_dossier_context(svc, dossier_id))
    return RedirectResponse(f"/dossiers/{dossier_id}", status_code=303)


@router.post("/dossiers/{dossier_id}/brouillon")
def brouillon(request: Request, dossier_id: int, admin: User = Depends(require_admin),
              svc: DossierService = Depends(get_service)):
    _get_dossier(svc, dossier_id)
    try:
        svc.revert_to_draft(admin, dossier_id)
    except ValueError as exc:
        return _render(request, "dossier.html", admin, status_code=409, message=str(exc),
                       **_dossier_context(svc, dossier_id))
    return RedirectResponse(f"/dossiers/{dossier_id}", status_code=303)


# ------------------------------------------------------------------ Châssis (administrateurs)
def _chassis_context(svc: DossierService, vin: str = "", notice: str = "", errors: Optional[list[str]] = None,
                     conflicts: Optional[list[str]] = None, form: Optional[dict] = None) -> dict:
    vin = re.sub(r"\s+", "", vin or "").upper()
    groups: dict[str, dict] = {}
    for row in svc.registry.get_cancelled():
        g = groups.setdefault(normalize_rfcv(row["rfcv_number"]), {
            "rfcv_number": row["rfcv_number"], "count": 0, "reason": row["reason"],
            "cancelled_at": row["cancelled_at"], "restantes": 0})
        g["count"] += 1
        g["restantes"] += row["restored_at"] is None
    return {
        "vin": vin, "notice": notice, "errors": errors or [], "conflicts": conflicts or [], "form": form or {},
        "entry": svc.registry.get_entry(vin) if vin else None,
        "history": svc.registry.get_cancelled(chassis_number=vin) if vin else [],
        "vin_dossiers": svc.list(vin) if vin else [],
        "cancelled": list(groups.values()), "hs_known": svc.hs_known(), "events": svc.recent_events(),
    }


def _chassis_error(request, admin, svc, message, form=None, conflicts=None, vin=""):
    return _render(request, "chassis.html", admin, status_code=422,
                   **_chassis_context(svc, vin=vin, errors=[message], conflicts=conflicts, form=form))


@router.get("/chassis", response_class=HTMLResponse)
def chassis(request: Request, vin: str = "", msg: str = "", admin: User = Depends(require_admin),
            svc: DossierService = Depends(get_service)):
    return _render(request, "chassis.html", admin, **_chassis_context(svc, vin=vin, notice=msg[:300]))


def _chassis_redirect(message: str) -> RedirectResponse:
    return RedirectResponse("/chassis?" + urlencode({"msg": message}), status_code=303)


@router.post("/chassis/annuler")
def chassis_annuler(request: Request, values: dict = Depends(form_data),
                    admin: User = Depends(require_admin), svc: DossierService = Depends(get_service)):
    rfcv, motif = values.get("rfcv", "").strip(), values.get("motif", "").strip()
    try:
        cancelled = svc.cancel_rfcv(admin, rfcv, motif)
    except ValueError as exc:
        return _chassis_error(request, admin, svc, str(exc)[:1].upper() + str(exc)[1:],
                              form={"rfcv": rfcv, "motif": motif})
    if not cancelled:                   # reprise : châssis déjà annulés dans le registre
        return _chassis_redirect(f"RFCV {rfcv} : annulation reprise, ses dossiers déclarés passent « Annulé »")
    return _chassis_redirect(f"RFCV {rfcv} annulé : {len(cancelled)} châssis libérés")


@router.post("/chassis/restaurer/{rfcv}")
def chassis_restaurer(request: Request, rfcv: str, admin: User = Depends(require_admin),
                      svc: DossierService = Depends(get_service)):
    try:
        result = svc.restore_rfcv(admin, rfcv)
    except ValueError as exc:
        return _chassis_error(request, admin, svc, str(exc)[:1].upper() + str(exc)[1:])
    if result["conflicts"]:
        return _render(request, "chassis.html", admin, **_chassis_context(
            svc, conflicts=result["conflicts"],
            notice=f"RFCV {rfcv} : {len(result['restored'])} châssis restauré(s), "
                   f"{len(result['conflicts'])} en conflit (déjà repris par un autre RFCV)"))
    return _chassis_redirect(f"RFCV {rfcv} restauré : {len(result['restored'])} châssis")


@router.post("/chassis/code-sh-normal")
def chassis_code_sh_normal(request: Request, values: dict = Depends(form_data),
                           admin: User = Depends(require_admin), svc: DossierService = Depends(get_service)):
    try:
        svc.mark_hs_known(admin, values.get("designation", ""), values.get("hs_code", ""))
    except ValueError as exc:
        return _chassis_error(request, admin, svc, str(exc))
    retour = values.get("retour", "")
    if re.fullmatch(r"/dossiers/\d+", retour):            # jamais d'adresse externe
        return RedirectResponse(retour, status_code=303)
    return _chassis_redirect("Code SH enregistré comme habituel")


# ------------------------------------------------------------------ téléchargements
def _send_stored(svc: DossierService, dossier: dict, path: Optional[str], kind: str, filename: str):
    """Fichier enregistré du dossier, confiné à son dossier sur le disque (aucun chemin ne vient de l'URL)."""
    introuvable = HTTPException(status_code=404, detail="Fichier introuvable")
    if not path:
        raise introuvable
    resolved = Path(path).resolve()
    folder = (Path(svc.settings.data_dir) / "dossiers" / str(dossier["id"])).resolve()
    if not resolved.is_relative_to(folder) or not resolved.is_file():
        raise introuvable
    return FileResponse(resolved, media_type=FICHIERS[kind], filename=filename)


@router.get("/dossiers/{dossier_id}/pdf")
def pdf_origine(dossier_id: int, svc: DossierService = Depends(get_service)):
    """PDF d'origine du dossier, disponible dès le dépôt."""
    dossier = _get_dossier(svc, dossier_id)
    return _send_stored(svc, dossier, dossier["pdf_path"], "pdf", dossier["filename"])


@router.get("/dossiers/{dossier_id}/fichiers/{n}/{kind}")
def fichier(dossier_id: int, n: int, kind: str, svc: DossierService = Depends(get_service)):
    """Fichiers enregistrés pour ce dossier et cette génération : aucun chemin ne vient de l'URL."""
    introuvable = HTTPException(status_code=404, detail="Fichier introuvable")
    if kind not in FICHIERS:
        raise introuvable
    dossier = _get_dossier(svc, dossier_id)
    generation = next((g for g in svc.generations(dossier_id) if g["n"] == n), None)
    if generation is None:
        raise introuvable
    path = {"xml": generation["xml_path"], "corps": generation["corps_path"], "pdf": dossier["pdf_path"]}[kind]
    stem = Path(dossier["filename"]).stem
    filename = {"xml": f"{stem}.xml", "corps": f"corps_{stem}.txt", "pdf": dossier["filename"]}[kind]
    return _send_stored(svc, dossier, path, kind, filename)
