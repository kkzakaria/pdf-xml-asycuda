"""
Date de la FDI (ligne 6610 et Identification/FDI_date) : la date de VALIDATION de la FDI fait foi
(décision de l'opérateur ; 31917 : RFCV 28/10/2026, FDI validée le 02/11/2026, levée réussie
avec le 02/11). Priorité : date saisie, puis PDF de la FDI, puis date du RFCV avec avertissement.
FDI fictives générées ; une vraie FDI se teste hors dépôt (variable FDI_REELLE).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fdi_fictive import ecrire_pdf, fdi_fictive  # noqa: E402
from test_ecarts_karta_31917 import LEGACY_TEXT  # noqa: E402
from test_rfcv_format_2026 import parse_text  # noqa: E402

from chassis_registry import ChassisRegistry  # noqa: E402
from fdi import ControleFDI, appliquer_fdi, lire_fdi  # noqa: E402

FDI_RFCV = "260100000"          # n° et date de FDI du RFCV fictif (LEGACY_TEXT)
DATE_RFCV = "28/10/2026"


@pytest.fixture
def rfcv(tmp_path):
    return parse_text(LEGACY_TEXT, ChassisRegistry(str(tmp_path / "r.db")), tmp_path,
                      register_chassis=False, taux_douane=596.302)


def dates_6610(data):
    return [d.document_date for it in data.items for d in it.attached_documents if d.code == "6610"]


# ------------------------------------------------------------------ lecture du PDF de la FDI
def test_lire_fdi_date_de_validation(tmp_path):
    info = lire_fdi(fdi_fictive(tmp_path / "fdi.pdf", numero="260100000", date_validation="02/11/2026"))
    assert info.numero == "260100000" and info.date_validation == "02/11/2026"


def test_lire_fdi_ignore_la_date_de_soumission(tmp_path):
    # la date de soumission (28/10) est sur la même page : seule la valeur sous « 5. Date Validation »
    info = lire_fdi(fdi_fictive(tmp_path / "fdi.pdf", date_validation="02/11/2026", date_soumission="28/10/2026"))
    assert info.date_validation == "02/11/2026"


def test_lire_fdi_refuse_un_autre_pdf(tmp_path):
    autre = ecrire_pdf(tmp_path / "autre.pdf", [(50, 50, "RAPPORT FINAL"), (50, 80, "Date : 01/01/2026")])
    with pytest.raises(ValueError, match="FDI"):
        lire_fdi(autre)


def test_lire_fdi_sans_date_lisible(tmp_path):
    pdf = ecrire_pdf(tmp_path / "fdi.pdf", [(306, 162, "4. N° FDI"), (306, 173.5, "260100000"),
                                            (446, 162, "5. Date Validation")])
    info = lire_fdi(pdf)
    assert info.numero == "260100000" and info.date_validation is None


@pytest.mark.skipif(not os.environ.get("FDI_REELLE"), reason="FDI réelle hors dépôt (FDI_REELLE=chemin)")
def test_lire_fdi_reelle():
    info = lire_fdi(Path(os.environ["FDI_REELLE"]))
    assert info.numero == os.environ.get("FDI_REELLE_NUMERO", info.numero)
    assert info.date_validation == os.environ.get("FDI_REELLE_DATE", info.date_validation)


# ------------------------------------------------------------------ priorité et application
def test_sans_fdi_date_du_rfcv_non_verifiee(rfcv):
    controle = appliquer_fdi(rfcv)
    assert controle == ControleFDI(source="rfcv", date=DATE_RFCV, date_rfcv=DATE_RFCV,
                                   numero_rfcv=FDI_RFCV, numero_fdi=None)
    assert rfcv.identification.fdi_date == DATE_RFCV and dates_6610(rfcv) == [DATE_RFCV]


def test_pdf_de_fdi_remplace_la_date(rfcv, tmp_path):
    controle = appliquer_fdi(rfcv, fdi_pdf=fdi_fictive(tmp_path / "fdi.pdf", numero=FDI_RFCV))
    assert controle.source == "fdi" and controle.date == "02/11/2026" and controle.numero_fdi == FDI_RFCV
    assert rfcv.identification.fdi_date == "02/11/2026" and dates_6610(rfcv) == ["02/11/2026"]


def test_date_saisie_prioritaire(rfcv, tmp_path):
    controle = appliquer_fdi(rfcv, date_fdi="03/11/2026",
                             fdi_pdf=fdi_fictive(tmp_path / "fdi.pdf", numero=FDI_RFCV))
    assert controle.source == "saisie" and controle.date == "03/11/2026"
    assert controle.numero_fdi == FDI_RFCV          # le PDF sert encore au contrôle du numéro
    assert dates_6610(rfcv) == ["03/11/2026"]


@pytest.mark.parametrize("saisie", ["2026-11-02", "32/11/2026", "2/11/26", "02/13/2026"])
def test_date_saisie_invalide(rfcv, saisie):
    with pytest.raises(ValueError, match="JJ/MM/AAAA"):
        appliquer_fdi(rfcv, date_fdi=saisie)


def test_pdf_sans_date_garde_le_rfcv(rfcv, tmp_path):
    pdf = ecrire_pdf(tmp_path / "fdi.pdf", [(306, 162, "4. N° FDI"), (306, 173.5, FDI_RFCV),
                                            (446, 162, "5. Date Validation")])
    controle = appliquer_fdi(rfcv, fdi_pdf=pdf)
    assert controle.source == "rfcv" and controle.date == DATE_RFCV


def test_numero_different_conserve(rfcv, tmp_path):
    controle = appliquer_fdi(rfcv, fdi_pdf=fdi_fictive(tmp_path / "fdi.pdf", numero="260199999"))
    assert controle.numero_fdi == "260199999" and controle.numero_rfcv == FDI_RFCV
    assert controle.numero_different


# ------------------------------------------------------------------ génération : résumé et XML
@pytest.fixture
def faux_rfcv(monkeypatch, tmp_path):
    """generate() lit le RFCV fictif (format 2026 : FDI 260200000 du 30/10/2026)."""
    import rfcv_parser
    from test_rfcv_format_2026 import MULTILINE_TEXT

    class Extracteur:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_all_text(self):
            return MULTILINE_TEXT

        def extract_all_tables(self):
            return []

    monkeypatch.setattr(rfcv_parser, "PDFExtractor", Extracteur)
    return tmp_path / "rfcv.pdf"


def generer(tmp_path, pdf, **reglages):
    from generation import GenerationSettings, generate
    return generate(pdf, GenerationSettings(taux_douane=596.302, **reglages), tmp_path / "out", "d",
                    ChassisRegistry(str(tmp_path / "g.db")))


def alertes(resultat):
    return {a.code: a for a in resultat.summary.alertes}


def test_generation_sans_fdi_avertit(tmp_path, faux_rfcv):
    r = generer(tmp_path, faux_rfcv)
    a = alertes(r)["fdi_date_non_verifiee"]
    assert not a.bloquante
    assert a.message == ("Date de FDI non vérifiée (date de la RFCV : 30/10/2026) : "
                         "fournir la FDI ou la date de validation")


def test_generation_avec_fdi(tmp_path, faux_rfcv):
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260200000", date_validation="03/11/2026")
    r = generer(tmp_path, faux_rfcv, fdi_pdf=str(pdf))
    assert "fdi_date_non_verifiee" not in alertes(r) and "fdi_numero" not in alertes(r)
    xml = r.xml_path.read_text(encoding="utf-8")
    assert "<FDI_date>11/3/26</FDI_date>" in xml.replace(" ", "")
    assert "Date de FDI : 30/10/2026 (RFCV) → 03/11/2026 (FDI validée)" in r.summary.ecarts


def test_generation_date_saisie(tmp_path, faux_rfcv):
    r = generer(tmp_path, faux_rfcv, date_fdi="04/11/2026")
    assert "fdi_date_non_verifiee" not in alertes(r)
    assert "Date de FDI : 30/10/2026 (RFCV) → 04/11/2026 (saisie)" in r.summary.ecarts


def test_generation_numero_fdi_different_bloque(tmp_path, faux_rfcv):
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260299999")
    a = alertes(generer(tmp_path, faux_rfcv, fdi_pdf=str(pdf)))["fdi_numero"]
    assert a.bloquante and "260299999" in a.message and "260200000" in a.message


# ------------------------------------------------------------------ ligne de commande
def test_cli_sans_fdi_avertit(tmp_path, faux_rfcv, capsys):
    from converter import convert_pdf_to_xml
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    assert convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302)
    assert "Date de FDI non vérifiée (date de la RFCV : 30/10/2026)" in capsys.readouterr().err


def test_cli_date_fdi(tmp_path, faux_rfcv, capsys):
    from converter import convert_pdf_to_xml
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260200000", date_validation="03/11/2026")
    assert convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302, fdi_pdf=str(pdf))
    xml = (tmp_path / "o.xml").read_text(encoding="utf-8").replace(" ", "")
    assert "<FDI_date>11/3/26</FDI_date>" in xml and "non vérifiée" not in capsys.readouterr().err


def test_cli_numero_fdi_different(tmp_path, faux_rfcv, capsys):
    from converter import convert_pdf_to_xml
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260299999")
    convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302, fdi_pdf=str(pdf))
    assert "BLOQUANT : N° de FDI différent : FDI 260299999, RFCV 260200000" in capsys.readouterr().err


def test_cli_options_fdi():
    import converter
    aide = converter.build_parser().format_help()
    assert "--date-fdi" in aide and "--fdi" in aide


# ------------------------------------------------------------------ revue PR #69
def test_date_saisie_differente_de_la_fdi(rfcv, tmp_path):
    controle = appliquer_fdi(rfcv, date_fdi="03/11/2026",
                             fdi_pdf=fdi_fictive(tmp_path / "fdi.pdf", numero=FDI_RFCV, date_validation="02/11/2026"))
    assert controle.date == "03/11/2026" and controle.date_fdi_pdf == "02/11/2026"
    assert controle.date_saisie_differente


def test_date_saisie_egale_a_la_fdi(rfcv, tmp_path):
    controle = appliquer_fdi(rfcv, date_fdi="02/11/2026",
                             fdi_pdf=fdi_fictive(tmp_path / "fdi.pdf", numero=FDI_RFCV, date_validation="02/11/2026"))
    assert not controle.date_saisie_differente


def test_alertes_fdi_messages(rfcv, tmp_path):
    from fdi import alertes_fdi
    assert alertes_fdi(appliquer_fdi(rfcv)) == [(
        "fdi_date_non_verifiee",
        f"Date de FDI non vérifiée (date de la RFCV : {DATE_RFCV}) : fournir la FDI ou la date de validation",
        False)]
    sans_date = ecrire_pdf(tmp_path / "sd.pdf", [(306, 162, "4. N° FDI"), (306, 173.5, FDI_RFCV),
                                                 (446, 162, "5. Date Validation")])
    assert alertes_fdi(appliquer_fdi(rfcv, fdi_pdf=sans_date)) == [(
        "fdi_date_non_verifiee",
        f"Date de validation illisible sur la FDI : saisir la date de validation (date de la RFCV : {DATE_RFCV} reprise)",
        False)]
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero=FDI_RFCV, date_validation="02/11/2026")
    assert alertes_fdi(appliquer_fdi(rfcv, date_fdi="03/11/2026", fdi_pdf=pdf)) == [(
        "fdi_date_differente",
        "Date de FDI saisie (03/11/2026) différente de la date de validation de la FDI (02/11/2026)",
        True)]


def test_generation_date_saisie_differente_bloque(tmp_path, faux_rfcv):
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260200000", date_validation="02/11/2026")
    a = alertes(generer(tmp_path, faux_rfcv, date_fdi="03/11/2026", fdi_pdf=str(pdf)))["fdi_date_differente"]
    assert a.bloquante


def test_cli_numero_different_code_de_sortie(tmp_path, faux_rfcv):
    from converter import convert_pdf_to_xml
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260299999")
    assert convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302, fdi_pdf=str(pdf)) is False


def test_cli_date_saisie_differente_code_de_sortie(tmp_path, faux_rfcv, capsys):
    from converter import convert_pdf_to_xml
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    pdf = fdi_fictive(tmp_path / "fdi.pdf", numero="260200000", date_validation="02/11/2026")
    ok = convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302,
                            date_fdi="03/11/2026", fdi_pdf=str(pdf))
    assert ok is False
    assert "BLOQUANT : Date de FDI saisie (03/11/2026) différente" in capsys.readouterr().err


def test_api_avertit_date_fdi(tmp_path, faux_rfcv):
    sys.path.insert(0, str(ROOT / "src" / "api"))
    from api.services.conversion_service import ConversionService
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    r = ConversionService.convert_pdf_to_xml(str(faux_rfcv), str(tmp_path / "o.xml"), taux_douane=596.302)
    assert r["success"]
    assert any("Date de FDI non vérifiée" in a for a in r["avertissements"])


def test_batch_avertit_date_fdi(tmp_path, faux_rfcv):
    from batch_processor import BatchProcessor
    faux_rfcv.write_bytes(b"%PDF-1.4\n")
    res = BatchProcessor._process_single_file(faux_rfcv, str(tmp_path / "out"), taux_douane=596.302)
    assert res.success and "Date de FDI non vérifiée" in (res.fdi_warning or "")
