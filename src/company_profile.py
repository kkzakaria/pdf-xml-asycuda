"""
Profil société / bureau : constantes de déclaration absentes du RFCV.

Le RFCV ne porte ni le bureau de dédouanement, ni le déclarant, ni la banque, ni le
compte, ni l'emplacement des marchandises. Ces valeurs dépendent de la société qui
déclare : elles viennent d'un fichier profil (clé=valeur), et les données propres au
dossier (n° de dossier, manifeste, nationalité du moyen de transport) de paramètres.

Format du fichier (UTF-8) :
    # commentaire
    bureau_code=CIAB6
    declarant_nom=KARTA Transit      # commentaire en fin de ligne
Une valeur vide est ignorée. « \\n » dans une valeur insère un saut de ligne.
"""
from dataclasses import dataclass, fields
from pathlib import Path

from models import Bank, RFCVData, Trader


@dataclass
class CompanyProfile:
    bureau_code: str | None = None            # Identification/Office_segment (ex. CIAB6)
    bureau_nom: str | None = None             # ex. ABJ GUICHET UNIQUE
    declarant_code: str | None = None         # Declarant/Declarant_code (ex. 00537M)
    declarant_nom: str | None = None          # Declarant/Declarant_name (1re ligne)
    declarant_adresse: str | None = None      # Declarant/Declarant_name (2e ligne)
    declarant_representant: str | None = None  # Declarant/Declarant_representative
    reference_prefixe: str | None = None      # Declarant/Reference/Number = préfixe + n° dossier
    banque_code: str | None = None            # Financial/Bank/Code (ex. BDU1)
    compte: str | None = None                 # Financial/Deffered_payment_reference (ex. 2600537M)
    emplacement: str | None = None            # Transport/Location_of_goods (ex. AIRE)


KNOWN_KEYS = {f.name for f in fields(CompanyProfile)}


def load_profile(path: str) -> CompanyProfile:
    """Lit un fichier profil. Une clé inconnue est une erreur (faute de frappe probable)."""
    values = {}
    for lineno, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{lineno} : ligne sans « = » : {raw!r}")
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in KNOWN_KEYS:
            raise ValueError(f"{path}:{lineno} : clé inconnue {key!r} (attendu : {', '.join(sorted(KNOWN_KEYS))})")
        if value:
            values[key] = value.replace("\\n", "\n")
    return CompanyProfile(**values)


def apply_profile(
    rfcv_data: RFCVData,
    profile: CompanyProfile | None = None,
    dossier: str | None = None,
    manifeste: str | None = None,
    nationalite_transport: str | None = None,
) -> RFCVData:
    """
    Complète la déclaration avec le profil société et les données du dossier.

    Le rapport de paiement passé au parser (rapport_paiement) reste prioritaire sur le
    compte du profil pour Financial/Deffered_payment_reference.
    """
    p = profile or CompanyProfile()
    ident, fin, trans = rfcv_data.identification, rfcv_data.financial, rfcv_data.transport

    if ident is not None:
        if p.bureau_code:
            ident.customs_office_code = p.bureau_code
            ident.customs_office_name = p.bureau_nom
        if manifeste:
            ident.manifest_reference = manifeste

    if p.declarant_code or p.declarant_nom or p.reference_prefixe or dossier:
        decl = rfcv_data.declarant or Trader()
        decl.code = p.declarant_code or decl.code
        decl.name = p.declarant_nom or decl.name
        decl.address = p.declarant_adresse or decl.address
        decl.representative = p.declarant_representant or decl.representative
        if dossier:
            decl.reference = f"{p.reference_prefixe or ''}{dossier}"
        rfcv_data.declarant = decl

    if fin is not None:
        if p.banque_code:
            fin.bank = fin.bank or Bank()
            fin.bank.code = p.banque_code
        if p.compte and not fin.deferred_payment_ref:
            fin.deferred_payment_ref = p.compte

    if trans is not None:
        if p.emplacement:
            trans.goods_location = p.emplacement
        if nationalite_transport:
            trans.vessel_nationality = nationalite_transport
    return rfcv_data
