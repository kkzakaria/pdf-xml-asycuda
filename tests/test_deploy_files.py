"""Fichiers de déploiement serveur : aucun port publié, variables requises listées."""
from pathlib import Path

import yaml

DEPLOY = Path(__file__).resolve().parent.parent / "deploy" / "serveur"


def test_compose_publishes_no_port():
    compose = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"app", "cloudflared"} <= set(compose["services"])
    for name, service in compose["services"].items():
        assert "ports" not in service, f"{name} publie un port"


def test_env_example_lists_required_vars():
    lines = (DEPLOY / ".env.exemple").read_text(encoding="utf-8").splitlines()
    active = {l.split("=", 1)[0].strip() for l in lines if "=" in l and not l.lstrip().startswith("#")}
    assert {"WEBAPP_ACCESS_AUD", "WEBAPP_ADMINS", "TUNNEL_TOKEN"} <= active
    assert "WEBAPP_DEV_USER" not in active
