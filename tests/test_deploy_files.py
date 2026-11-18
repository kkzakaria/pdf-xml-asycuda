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


def test_compose_required_vars_listed_in_env_example():
    import re
    compose = (DEPLOY / "docker-compose.yml").read_text(encoding="utf-8")
    required = set(re.findall(r"\$\{(\w+):\?", compose))
    assert required
    lines = (DEPLOY / ".env.exemple").read_text(encoding="utf-8").splitlines()
    active = {l.split("=", 1)[0].strip() for l in lines if "=" in l and not l.lstrip().startswith("#")}
    assert required <= active, required - active


# ------------------------------------------------------------------ sauvegarde
import os  # noqa: E402
import shutil  # noqa: E402
import sqlite3  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

needs_tools = pytest.mark.skipif(not (shutil.which("sqlite3") and shutil.which("rsync")),
                                 reason="sqlite3 ou rsync absent")


def _data_dir(tmp_path):
    data = tmp_path / "data"
    (data / "webapp" / "dossiers" / "1" / "gen-1").mkdir(parents=True)
    (data / "webapp" / "dossiers" / "1" / "a.pdf").write_bytes(b"%PDF-1.4")
    (data / "webapp" / "dossiers" / "1" / "gen-1" / "a.xml").write_text("<x/>")
    for path in (data / "webapp" / "webapp.db", data / "chassis_registry.db"):
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE t (x)")
        conn.commit()
        conn.close()
    return data


def _run_backup(data, **env):
    return subprocess.run(["bash", str(DEPLOY / "sauvegarde.sh")], capture_output=True, text=True,
                          env={**os.environ, "DATA_DIR": str(data), **env}, timeout=60)


@needs_tools
def test_backup_mirrors_dossiers_without_archive(tmp_path):
    data = _data_dir(tmp_path)
    r = _run_backup(data)
    assert r.returncode == 0, r.stderr
    dest = data / "sauvegardes"
    assert len(list(dest.glob("webapp-*.db"))) == 1 and len(list(dest.glob("chassis_registry-*.db"))) == 1
    assert not list(dest.glob("*.tar.gz"))
    mirror = dest / "dossiers-miroir" / "1"
    assert (mirror / "a.pdf").read_bytes() == b"%PDF-1.4" and (mirror / "gen-1" / "a.xml").exists()
    # miroir incrémental, jamais de suppression : un dossier retiré à la source reste copié
    shutil.rmtree(data / "webapp" / "dossiers" / "1" / "gen-1")
    assert _run_backup(data).returncode == 0
    assert (mirror / "gen-1" / "a.xml").exists()


@needs_tools
def test_backup_pushes_off_host_and_fails_loudly(tmp_path):
    data = _data_dir(tmp_path)
    remote = tmp_path / "nas"
    remote.mkdir()
    r = _run_backup(data, BACKUP_REMOTE=f"{remote}/")
    assert r.returncode == 0, r.stderr
    assert list(remote.glob("webapp-*.db")) and (remote / "dossiers-miroir" / "1" / "a.pdf").exists()
    r = _run_backup(data, BACKUP_REMOTE=str(tmp_path / "absent" / "encore" / "nas") + "/")
    assert r.returncode != 0
    assert "hors serveur" in r.stderr


def test_installation_documents_off_host_copy():
    doc = (DEPLOY / "INSTALLATION.md").read_text(encoding="utf-8")
    assert "BACKUP_REMOTE" in doc and "rsync" in doc and "df -h" in doc
