#!/usr/bin/env python3
"""
Générateur du corps SYDAM : XML ASYCUDA -> corps.txt (fichier d'écriture de l'agent SYDAM).

Repris de sydam-api (tools/xml_to_corps.py). Lit un XML ASYCUDA (produit par ce projet ou
exporté du client) et génère le fichier `corps.txt` que l'agent injecte dans la déclaration :

  - champs du segment général :  NomChamp=valeur          (ex. Fld_9a=2502282K)
  - champs d'article           :  ITEM.<n>.NomChamp=valeur (ex. ITEM.3.Fld_42=363.0)

Ne produit PAS les champs remplis automatiquement par ASYCUDA depuis un code
(nom de bureau, de banque, de déclarant, libellé de colis), ni les champs calculés
à la liquidation (lignes de taxes, cautions).

Usage :
    python converter.py RFCV.pdf --corps                     (XML + corps_<nom>.txt)
    python src/corps_generator.py DECLARATION.xml -o corps.txt
    python src/corps_generator.py DECLARATION.xml --profil profil-corps.ini

Le --profil de ce module est un fichier de constantes du corps (clés Fld_*/Fcx_*, ex.
Fld_30=AIRE), utilisées seulement quand le XML ne porte pas la valeur. Ce n'est pas le
profil société de converter.py (profils/*.ini).
"""
import argparse
import re
import sys
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path

# Parseur XML : defusedxml si disponible (protège des attaques XXE et
# "billion laughs"), sinon repli sur la bibliothèque standard.
try:
    from defusedxml import ElementTree as ET
    _SAFE_XML = True
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET
    _SAFE_XML = False

# --------------------------------------------------------------------------- #
# Correspondance champ DAU -> chemin XML (segment général)
# Chemins relatifs à la racine <ASYCUDA>. Voir docs/correspondance-xml-dau.md
# --------------------------------------------------------------------------- #
GENERAL = {
    "Fcx_Aa":  "Identification/Office_segment/Customs_clearance_office_code",
    "Fld_Ah":  "Identification/Manifest_reference_number",
    "Fld_7b":  "Declarant/Reference/Number",
    "Fld_9a":  "Traders/Consignee/Consignee_code",
    "Ftx_9b":  "Traders/Consignee/Consignee_name",
    "Fld_6":   "Property/Nbers/Total_number_of_packages",   # case 6 : total colis = Σ colis/article
    "Fcx_10":  "General_information/Country/Country_first_destination",
    "Fld_12":  "General_information/Value_details",
    "Fcx_15a": "General_information/Country/Export/Export_country_name",
    "Fcx_15b": "General_information/Country/Export/Export_country_code",
    "Fld_16":  "General_information/Country/Country_of_origin_name",
    "Fld_18a": "Transport/Means_of_transport/Departure_arrival_information/Identity",
    "Fcx_18b": "Transport/Means_of_transport/Departure_arrival_information/Nationality",
    "Fld_21a": "Transport/Means_of_transport/Border_information/Identity",
    # Case 22 : devise + montant total facture (note generale = Valuation/Gs_Invoice).
    # Doit correspondre a la somme des factures par article (verifie : 12705 USD = somme).
    "Fcx_22a": "Valuation/Gs_Invoice/Currency_code",
    "Fld_22b": "Valuation/Gs_Invoice/Amount_foreign_currency",
    "Fld_23":  "Valuation/Gs_Invoice/Currency_rate",
    "Fld_24a": "Financial/Financial_transaction/code1",
    "Fld_24b": "Financial/Financial_transaction/code2",
    "Fcx_25":  "Transport/Means_of_transport/Border_information/Mode",
    "Fld_27a": "Transport/Place_of_loading/Code",
    "Fld_27b": "Transport/Place_of_loading/Name",
    "Fcx_28b": "Financial/Bank/Code",
    "Fcx_29a": "Transport/Border_office/Code",
    "Fld_30":  "Transport/Location_of_goods",
    "Fld_48":  "Financial/Deffered_payment_reference",
}

