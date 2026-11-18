"""Tests de l'authentification Cloudflare Access de la webapp."""
import sqlite3

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from webapp import auth, config
from webapp.auth import User

HEADER = "Cf-Access-Jwt-Assertion"


@pytest.mark.asyncio
async def test_valid_token_gives_user(client, make_token, webapp_settings):
    s = webapp_settings()
    r = await client.get("/", headers={HEADER: make_token(email="Op@Karta.ci")})
    assert r.status_code == 200
    assert "Connecté : op@karta.ci" in r.text
    # cookie CF_Authorization accepté aussi
    client.cookies.set("CF_Authorization", make_token(email="b@karta.ci"))
    r = await client.get("/")
    client.cookies.clear()
    assert r.status_code == 200 and "b@karta.ci" in r.text
    # utilisateur enregistré
    conn = sqlite3.connect(s.data_dir / "webapp.db")
    emails = {row[0] for row in conn.execute("SELECT email FROM users")}
    conn.close()
    assert emails == {"op@karta.ci", "b@karta.ci"}


@pytest.mark.asyncio
async def test_missing_token_401(client):
    r = await client.get("/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_audience_rejected(client, make_token):
    r = await client.get("/", headers={HEADER: make_token(aud="autre-application")})
    assert r.status_code == 401
    r = await client.get("/", headers={HEADER: make_token(iss="https://autre.cloudflareaccess.com")})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_bad_signature_rejected(client, make_token):
    from cryptography.hazmat.primitives.asymmetric import rsa
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    r = await client.get("/", headers={HEADER: make_token(key=other)})
    assert r.status_code == 401
    r = await client.get("/", headers={HEADER: "pas-un-jeton"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected(client, make_token):
    r = await client.get("/", headers={HEADER: make_token(exp_delta=-60)})
    assert r.status_code == 401


def _probe_app():
    """Petite application qui expose current_user / require_admin derrière le garde."""
    probe = FastAPI()
    probe.middleware("http")(auth.access_guard)

    @probe.get("/moi")
    async def moi(user: User = Depends(auth.current_user)):
        return {"email": user.email, "is_admin": user.is_admin}

    @probe.get("/admin")
    async def admin(user: User = Depends(auth.require_admin)):
        return {"ok": True}

    return probe


@pytest.mark.asyncio
async def test_admin_from_config(webapp_settings, make_token):
    webapp_settings(admins="Chef@Karta.ci, autre@karta.ci")
    transport = ASGITransport(app=_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/moi", headers={HEADER: make_token(email="chef@karta.ci")})
        assert r.json() == {"email": "chef@karta.ci", "is_admin": True}
        r = await c.get("/admin", headers={HEADER: make_token(email="chef@karta.ci")})
        assert r.status_code == 200
        r = await c.get("/moi", headers={HEADER: make_token(email="op@karta.ci")})
        assert r.json()["is_admin"] is False
        r = await c.get("/admin", headers={HEADER: make_token(email="op@karta.ci")})
        assert r.status_code == 403


def test_admins_from_env(monkeypatch):
    monkeypatch.setenv("WEBAPP_ADMINS", "A@x.ci,b@x.ci")
    monkeypatch.setenv("WEBAPP_ACCESS_AUD", "x")
    s = config.WebappSettings()
    assert s.admins == ["a@x.ci", "b@x.ci"]


@pytest.mark.asyncio
async def test_dev_user_mode(client, webapp_settings):
    webapp_settings(access_aud="", dev_user="dev@karta.ci", admins=["dev@karta.ci"])
    r = await client.get("/")
    assert r.status_code == 200
    assert "Connecté : dev@karta.ci" in r.text


def test_both_dev_and_aud_refused(tmp_path):
    with pytest.raises(ValidationError, match="développement"):
        config.WebappSettings(access_aud="aud", dev_user="dev@karta.ci", data_dir=tmp_path)
    s = config.WebappSettings(access_aud="aud", data_dir=tmp_path)
    with pytest.raises(ValidationError):
        s.dev_user = "dev@karta.ci"


@pytest.mark.asyncio
async def test_unconfigured_pages_503(client, webapp_settings, make_token):
    webapp_settings(access_aud="", dev_user=None)
    r = await client.get("/", headers={HEADER: make_token()})
    assert r.status_code == 503
    assert "Accès non configuré" in r.text
    # aucun utilisateur établi, même avec un jeton : current_user refuse
    r = await client.get("/route-inconnue")
    assert r.status_code == 404
    # les routes /api existantes gardent leur comportement (X-API-Key)
    r = await client.get("/api")
    assert r.status_code == 200
    assert "endpoints" in r.json()


@pytest.mark.asyncio
async def test_api_routes_also_guarded(client, make_token):
    for path in ("/api", "/api/v1/metrics", "/openapi.json", "/docs"):
        r = await client.get(path)
        assert r.status_code == 401, path
    r = await client.get("/api", headers={HEADER: make_token()})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health_open(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_jwks_source_url_and_cache(monkeypatch, rsa_key, make_token, webapp_settings):
    """La source par défaut lit les certificats de l'équipe, une seule fois (cache)."""
    s = webapp_settings()
    jwk = jwt_algorithms_rsa().to_jwk(rsa_key.public_key(), as_dict=True)
    jwk.update(kid="test", use="sig", alg="RS256")
    calls = []

    def fake_fetch(self):
        calls.append(self.uri)
        return {"keys": [jwk]}

    monkeypatch.setattr(auth.jwt.PyJWKClient, "fetch_data", fake_fetch)
    monkeypatch.setattr(auth, "_jwks_clients", {})
    monkeypatch.setattr(auth, "_key_source", auth._jwks_key_source)
    assert auth.verify_token(make_token(email="a@karta.ci"), s) == "a@karta.ci"
    assert auth.verify_token(make_token(email="b@karta.ci"), s) == "b@karta.ci"
    assert calls == ["https://groupekarta.cloudflareaccess.com/cdn-cgi/access/certs"]


def jwt_algorithms_rsa():
    from jwt.algorithms import RSAAlgorithm
    return RSAAlgorithm


def test_record_user_throttled(webapp_settings, monkeypatch):
    """Au plus une écriture par minute et par e-mail ; une erreur de base ne casse pas la requête."""
    s = webapp_settings()
    calls = []
    original = auth.db.upsert_user
    monkeypatch.setattr(auth.db, "upsert_user", lambda conn, email: (calls.append(email), original(conn, email)))
    clock = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    auth.record_user("a@karta.ci", s)
    auth.record_user("a@karta.ci", s)
    auth.record_user("b@karta.ci", s)
    assert calls == ["a@karta.ci", "b@karta.ci"]
    clock[0] += 61
    auth.record_user("a@karta.ci", s)
    assert calls == ["a@karta.ci", "b@karta.ci", "a@karta.ci"]

    def broken(conn, email):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(auth.db, "upsert_user", broken)
    clock[0] += 61
    auth.record_user("a@karta.ci", s)          # journalisé, pas d'exception
    monkeypatch.setattr(auth.db, "upsert_user", lambda conn, email: calls.append(email))
    auth.record_user("a@karta.ci", s)          # l'échec n'a pas compté comme une visite
    assert calls[-1] == "a@karta.ci" and len(calls) == 4
