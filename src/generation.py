"""
Génération « brouillon » d'un dossier : XML ASYCUDA + corps SYDAM + résumé, sans écriture
dans le registre des châssis (contrôle des doublons en lecture seule, rendu en alertes).

Même chaîne que la CLI (converter.convert_pdf_to_xml avec --corps) : RFCVParser -> profil
société -> (désignation) -> XMLGenerator -> corps. Sans réglage particulier, les fichiers
produits sont identiques octet pour octet à ceux de la CLI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

from chassis_registry import ChassisRegistry
from company_profile import CompanyProfile, apply_profile
from corps_generator import write_corps
from designation import apply_designation
from fdi import appliquer_fdi
from generation_summary import Summary, summarize
from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator

ASSURANCE_MODES = ("formule", "rfcv", "imposee")


@dataclass
class Amount:
    value: float
    per_article: bool = False          # vrai : value × nombre d'articles

    def total(self, nb_articles: int) -> float:
        return self.value * nb_articles if self.per_article else self.value


@dataclass
class GenerationSettings:
    taux_douane: float
    profile: Optional[CompanyProfile] = None
    dossier: Optional[str] = None
    manifeste: Optional[str] = None
    nationalite_transport: Optional[str] = None
    rapport_paiement: Optional[str] = None
    takikro: bool = False
    disp: bool = False
    banque: str | None = None           # case 28 : remplace banque_code du profil (DISP prioritaire)
    fob_revise: Optional[Amount] = None
    fob_mode: str = "prorata"
    fret: Optional[Amount] = None
    assurance_mode: str = "formule"     # "formule" | "rfcv" | "imposee"
    assurance: Optional[Amount] = None  # requis si "imposee"
    designation: Optional[str] = None
    fob_exact: bool = False             # case 22 au centime (défaut : arrondie à l'unité, comme Karta)
    date_fdi: Optional[str] = None      # date de validation de la FDI saisie (JJ/MM/AAAA), prioritaire
    fdi_pdf: Optional[str] = None       # PDF de la FDI : date de validation et contrôle du n° de FDI

    def to_dict(self) -> dict:
        """Dictionnaire sérialisable en JSON (stockage en base)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GenerationSettings":
        d = {k: v for k, v in d.items() if k in {f.name for f in fields(cls)}}
        if d.get("profile") is not None:
            d["profile"] = CompanyProfile(**d["profile"])
        for key in ("fob_revise", "fret", "assurance"):
            if d.get(key) is not None:
                d[key] = Amount(**d[key])
        return cls(**d)


@dataclass
class GenerationResult:
    xml_path: Path
    corps_path: Path
    summary: Summary


def _parser_options(settings: GenerationSettings, nb_articles: int) -> dict:
    """Réglages -> paramètres du parseur (montants « par article » convertis en totaux)."""
    def total(a: Optional[Amount]) -> Optional[float]:
        return a.total(nb_articles) if a is not None else None

    if settings.assurance_mode not in ASSURANCE_MODES:
        raise ValueError(f"Mode d'assurance invalide : {settings.assurance_mode!r} "
                         f"(attendu : {', '.join(ASSURANCE_MODES)})")
    if settings.assurance_mode == "imposee" and settings.assurance is None:
        raise ValueError("Assurance « imposée » sans montant : indiquer le montant de l'assurance")
    imposee = settings.assurance_mode == "imposee"
    return {
        "insurance_mode": "rfcv" if settings.assurance_mode == "rfcv" else "formule",
        "assurance_imposee": total(settings.assurance) if imposee else None,
        "fob_revise": total(settings.fob_revise),
        "fob_mode": settings.fob_mode,
        "fret_impose": total(settings.fret),
        "fob_exact": settings.fob_exact,
    }


def generate(pdf_path: Path, settings: GenerationSettings, out_dir: Path, stem: str,
             registry: ChassisRegistry, other_drafts: dict[str, set[str]] | None = None,
             known_hs: set[tuple[str, str]] | None = None) -> GenerationResult:
    """
    Génère out_dir/<stem>.xml et out_dir/corps_<stem>.txt sans écrire dans le registre.

    Le RFCV est parsé deux fois : sans réglage (référence des écarts, nombre d'articles pour
    les montants « par article »), puis avec les réglages. other_drafts = {libellé du dossier :
    VIN} des autres brouillons ; known_hs = paires (désignation, code SH) déjà déclarées.
    """
    if registry is None:
        raise ValueError("Registre des châssis requis : generate() ne doit jamais utiliser le "
                         "registre par défaut du dépôt")
    common = {"taux_douane": settings.taux_douane, "rapport_paiement": settings.rapport_paiement,
              "registry": registry, "register_chassis": False}
    # Référence au même arrondi de la case 22 : l'arrondi n'est pas un écart de réglage
    reference = RFCVParser(str(pdf_path), **common, fob_exact=settings.fob_exact).parse()
    options = _parser_options(settings, len(reference.items))

    parser = RFCVParser(str(pdf_path), **common, **options)
    rfcv_data = parser.parse()

    # Même condition que la CLI (converter.convert_pdf_to_xml)
    s = settings
    if s.profile or s.dossier or s.manifeste or s.nationalite_transport or s.takikro or s.disp or s.banque:
        apply_profile(rfcv_data, s.profile, dossier=s.dossier, manifeste=s.manifeste,
                      nationalite_transport=s.nationalite_transport, takikro=s.takikro, disp=s.disp,
                      banque=s.banque)
    if s.designation:
        apply_designation(rfcv_data, s.designation)
    # Date de FDI : saisie > PDF de la FDI > RFCV (signalée « non vérifiée »)
    controle_fdi = appliquer_fdi(rfcv_data, date_fdi=s.date_fdi, fdi_pdf=s.fdi_pdf)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = out_dir / f"{stem}.xml"
    generator = XMLGenerator(rfcv_data)
    generator.generate()
    generator.save(str(xml_path), pretty_print=True)
    corps_path, corps = write_corps(xml_path)

    summary = summarize(rfcv_data, reference, corps, parser.chassis_conflicts, other_drafts or {},
                        known_hs, settings=settings, controle_fdi=controle_fdi)
    return GenerationResult(xml_path=xml_path, corps_path=Path(corps_path), summary=summary)