# Champs d'article : chemin relatif à <Item>
ITEM = {
    "Ftx_31b1": "Packages/Marks1_of_packages",
    "Ftx_31b2": "Packages/Marks2_of_packages",   # châssis
    "Ftx_44m":  "Free_text_1",                   # châssis (2e emplacement)
    "Fld_31e":  "Packages/Number_of_packages",
    "Fcx_31f":  "Packages/Kind_of_packages_code",
    "Fld_33a":  "Tarification/HScode/Commodity_code",
    "Fld_33b":  "Tarification/HScode/Precision_1",
    # Case 41 (D.D.U) : quantite d'unite supplementaire = SUP.at(1)/QTY (obligatoire, Verifier).
    # Valeur = XML Supplementary_unit[1]/quantity (= 1.0 partout, unite QA "apurement").
    # (essai a 13/nb colis abandonne : le XML et la saisie d'origine donnent 1.0)
    "Fld_41b":  "Tarification/Supplementary_unit[1]/Suppplementary_unit_quantity",
    "Fcx_37a":  "Tarification/Extended_customs_procedure",
    "Fcx_37b":  "Tarification/National_customs_procedure",
    "Fld_42":   "Tarification/Item_price",
    "Fld_43":   "Tarification/Valuation_method_code",
    "Fld_44g":  "Tarification/Value_item",
    "Fld_35":   "Valuation_item/Weight_itm/Gross_weight_itm",
    "Fld_38":   "Valuation_item/Weight_itm/Net_weight_itm",
    "Fld_46":   "Valuation_item/Statistical_value",
    "Fld_40":   "Previous_doc/Summary_declaration",

    # --- Note de valeur par article (onglet "Note de val.", champs Vit_*) ---
    # FOB (facture) -> VIT/INV, fret externe -> EFR, fret interne -> IFR, assurance -> INS.
    # 4 composantes chacun : montant devise (FCX), montant national (NMU), code devise (COD),
    # taux (RAT). Chemins de donnees confirmes par decompilation de VP_ValItm.
    "Fld_Vit_Inv_Amt_Fcx": "Valuation_item/Item_Invoice/Amount_foreign_currency",
    "Fld_Vit_Inv_Amt_Nmu": "Valuation_item/Item_Invoice/Amount_national_currency",
    "Fcx_Vit_Inv_Cur_Cod": "Valuation_item/Item_Invoice/Currency_code",
    "Fld_Vit_Inv_Cur_Rat": "Valuation_item/Item_Invoice/Currency_rate",
    "Fld_Vit_Efr_Amt_Fcx": "Valuation_item/item_external_freight/Amount_foreign_currency",
    "Fld_Vit_Efr_Amt_Nmu": "Valuation_item/item_external_freight/Amount_national_currency",
    "Fcx_Vit_Efr_Cur_Cod": "Valuation_item/item_external_freight/Currency_code",
    "Fld_Vit_Efr_Cur_Rat": "Valuation_item/item_external_freight/Currency_rate",
    "Fld_Vit_Ifr_Amt_Fcx": "Valuation_item/item_internal_freight/Amount_foreign_currency",
    "Fld_Vit_Ifr_Amt_Nmu": "Valuation_item/item_internal_freight/Amount_national_currency",
    "Fcx_Vit_Ifr_Cur_Cod": "Valuation_item/item_internal_freight/Currency_code",
    "Fld_Vit_Ifr_Cur_Rat": "Valuation_item/item_internal_freight/Currency_rate",
    "Fld_Vit_Ins_Amt_Fcx": "Valuation_item/item_insurance/Amount_foreign_currency",
    "Fld_Vit_Ins_Amt_Nmu": "Valuation_item/item_insurance/Amount_national_currency",
    "Fcx_Vit_Ins_Cur_Cod": "Valuation_item/item_insurance/Currency_code",
    "Fld_Vit_Ins_Cur_Rat": "Valuation_item/item_insurance/Currency_rate",
    # Quantite d'unite supplementaire (obligatoire, reclamee par Verifier). Les CODES sont
    # auto-remplis depuis le tarif (champs desactives) : on n'ecrit que les quantites.
    # Su1 <- SUP.at(2) <-> Supplementary_unit[2] ; Su2 <- SUP.at(3) <-> Supplementary_unit[3].
    "Fld_Vit_Su1_Qty": "Tarification/Supplementary_unit[2]/Suppplementary_unit_quantity",
    "Fld_Vit_Su2_Qty": "Tarification/Supplementary_unit[3]/Suppplementary_unit_quantity",
}

