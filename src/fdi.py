"""
Date de la FDI (Fiche de Déclaration à l'Importation, DGCE) portée par la déclaration :
Identification/FDI_date et date du document joint 6610 (NUMERO FDI).

Décision de l'opérateur : la date de VALIDATION de la FDI fait foi, pas la date imprimée sur le
RFCV (31917 : RFCV 28/10/2026, FDI validée le 02/11/2026 ; la levée a réussi avec le 02/11).
Priorité : date saisie, puis date lue dans le PDF de la FDI, puis date du RFCV (signalée « non
vérifiée » par le résumé de génération).

Lecture du PDF par position (pdfplumber), comme sydam-cli (cli/internal/fdi) : la valeur est
imprimée sous son étiquette, dans la même colonne (11,5 points plus bas sur la FDI réelle).
"""
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pdfplumber

ETIQUETTE_NUMERO = "4. N° FDI"
ETIQUETTE_DATE = "5. Date Validation"

# Tolérances de mise en page (points PDF), relevées sur une FDI réelle
_DESSOUS_MIN, _DESSOUS_MAX = 3.0, 16.0     # écart vertical étiquette -> valeur
_COLONNE = 4.0                             # écart horizontal admis entre étiquette et valeur
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")


@dataclass(frozen=True)
class FDIInfo:
    numero: Optional[str]
    date_validation: Optional[str]


@dataclass(frozen=True)
class ControleFDI:
    """Origine de la date de FDI retenue : « saisie », « fdi » (PDF) ou « rfcv »."""
    source: Optional[str]
    date: Optional[str]
    date_rfcv: Optional[str]
    numero_rfcv: Optional[str]
    numero_fdi: Optional[str]

    @property
    def numero_different(self) -> bool:
        return bool(self.numero_fdi and self.numero_rfcv and self.numero_fdi != self.numero_rfcv)


def _norm(texte: str) -> str:
    return " ".join(texte.split())


def _valeur_sous(mots: list[dict], etiquette: dict) -> Optional[str]:
    """Texte imprimé sous l'étiquette, dans la même colonne (le plus proche)."""
    candidats = [m for m in mots
                 if abs(m["x0"] - etiquette["x0"]) <= _COLONNE
                 and _DESSOUS_MIN <= m["top"] - etiquette["top"] <= _DESSOUS_MAX]
    if not candidats:
        return None
    return _norm(min(candidats, key=lambda m: m["top"])["text"]) or None


def lire_fdi(pdf_path) -> FDIInfo:
    """N° et date de validation d'une FDI ; ValueError si le PDF n'est pas une FDI lisible."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            mots = page.extract_words(keep_blank_chars=True, x_tolerance=1.5)
            etiquettes = {_norm(m["text"]): m for m in mots}
            if ETIQUETTE_NUMERO not in etiquettes:
                continue
            numero = _valeur_sous(mots, etiquettes[ETIQUETTE_NUMERO])
            date = _valeur_sous(mots, etiquettes[ETIQUETTE_DATE]) if ETIQUETTE_DATE in etiquettes else None
            return FDIInfo(numero=numero, date_validation=date if date and _DATE.match(date) else None)
    raise ValueError(f"{Path(pdf_path).name} n'est pas une FDI lisible (étiquette « {ETIQUETTE_NUMERO} » absente)")


def valider_date(texte: str) -> str:
    """Date saisie au format JJ/MM/AAAA (date réelle) ; ValueError sinon."""
    t = (texte or "").strip()
    if not _DATE.match(t):
        raise ValueError(f"Date de FDI « {texte} » : format attendu JJ/MM/AAAA")
    try:
        datetime.strptime(t, "%d/%m/%Y")
    except ValueError:
        raise ValueError(f"Date de FDI « {texte} » invalide : format attendu JJ/MM/AAAA") from None
    return t


def appliquer_fdi(rfcv_data, date_fdi: Optional[str] = None, fdi_pdf=None) -> ControleFDI:
    """
    Retient la date de FDI (saisie > PDF de la FDI > RFCV) et l'écrit dans Identification et sur
    le document joint 6610. Le PDF, s'il est fourni, sert aussi au contrôle du n° de FDI.
    """
    ident = rfcv_data.identification
    date_rfcv = ident.fdi_date if ident else None
    numero_rfcv = ident.fdi_number if ident else None
    info = lire_fdi(fdi_pdf) if fdi_pdf else None

    if date_fdi:
        source, date = "saisie", valider_date(date_fdi)
    elif info and info.date_validation:
        source, date = "fdi", info.date_validation
    elif date_rfcv:
        source, date = "rfcv", date_rfcv
    else:
        source, date = None, None

    if date and source != "rfcv":
        if ident is not None:
            ident.fdi_date = date
        for item in rfcv_data.items or []:
            for doc in item.attached_documents:
                if doc.code == "6610":
                    doc.document_date = date
    return ControleFDI(source=source, date=date, date_rfcv=date_rfcv, numero_rfcv=numero_rfcv,
                       numero_fdi=info.numero if info else None)
