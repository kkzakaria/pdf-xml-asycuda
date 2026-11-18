"""
Fixtures des tests webapp : clé RSA locale, fabrique de jetons Access, client HTTP.

Aucun accès réseau : la source des clés publiques est remplacée par la clé de test.
"""
import sys
import time
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import chassis_registry  # noqa: E402
from api.main import app  # noqa: E402
from webapp import auth, config  # noqa: E402

REPO_REGISTRY = (Path(__file__).parent.parent.parent / "data" / "chassis_registry.db").resolve()

TEAM_DOMAIN = "groupekarta.cloudflareaccess.com"
AUD = "aud-tag-de-test"


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def make_token(rsa_key):
    """Fabrique un jeton Access signé RS256 par la clé de test."""

    def _make(email="op@karta.ci", aud=AUD, iss=f"https://{TEAM_DOMAIN}",
              exp_delta=300, key=None):
        now = int(time.time())
        claims = {"email": email, "aud": aud, "iss": iss,
                  "iat": now, "exp": now + exp_delta, "sub": "test"}
        return jwt.encode(claims, key or rsa_key, algorithm="RS256",
                          headers={"kid": "test"})

    return _make


@pytest.fixture(autouse=True)
def guard_repo_registry(monkeypatch):
    """Garde : aucun test webapp n'ouvre le registre des châssis du dépôt (data/chassis_registry.db)."""
    original = chassis_registry.ChassisRegistry.__init__

    def guarded(self, db_path=None):
        target = Path(db_path or chassis_registry._DB_DEFAULT).resolve()
        if target == REPO_REGISTRY:
            raise AssertionError(f"Test webapp sur le registre du dépôt : {target}")
        original(self, db_path)

    monkeypatch.setattr(chassis_registry.ChassisRegistry, "__init__", guarded)


@pytest.fixture
def webapp_settings(tmp_path, rsa_key, monkeypatch):
    """Installe des réglages webapp de test ; renvoie une fonction pour les remplacer."""
    monkeypatch.setattr(auth, "_key_source", lambda token: rsa_key.public_key())

    def _install(**overrides):
        values = {"access_aud": AUD, "admins": [], "dev_user": None,
                  "data_dir": tmp_path / "webapp", "registry_path": tmp_path / "r.db"}
        values.update(overrides)
        s = config.WebappSettings(**values)
        monkeypatch.setattr(config, "settings", s)
        return s

    _install()
    return _install


@pytest_asyncio.fixture
async def client(webapp_settings):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