# Champs qui doivent porter un châssis au format CH:<VIN> (sans espace)
CHASSIS_FIELDS = ("Ftx_31b2", "Ftx_44m")

# Constantes par société / bureau, utilisées quand le XML ne les porte pas.
# Surchargeables par --profil (fichier clé=valeur).
DEFAULT_PROFILE = {
    "Fld_30":  "AIRE",     # emplacement des marchandises
    "Fcx_29a": "CIAB1",    # bureau d'entrée
    "Fld_24a": "0",        # nature de la transaction
    "Fld_24b": "1",
    "Fcx_25":  "1",        # mode de transport (mer)
}


def text_at(node, path):
    """Texte d'un chemin relatif, ou None si absent/vide/<null/>."""
    if node is None:
        return None
    el = node.find(path)
    if el is None:
        return None
    if len(el) and el.find("null") is not None:
        return None
    txt = (el.text or "").strip()
    return txt or None


def normalize_chassis(value):
    """'CH: LRFX...' ou 'LRFX...' -> 'CH:LRFX...' (sans espace)."""
    if not value:
        return value
    v = value.strip()
    if v.upper().startswith("CH:"):
        v = v[3:].strip()
    return "CH:" + v


# Commentaire en fin de ligne : « valeur   # commentaire » (un blanc avant le #)
_INLINE_COMMENT = re.compile(r"\s+#.*$")

# Champs dont seule la première ligne a un sens dans le corps : le XML ASYCUDA natif
# met « nom\nadresse » dans Consignee_name, le corps de référence ne porte que le nom.
FIRST_LINE_FIELDS = ("Ftx_9b",)


def load_corps_profile(path=None):
    prof = dict(DEFAULT_PROFILE)
    if not path:
        return prof
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = _INLINE_COMMENT.sub("", line).strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        prof[k.strip()] = v.strip()
    return prof


def single_line(field, value, flattened):
    """
    Une valeur du corps tient sur une ligne (format clé=valeur) : un saut de ligne
    créerait une ligne orpheline. Première ligne pour FIRST_LINE_FIELDS, sinon lignes
    jointes par un espace (champ signalé dans le récapitulatif).
    """
    if "\n" not in value and "\r" not in value:
        return value
    lines = [part.strip() for part in value.splitlines() if part.strip()]
    if field.rsplit(".", 1)[-1] in FIRST_LINE_FIELDS:
        return lines[0] if lines else ""
    flattened.append(field)
    return " ".join(lines)


def build(xml_source, profile=None):
    """xml_source : chemin du XML, ou élément racine <ASYCUDA> déjà lu."""
    profile = DEFAULT_PROFILE if profile is None else profile
    root = ET.parse(xml_source).getroot() if isinstance(xml_source, (str, Path)) else xml_source
    out = []          # (clé, valeur)
    missing = []      # champs attendus non trouvés
    flattened = []    # champs multi-lignes ramenés sur une ligne

    # --- segment général ---
    for field, path in GENERAL.items():
        val = text_at(root, path)
        if val is None:
            val = profile.get(field)          # repli sur le profil société
            if val is None:
                missing.append(field)
                continue
        out.append((field, single_line(field, val, flattened)))

    # --- articles ---
    items = root.findall("Item")
    for idx, item in enumerate(items, start=1):
        for field, path in ITEM.items():
            val = text_at(item, path)
            if val is None:
                continue
            if field in CHASSIS_FIELDS:
                val = normalize_chassis(val)
            key = f"ITEM.{idx}.{field}"
            out.append((key, single_line(key, val, flattened)))

    return out, missing, len(items), flattened


