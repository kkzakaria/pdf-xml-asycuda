"""
Authentification par Cloudflare Access.

Cloudflare Access place devant l'application un jeton JWT signé (RS256) : en-tête
`Cf-Access-Jwt-Assertion` ou cookie `CF_Authorization`. Le garde `access_guard`
le vérifie sur toute l'application (pages et /api/…, sauf le health check) :
signature par les clés publiques de l'équipe Zero Trust, audience = AUD de
l'application, émetteur = https://<team_domain>, expiration. L'identité est
l'e-mail du jeton.
"""
import logging
import threading
from dataclasses import dataclass
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import config, db

logger = logging.getLogger(__name__)

TOKEN_HEADER = "Cf-Access-Jwt-Assertion"
TOKEN_COOKIE = "CF_Authorization"
JWKS_CACHE_SECONDS = 3600

# Routes ouvertes sans jeton (supervision du conteneur).
OPEN_ROUTES = {("GET", "/api/v1/health"), ("HEAD", "/api/v1/health")}

@dataclass(frozen=True)
class User:
    email: str
    is_admin: bool


class InvalidToken(Exception):
    """Jeton Access absent ou invalide."""


# --- Clés publiques ------------------------------------------------------------

_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_jwks_lock = threading.Lock()


def certs_url(team_domain: str) -> str:
    return f"https://{team_domain}/cdn-cgi/access/certs"


def _jwks_key_source(token: str):
    """Clé publique (selon le `kid` du jeton) tirée des certificats de l'équipe, en cache."""
    url = certs_url(config.get_settings().team_domain)
    with _jwks_lock:
        client = _jwks_clients.get(url)
        if client is None:
            client = jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=JWKS_CACHE_SECONDS,
                                     timeout=10)
            _jwks_clients[url] = client
    return client.get_signing_key_from_jwt(token).key


# Source des clés : remplaçable (tests) par une fonction jeton -> clé publique.
_key_source: Callable = _jwks_key_source


def set_key_source(source: Callable | None) -> None:
    """Remplace la source des clés publiques (None : certificats Cloudflare)."""
    global _key_source
    _key_source = source or _jwks_key_source


# --- Vérification --------------------------------------------------------------

def verify_token(token: str, settings: config.WebappSettings) -> str:
    """Vérifie le jeton Access et renvoie l'e-mail (minuscules). Lève InvalidToken."""
    if not settings.access_aud:
        raise InvalidToken("AUD non configuré")
    try:
        key = _key_source(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.access_aud,
            issuer=f"https://{settings.team_domain}",
            options={"require": ["exp", "iss", "aud"]},
        )
    except Exception as exc:  # jeton mal formé, signature, aud, iss, exp, clés…
        raise InvalidToken(type(exc).__name__) from exc
    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise InvalidToken("e-mail absent")
    return email.strip().lower()


def make_user(email: str, settings: config.WebappSettings) -> User:
    email = email.strip().lower()
    return User(email=email, is_admin=email in settings.admins)


# --- Base des utilisateurs -----------------------------------------------------

_initialized_dbs: set[str] = set()
_db_lock = threading.Lock()


def record_user(email: str, settings: config.WebappSettings) -> None:
    """Crée la base au besoin et enregistre la visite de l'utilisateur."""
    path = settings.db_path
    conn = db.connect(path)
    try:
        with _db_lock:
            if str(path.resolve()) not in _initialized_dbs:
                db.init(conn)
                _initialized_dbs.add(str(path.resolve()))
        db.upsert_user(conn, email)
    finally:
        conn.close()


def _authenticate(token: str | None, settings: config.WebappSettings) -> User:
    """Exécuté hors de la boucle (réseau éventuel pour les clés, SQLite)."""
    if settings.mode == "access":
        if not token:
            raise InvalidToken("jeton absent")
        email = verify_token(token, settings)
    else:  # mode développement
        email = settings.dev_user
    user = make_user(email, settings)
    record_user(user.email, settings)
    return user


# --- Garde et dépendances FastAPI ----------------------------------------------

async def access_guard(request: Request, call_next):
    """Middleware HTTP : exige un utilisateur authentifié sur toute l'application."""
    if (request.method, request.url.path) in OPEN_ROUTES:
        return await call_next(request)

    settings = config.get_settings()
    if settings.mode == "non_configure":
        # Aucun utilisateur n'est établi : les routes de la webapp (qui exigent
        # current_user) répondent 503 ; l'API existante garde sa clé X-API-Key.
        return await call_next(request)

    token = request.headers.get(TOKEN_HEADER) or request.cookies.get(TOKEN_COOKIE)
    try:
        user = await run_in_threadpool(_authenticate, token, settings)
    except InvalidToken as exc:
        logger.warning("Accès refusé (%s) : %s %s", exc, request.method, request.url.path)
        return JSONResponse({"detail": "Authentification Cloudflare Access requise"},
                            status_code=401)
    request.state.user = user
    return await call_next(request)


def current_user(request: Request) -> User:
    """Utilisateur authentifié par le garde (503 si l'accès n'est pas configuré, 401 sinon)."""
    user = getattr(request.state, "user", None)
    if not isinstance(user, User):
        if config.get_settings().mode == "non_configure":
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Accès non configuré")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentification Cloudflare Access requise")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Réservé aux administrateurs")
    return user


def log_startup_mode(settings: config.WebappSettings | None = None) -> None:
    """Annonce le mode d'accès au démarrage."""
    settings = settings or config.get_settings()
    if settings.mode == "access":
        logger.info("Webapp : authentification Cloudflare Access (%s)", settings.team_domain)
    elif settings.mode == "dev":
        logger.warning("!" * 70)
        logger.warning("Webapp en MODE DÉVELOPPEMENT : toutes les requêtes sont traitées "
                       "comme %s, SANS vérification Cloudflare Access. "
                       "Ne jamais utiliser en production.", settings.dev_user)
        logger.warning("!" * 70)
    else:
        logger.warning("Webapp : accès non configuré (ni WEBAPP_ACCESS_AUD ni "
                       "WEBAPP_DEV_USER) — les pages répondent 503.")
