"""
Lecture du format RFCV « 2026 » (texte pdfplumber des RFCV générés actuels).

Différences avec le format historique géré par RFCVParser :
  - nombres au format anglo-saxon : 1,234.56 (virgule = milliers, point = décimales)
  - libellés courts : « 19. Total FOB », « 20. Fret », « 21. Assurance », « 23. Total Customs »
  - code SH sans points : 8711209900
  - article sur trois lignes : désignation / ligne de données / suite de la désignation (VIN)

Fonctions pures sur le texte : pas de dépendance à pdfplumber ni aux dataclasses.
"""
import re

NUM = r"([\d,]+\.\d{2})"

# Pays de provenance (case 9) -> code ISO
COUNTRY_CODES = {
    "Togo": "TG", "Chine": "CN", "China": "CN", "Emirats Arabes Unis": "AE",
    "United Arab Emirates": "AE", "Ghana": "GH", "Benin": "BJ", "Bénin": "BJ",
    "Nigeria": "NG", "Burkina Faso": "BF", "Mali": "ML", "Guinée": "GN",
    "Senegal": "SN", "Sénégal": "SN", "Inde": "IN", "India": "IN", "France": "FR",
    "Allemagne": "DE", "Germany": "DE", "Italie": "IT", "Espagne": "ES",
    "Turquie": "TR", "Turkey": "TR", "Japon": "JP", "Japan": "JP",
}

# Mode de transport (libellé RFCV) -> code ASYCUDA (case 25)
TRANSPORT_MODES = {"maritime": "1", "ferroviaire": "2", "route": "3", "routier": "3",
                   "aérien": "4", "aerien": "4"}

# UN/LOCODE -> nom (Place_of_loading/Name) pour les lieux rencontrés
LOCODE_NAMES = {"TGLFW": "LOME", "CNNSA": "NANSHA", "CNSHA": "SHANGHAI", "CNNGB": "NINGBO",
                "CNSZX": "SHENZHEN", "CNTAO": "QINGDAO", "CNTXG": "TIANJIN", "CIABJ": "ABIDJAN",
                "GHTEM": "TEMA", "BJCOO": "COTONOU", "AEJEA": "JEBEL ALI"}

PACKAGE_KINDS = {"colis": "COLIS", "carton": "CARTONS", "cartons": "CARTONS",
                 "palette": "PALETTES", "palettes": "PALETTES", "pieces": "PIECES",
                 "pièces": "PIECES"}

# Ligne de données d'un article :
#   "1 1.0 UNITE TG N 1 8711209900 44,040.21"            (valeur taxable vide)
#   "1 1.0 UNITE TG N 1 8711209900 44,040.21 44,040.21"
#   "1 1.0 UNITE CN N MOTORCYCLE 1 8711209100 362.39"    (désignation sur la ligne)
ITEM_DATA = re.compile(
    r"^(?P<n>\d+) (?P<qty>[\d,]+\.\d+) (?P<unit>[A-Z]+) (?P<origin>[A-Z]{2}) (?P<used>[A-Z]) "
    r"(?:(?P<desc>.+?) )?(?P<state>\d+) (?P<hs>\d{8,10}) (?P<fob>[\d,]+\.\d{2})(?: (?P<taxable>[\d,]+\.\d{2}))?$")


# Lignes de mise en page à ignorer autour des articles (en-têtes, pieds de page, totaux)
NOISE_PREFIXES = ("Sous -total", "TOTAL GENERAL", "RFCV", "Page ", "Ce document", "obligations",
                  "obligation", "Douanières", "27. Remarques")


def is_format_2026(text: str) -> bool:
    """Vrai si le texte est celui d'un RFCV au format actuel."""
    return bool(re.search(r"19\.\s*Total FOB\s+20\.\s*Fret", text)) and "26. Articles" in text


def to_number(value: str | None) -> float | None:
    if value is None:
        return None
    return float(value.replace(",", "").strip())


