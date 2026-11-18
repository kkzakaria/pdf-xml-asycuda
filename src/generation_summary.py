"""
Résumé structuré d'une génération : totaux, valeurs par article, cases clés du corps,
écarts par rapport au RFCV et alertes (affichés avant téléchargement).

Unités : FOB et fret en devise du RFCV (Summary.devise, comme la saisie et la case 22),
assurance et CIF en XOF ; de même pour les valeurs par article (valeurs_articles).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Optional

from designation import suggest_designation
from models import RFCVData

if TYPE_CHECKING:  # pragma: no cover
    from corps_generator import CorpsResult
    from generation import GenerationSettings

GENERAL_CASES = ("Fcx_Aa", "Fcx_29a", "Fcx_10", "Fcx_18b", "Fcx_28b")
ITEM_CASES = ("Fcx_31f", "Fld_40")
FOB_MODES = {"prorata": "au prorata des FOB du RFCV", "uniforme": "uniformément"}


@dataclass
class Alert:
    code: str          # "chassis_declares", "chassis_autre_brouillon", "colis_zero", "somme_articles",
                       # "fob_heterogene", "designation", "code_sh_inhabituel"
    message: str       # français, prêt à afficher
    bloquante: bool    # vrai seulement pour "chassis_declares" et "somme_articles"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        return cls(code=d["code"], message=d["message"], bloquante=bool(d["bloquante"]))


@dataclass
class Summary:
    """
    Résumé d'une génération. Unités :
    - fob_total, fret_total : devise du RFCV (``devise``, ex. USD) ;
    - assurance_total, cif_total : XOF ;
    - valeurs_articles : "fob" et "fret" en devise du RFCV, "assurance" et "cif" en XOF,
      chaque liste = [(valeur, nombre d'articles)], par nombre décroissant puis valeur ;
    - colis : nombre (case 6) ; poids_brut, poids_net : kg.
    Tous les champs ont une valeur par défaut : from_dict lit un résumé stocké avant
    l'ajout d'un champ.
    """
    rfcv_number: Optional[str] = None
    nb_articles: int = 0
    nb_vin: int = 0
    fob_total: float = 0.0
    fret_total: float = 0.0
    assurance_total: float = 0.0
    cif_total: float = 0.0
    colis: int = 0
    poids_brut: float = 0.0
    poids_net: float = 0.0
    valeurs_articles: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    cases: dict[str, str] = field(default_factory=dict)
    ecarts: list[str] = field(default_factory=list)
    alertes: list[Alert] = field(default_factory=list)
    vins: list[str] = field(default_factory=list)
    designation: Optional[str] = None
    codes_sh: list[str] = field(default_factory=list)
    devise: Optional[str] = None       # code devise du RFCV (FOB et fret)

    @property
    def bloquante(self) -> bool:
        return any(a.bloquante for a in self.alertes)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["valeurs_articles"] = {k: [[v, n] for v, n in vals] for k, vals in self.valeurs_articles.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Summary":
        """Ignore les clés inconnues ; une clé absente prend sa valeur par défaut."""
        d = {k: v for k, v in d.items() if k in {f.name for f in fields(cls)}}
        if "valeurs_articles" in d:
            d["valeurs_articles"] = {k: [(float(v), int(n)) for v, n in vals]
                                     for k, vals in (d["valeurs_articles"] or {}).items()}
        if "alertes" in d:
            d["alertes"] = [Alert.from_dict(a) for a in (d["alertes"] or [])]
        return cls(**d)


# ------------------------------------------------------------------ lecture des données
def _amount(ca, attr="amount_foreign") -> float:
    return float(getattr(ca, attr) or 0) if ca is not None else 0.0


def _fob_total(d: RFCVData) -> float:
    return _amount(d.valuation.invoice if d.valuation else None)


def _fret_total(d: RFCVData) -> float:
    return _amount(d.valuation.external_freight if d.valuation else None)


def _assurance_total(d: RFCVData) -> float:
    return _amount(d.valuation.insurance if d.valuation else None, "amount_national")


def _item_prices(d: RFCVData) -> list[float]:
    return [float(i.tarification.item_price or 0) if i.tarification else 0.0 for i in d.items]


def _item_packages(d: RFCVData) -> list[float]:
    return [float(i.packages.number_of_packages or 0) if i.packages else 0.0 for i in d.items]


def _item_designation(it) -> Optional[str]:
    return (it.packages.marks1 if it.packages and it.packages.marks1 else None) or it.goods_description


def _designation(d: RFCVData) -> Optional[str]:
    """Désignation du 1er article (marques case 31, sinon description)."""
    return _item_designation(d.items[0]) if d.items else None


def _hs(it) -> Optional[str]:
    return it.tarification.hscode.commodity_code if it.tarification and it.tarification.hscode else None


def _vin(it) -> Optional[str]:
    p = it.packages
    if p is None:
        return None
    if p.chassis_number:
        return p.chassis_number
    if p.marks2 and p.marks2.upper().startswith("CH:"):
        return p.marks2[3:].strip() or None
    return None


def _distinct(values) -> list[tuple[float, int]]:
    counts = Counter(round(float(v), 2) for v in values)
    return sorted(counts.items(), key=lambda vn: (-vn[1], vn[0]))


def _valeurs_articles(d: RFCVData) -> dict[str, list[tuple[float, int]]]:
    vis = [i.valuation_item for i in d.items]
    return {
        "fob": _distinct(_item_prices(d)),
        "fret": _distinct(_amount(v.external_freight if v else None) for v in vis),
        "assurance": _distinct(_amount(v.insurance if v else None, "amount_national") for v in vis),
        "cif": _distinct(float(v.total_cif or 0) if v else 0.0 for v in vis),
    }


def _cases(corps: "CorpsResult") -> dict[str, str]:
    values = {}
    for line in corps.content.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    cases = {k: values.get(k, "") for k in GENERAL_CASES}
    cases.update({k: values.get(f"ITEM.1.{k}", "") for k in ITEM_CASES})
    return cases


def fmt_montant(x: float) -> str:
    """12930135 -> '12 930 135' ; 12683.65 -> '12 683,65'."""
    x = round(float(x), 2)
    if x == int(x):
        return f"{int(x):,}".replace(",", " ")
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def _all_equal(values) -> bool:
    return len({round(v, 2) for v in values}) <= 1


# ------------------------------------------------------------------ écarts et alertes
def _fob_mode(rfcv_data: RFCVData, settings: Optional["GenerationSettings"]) -> str:
    if settings is not None:
        return settings.fob_mode
    return "uniforme" if _all_equal(_item_prices(rfcv_data)) else "prorata"


def _ecarts(d: RFCVData, ref: RFCVData, settings: Optional["GenerationSettings"]) -> list[str]:
    devise = (d.financial.currency_code if d.financial else None) or ""
    suffixe = f" {devise}" if devise else ""
    out = []
    old, new = _fob_total(ref), _fob_total(d)
    if round(old, 2) != round(new, 2):
        out.append(f"FOB révisé : {fmt_montant(old)} → {fmt_montant(new)}{suffixe}, réparti "
                   f"{FOB_MODES.get(_fob_mode(d, settings), _fob_mode(d, settings))}")
    old, new = _fret_total(ref), _fret_total(d)
    if round(old, 2) != round(new, 2):
        out.append(f"Fret imposé : {fmt_montant(old)} → {fmt_montant(new)}{suffixe}")
    old, new = _assurance_total(ref), _assurance_total(d)
    if round(old, 2) != round(new, 2):
        mode = settings.assurance_mode if settings is not None else None
        libelle = {"imposee": "Assurance imposée", "rfcv": "Assurance attestée (case 21)",
                   "formule": "Assurance recalculée (formule)"}.get(mode, "Assurance")
        out.append(f"{libelle} : {fmt_montant(old)} → {fmt_montant(new)} XOF")
    old, new = _designation(ref), _designation(d)
    if old != new:
        out.append(f"Désignation : {old or '(vide)'} → {new or '(vide)'}")
    return out


def _alertes(d: RFCVData, ref: RFCVData, vins: list[str], conflicts: list[dict],
             other_drafts: dict[str, set[str]], known_hs, settings) -> list[Alert]:
    alertes = []
    if conflicts:
        origines = sorted({c.get("first_rfcv_number") or c.get("first_filename") or "?" for c in conflicts})
        alertes.append(Alert("chassis_declares",
                             f"{len(conflicts)} châssis déjà déclaré(s), RFCV d'origine : {', '.join(origines)}",
                             True))

    vin_set = set(vins)
    communs, dossiers = set(), []
    for libelle, autres in (other_drafts or {}).items():
        inter = vin_set & set(autres or ())
        if inter:
            communs |= inter
            dossiers.append(libelle)
    if communs:
        alertes.append(Alert("chassis_autre_brouillon",
                             f"{len(communs)} châssis présent(s) dans un autre brouillon : "
                             f"{', '.join(sorted(dossiers))}", False))

    total_colis = d.property.total_packages if d.property else None
    colis = _item_packages(d)
    if not total_colis or not any(colis):
        alertes.append(Alert("colis_zero", "Nombre de colis à 0 (case 6 ou articles) : à vérifier", False))

    erreurs = []
    somme_fob, fob = sum(_item_prices(d)), _fob_total(d)
    if round(somme_fob, 2) != round(fob, 2):
        erreurs.append(f"FOB des articles {fmt_montant(somme_fob)} ≠ FOB total {fmt_montant(fob)}")
    if round(sum(colis), 2) != round(float(total_colis or 0), 2):
        erreurs.append(f"colis des articles {fmt_montant(sum(colis))} ≠ total {fmt_montant(total_colis or 0)}")
    if erreurs:
        alertes.append(Alert("somme_articles", "Somme des articles ≠ total : " + " ; ".join(erreurs), True))

    revision = (settings.fob_revise is not None) if settings is not None \
        else round(_fob_total(ref), 2) != round(_fob_total(d), 2)
    if revision and not _all_equal(_item_prices(ref)):
        mode = _fob_mode(d, settings)
        alertes.append(Alert("fob_heterogene",
                             f"FOB attestés différents entre articles ; FOB révisé réparti "
                             f"{FOB_MODES.get(mode, mode)}", False))

    brute = _designation(d)
    proposee = suggest_designation(brute)
    if proposee is not None:
        alertes.append(Alert("designation",
                             f"Désignation non nettoyée : « {brute} » (proposée : {proposee})", False))

    if known_hs:
        vus = set()
        for it in d.items:
            paire = (_item_designation(it), _hs(it))
            if paire in vus or paire in known_hs:
                continue
            vus.add(paire)
            alertes.append(Alert("code_sh_inhabituel",
                                 f"Code SH {paire[1]} jamais déclaré pour « {paire[0]} »", False))
    return alertes


def summarize(rfcv_data: RFCVData, rfcv_reference: RFCVData, corps: "CorpsResult",
              conflicts: list[dict], other_drafts: dict[str, set[str]],
              known_hs: set[tuple[str, str]] | None,
              settings: Optional["GenerationSettings"] = None) -> Summary:
    """
    Résumé d'une génération. rfcv_reference = le même RFCV parsé sans réglage (écarts).
    known_hs None ou vide : pas d'alerte de code SH. settings (facultatif) précise le mode
    de répartition du FOB et la source de l'assurance ; sinon ils sont déduits des données.
    """
    d = rfcv_data
    vins = [v for v in (_vin(it) for it in d.items) if v]
    val = d.valuation
    codes_sh = sorted({c for c in (_hs(it) for it in d.items) if c})
    return Summary(
        rfcv_number=d.identification.rfcv_number if d.identification else None,
        nb_articles=len(d.items),
        nb_vin=len(vins),
        fob_total=_fob_total(d),
        fret_total=_fret_total(d),
        assurance_total=_assurance_total(d),
        cif_total=float(val.total_cif or 0) if val else 0.0,
        colis=int(d.property.total_packages or 0) if d.property else 0,
        poids_brut=float(val.gross_weight or 0) if val else 0.0,
        poids_net=float(val.net_weight or 0) if val else 0.0,
        valeurs_articles=_valeurs_articles(d),
        cases=_cases(corps),
        ecarts=_ecarts(d, rfcv_reference, settings),
        alertes=_alertes(d, rfcv_reference, vins, conflicts, other_drafts, known_hs, settings),
        vins=vins,
        designation=_designation(d),
        codes_sh=codes_sh,
        devise=(d.financial.currency_code if d.financial else None) or None,
    )
