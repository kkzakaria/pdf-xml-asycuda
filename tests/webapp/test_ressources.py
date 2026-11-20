"""
Ressources de l'interface : CSS compilé localement, police et logo servis par l'application,
aucune ressource externe au chargement (l'interface doit s'afficher sans CDN ni Google Fonts).
"""
import re
from pathlib import Path

import pytest

WEBAPP = Path(__file__).resolve().parents[2] / "src" / "webapp"
ROOT = Path(__file__).resolve().parents[2]



@pytest.fixture
def operateur(webapp_settings, tmp_path):
    webapp_settings(access_aud="", dev_user="op@karta.ci", registry_path=tmp_path / "registre.db",
                    profile_path=ROOT / "profils" / "karta-transit.ini")


def test_templates_sans_url_externe():
    for gabarit in (WEBAPP / "templates").glob("*.html"):
        texte = re.sub(r'xmlns="[^"]*"', "", gabarit.read_text(encoding="utf-8"))
        assert "http://" not in texte and "https://" not in texte, gabarit.name


@pytest.mark.asyncio
async def test_base_lie_css_local(client, operateur):
    r = await client.get("/")
    assert r.status_code == 200
    assert re.search(r'href="/static/app\.css(\?v=[0-9a-f]+)?"', r.text)
    assert "fonts.googleapis" not in r.text and "cdn." not in r.text


@pytest.mark.asyncio
async def test_logo_et_polices_servis(client, operateur):
    logo = await client.get("/static/img/logo-karta-transit.jpg")
    assert logo.status_code == 200 and logo.headers["content-type"] == "image/jpeg"
    assert len(logo.content) <= 60 * 1024
    licence = await client.get("/static/fonts/OFL.txt")
    assert licence.status_code == 200 and "SIL OPEN FONT LICENSE" in licence.text.upper()


def test_entree_tailwind_declare_le_theme():
    entree = (WEBAPP / "styles" / "app.css").read_text(encoding="utf-8")
    assert '@import "tailwindcss"' in entree
    assert "--color-karta-bleu: #1B1BA8" in entree
    assert '@source "../templates"' in entree
    assert "/static/fonts/" in entree


@pytest.mark.asyncio
async def test_statiques_versionnes_par_contenu(client, operateur, tmp_path, monkeypatch):
    """Cloudflare et les navigateurs gardent les .css en cache : l'adresse change avec le contenu."""
    from webapp import routes
    css = tmp_path / "app.css"
    css.write_text("a{}")
    monkeypatch.setattr(routes, "STATIC_DIR", tmp_path)
    for nom in ("htmx.min.js",):
        (tmp_path / nom).write_text("x")
    page1 = (await client.get("/")).text
    m1 = re.search(r'href="/static/app\.css\?v=([0-9a-f]{8,})"', page1)
    assert m1, "lien CSS sans version"
    css.write_text("a{color:red}")
    page2 = (await client.get("/")).text
    m2 = re.search(r'href="/static/app\.css\?v=([0-9a-f]{8,})"', page2)
    assert m2 and m2.group(1) != m1.group(1)
    assert re.search(r'src="/static/htmx\.min\.js\?v=[0-9a-f]{8,}"', page2)