def render(pairs, xml_name, n_items):
    lines = [
        "# corps.txt — généré depuis " + xml_name,
        "# À placer sur le poste dans : C:\\sydam\\in\\corps.txt",
        "# Écriture par l'agent SYDAM : Ctrl+Shift+W",
        f"# Segment général + {n_items} article(s). Châssis au format CH:<VIN> (sans espace).",
        "",
    ]
    gen = [(k, v) for k, v in pairs if not k.startswith("ITEM.")]
    lines.append("# --- Segment général ---")
    lines += [f"{k}={v}" for k, v in gen]
    lines.append("")
    cur = None
    for k, v in pairs:
        if not k.startswith("ITEM."):
            continue
        n = k.split(".")[1]
        if n != cur:
            cur = n
            lines.append(f"# --- Article {n} ---")
        lines.append(f"{k}={v}")
    return "\n".join(lines) + "\n"


@dataclass
class CorpsResult:
    """Corps généré et récapitulatif."""
    content: str
    n_items: int
    n_general: int
    n_item_fields: int
    missing: list = dc_field(default_factory=list)     # champs généraux sans valeur (ni XML ni profil)
    flattened: list = dc_field(default_factory=list)   # valeurs multi-lignes ramenées sur une ligne

    def summary(self) -> str:
        msg = [(f"{self.n_general} champ(s) général(aux), {self.n_items} article(s), "
                f"{self.n_item_fields} champ(s) d'article.")]
        if self.missing:
            msg.append("Champs sans valeur (ni XML ni profil): " + ", ".join(self.missing))
        if self.flattened:
            msg.append("Valeurs multi-lignes ramenées sur une ligne: " + ", ".join(self.flattened[:10])
                       + (" …" if len(self.flattened) > 10 else ""))
        return "\n".join(msg)


def generate_corps(xml_source, profile=None, xml_name=None) -> CorpsResult:
    """
    Corps SYDAM d'un XML ASYCUDA.

    xml_source : chemin du XML ou élément racine ; profile : constantes du corps
    (load_corps_profile), DEFAULT_PROFILE par défaut ; xml_name : nom cité en en-tête.
    """
    pairs, missing, n_items, flattened = build(xml_source, profile)
    if xml_name is None:
        xml_name = Path(xml_source).name if isinstance(xml_source, (str, Path)) else "XML ASYCUDA"
    n_general = sum(1 for k, _ in pairs if not k.startswith("ITEM."))
    return CorpsResult(content=render(pairs, xml_name, n_items), n_items=n_items, n_general=n_general,
                       n_item_fields=len(pairs) - n_general, missing=missing, flattened=flattened)


def corps_path_for(xml_path) -> Path:
    """Chemin du corps à côté du XML : <dossier>/corps_<nom du XML>.txt."""
    xml_path = Path(xml_path)
    return xml_path.with_name(f"corps_{xml_path.stem}.txt")


def write_corps(xml_path, output_path=None, profile=None) -> tuple[Path, CorpsResult]:
    """Écrit le corps d'un XML (par défaut corps_<nom>.txt à côté du XML)."""
    result = generate_corps(xml_path, profile)
    output = Path(output_path) if output_path else corps_path_for(xml_path)
    output.write_text(result.content, encoding="utf-8")
    return output, result


def main():
    ap = argparse.ArgumentParser(description="XML ASYCUDA -> corps.txt (agent SYDAM)")
    ap.add_argument("xml", help="Fichier XML ASYCUDA")
    ap.add_argument("-o", "--output", default=None, help="Fichier de sortie (défaut: stdout)")
    ap.add_argument("--profil", default=None, help="Fichier de constantes société (clé=valeur)")
    ap.add_argument("--quiet", action="store_true", help="Ne pas afficher le récapitulatif")
    args = ap.parse_args()

    if not Path(args.xml).is_file():
        print(f"Erreur: fichier introuvable: {args.xml}", file=sys.stderr)
        return 1
    if not _SAFE_XML and not args.quiet:
        print("Note: module 'defusedxml' absent, parseur standard utilisé. "
              "Pour un XML d'origine non maîtrisée: pip install defusedxml",
              file=sys.stderr)

    profile = load_corps_profile(args.profil)
    result = generate_corps(args.xml, profile)

    if args.output:
        Path(args.output).write_text(result.content, encoding="utf-8")
    else:
        sys.stdout.write(result.content)

    if not args.quiet:
        print(result.summary(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