def _find(pattern: str, text: str, group: int = 1, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(group).strip() if m else None


def parse_header(text: str) -> dict:
    """Cases 1 à 24 du RFCV. Les champs introuvables valent None."""
    h: dict = {}
    h["rfcv_number"] = _find(r"(RCS[A-Z]?\d+) \d{2}/\d{2}/\d{4}", text)
    h["rfcv_date"] = _find(r"RCS[A-Z]?\d+ (\d{2}/\d{2}/\d{4})", text)
    h["delivery_type"] = _find(r"RCS[A-Z]?\d+ \d{2}/\d{2}/\d{4} (TOT|PART)", text)
    h["fdi_number"] = _find(r"7\. No FDI/DAI.*\n.*\n(\S+) \d{2}/\d{2}/\d{4}", text)
    h["fdi_date"] = _find(r"7\. No FDI/DAI.*\n.*\n\S+ (\d{2}/\d{2}/\d{4})", text)

    h["importer_code"] = _find(r"Code:\s*(\S+)", text)
    h["importer_name"] = _find(r"7\. No FDI/DAI.*\n([^\n]+)", text)
    h["importer_address"] = _find(r"9\. Pays de provenance.*\n([^\n]+)", text)

    country = _find(r"9\. Pays de provenance.*\n.*\n(\S[^\n]*?)\s+Paiement", text)
    h["country_name"] = country
    h["country_code"] = COUNTRY_CODES.get(country) if country else None
    h["payment_mode"] = _find(r"\n\S[^\n]*? (Paiement [^\n]+)", text)

    h["net_weight"] = to_number(_find(r"11\. Poids Total Net.*\n" + NUM, text))
    h["gross_weight"] = to_number(_find(r"11\. Poids Total Net.*\n[\d,.]+ " + NUM, text))

    exp = re.search(r"2\. Nom et Adresse de l'Exportateur.*\n.*\n(.+?) 13\. No Facture.*\n.*\n"
                    r"(.+?) 16\. Code devise.*\n(\S[^\n]*?) [A-Z]{3} [\d.,]+ [\d,]+\.\d{2}", text)
    h["exporter_name"] = exp.group(1).strip() if exp else None
    h["exporter_address"] = f"{exp.group(2).strip().rstrip(',')}, {exp.group(3).strip()}" if exp else None

    h["invoice_number"] = _find(r"13\. No Facture.*\n(\S+) \d{2}/\d{2}/\d{4}", text)
    h["invoice_date"] = _find(r"13\. No Facture.*\n\S+ (\d{2}/\d{2}/\d{4})", text)
    h["incoterm"] = _find(r"13\. No Facture.*\n\S+ \d{2}/\d{2}/\d{4} ([A-Z]{3})", text)

    cur = re.search(r"\s([A-Z]{3}) ([\d.,]+) ([\d,]+\.\d{2})\n3\. D", text)
    h["currency_code"] = cur.group(1) if cur else None
    h["exchange_rate"] = to_number(cur.group(2)) if cur else None
    h["invoice_total"] = to_number(cur.group(3)) if cur else None

    h["fob"] = to_number(_find(r"19\. Total FOB 20\. Fret\n" + NUM, text))
    h["freight"] = to_number(_find(r"19\. Total FOB 20\. Fret\n[\d,.]+ " + NUM, text))
    tot = re.search(r"23\. Total Customs\n.*?" + NUM + " " + NUM + " " + NUM + r"\n", text)
    h["insurance"] = to_number(tot.group(1)) if tot else None
    h["charges"] = to_number(tot.group(2)) if tot else None
    h["total_customs"] = to_number(tot.group(3)) if tot else None

    h["bill_of_lading"] = _find(r"No\. \(LTA/Connaissement/CMR\).*\n(\S+)", text)
    mode = _find(r"Mode de transport :\n\S+\s+(Transport [^\n]*?)\s+21\.", text)
    h["transport_mode"] = mode
    h["transport_mode_code"] = next((c for k, c in TRANSPORT_MODES.items() if mode and k in mode.lower()), None)
    h["voyage_number"] = _find(r"No\. \(Vol/Voyage/Transport.*\n(.+?) 24\. Colisage", text)
    h["bl_date"] = _find(r"Date de Transporteur ID :.*\n(\d{2}/\d{2}/\d{4})", text)
    h["carrier"] = _find(r"Date de Transporteur ID :.*\n\d{2}/\d{2}/\d{4} ([^\n]+)", text)
    lcl = _find(r"No\. de LCL (\d+)", text)
    fcl = _find(r"No\. de FCL (\d+)", text)
    h["lcl_count"] = int(lcl) if lcl else None
    h["fcl_count"] = int(fcl) if fcl else None
    h["loading_place"] = _find(r"Lieu de chargement : ([A-Z]{5})", text)
    h["loading_place_name"] = LOCODE_NAMES.get(h["loading_place"]) if h["loading_place"] else None
    h["discharge_place"] = _find(r"Lieu de déchargement :\s*\n?([A-Z]{5})", text)

    colis = re.search(r"(\d+) - ([A-Za-zéè]+)", text)
    h["total_packages"] = int(colis.group(1)) if colis else None
    h["package_type"] = PACKAGE_KINDS.get(colis.group(2).lower(), colis.group(2).upper()) if colis else None
    h["commercial_description"] = _find(r"Lieu de chargement : [A-Z]{5} ([^\n]+)", text)
    return h


def short_designation(description: str) -> str:
    """
    Désignation courte des déclarations de production : texte avant le premier tiret.
    « MOTORCYCLE-FENGHAO - LRFX... » -> « MOTORCYCLE » ; « MOTO - HAOJUE - LC6... » -> « MOTO ».
    """
    head = re.split(r"\s*-", description or "", maxsplit=1)[0].strip()
    return head or (description or "").strip()


def parse_items(text: str) -> tuple[list[dict], dict[int, float], list[str]]:
    """
    Articles de la section 26.

    Returns:
        (articles, sous_totaux_par_page, anomalies)
        article = {n, qty, unit, origin, state, hs, fob, taxable, description}
    """
    items: list[dict] = []
    subtotals: dict[int, float] = {}
    problems: list[str] = []

    section = text.split("26. Articles", 1)[1] if "26. Articles" in text else ""
    lines = section.split("\n")
    for m in re.finditer(r"Sous -total P(\d+) ([\d,]+\.\d{2})", section):
        subtotals[int(m.group(1))] = to_number(m.group(2))

    def is_noise(line: str) -> bool:
        s = line.strip()
        return (not s or ITEM_DATA.match(s) is not None or s.startswith(NOISE_PREFIXES)
                or re.fullmatch(r"[A-Z](?: [A-Z]){0,11}", s) is not None or "Description des marchandises" in s)

    for i, line in enumerate(lines):
        m = ITEM_DATA.match(line.strip())
        if not m:
            continue
        before = lines[i - 1].strip() if i > 0 and not is_noise(lines[i - 1]) else ""
        after = lines[i + 1].strip() if i + 1 < len(lines) and not is_noise(lines[i + 1]) else ""
        description = " ".join(p for p in (before, (m["desc"] or "").strip(), after) if p)
        items.append({
            "n": int(m["n"]), "qty": to_number(m["qty"]), "unit": m["unit"], "origin": m["origin"],
            "state": m["state"], "hs": m["hs"], "fob": to_number(m["fob"]),
            "taxable": to_number(m["taxable"]), "description": description,
        })

    expected = list(range(1, len(items) + 1))
    if [it["n"] for it in items] != expected:
        problems.append("numérotation des articles non continue")
    return items, subtotals, problems
