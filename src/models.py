"""
Modèles de données pour la conversion PDF RFCV → XML ASYCUDA
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date


@dataclass
class Identification:
    """Informations d'identification de la déclaration"""
    customs_office_code: Optional[str] = None
    customs_office_name: Optional[str] = None
    type_of_declaration: Optional[str] = None
    declaration_procedure_code: Optional[str] = None
    manifest_reference: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[str] = None
    assessment_number: Optional[str] = None
    assessment_date: Optional[str] = None

    # Nouveaux champs PRIORITÉ 3
    rfcv_date: Optional[str] = None           # Date RFCV (DD/MM/YYYY)
    fdi_number: Optional[str] = None          # No. FDI/DAI
    fdi_date: Optional[str] = None            # Date FDI/DAI (DD/MM/YYYY)
    delivery_type: Optional[str] = None       # Type livraison (TOT/PART)


@dataclass
class Trader:
    """Informations sur un opérateur (exportateur, destinataire, déclarant)"""
    code: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    representative: Optional[str] = None
    reference: Optional[str] = None


@dataclass
class Country:
    """Informations sur les pays"""
    first_destination: Optional[str] = None
    trading_country: Optional[str] = None
    export_country_code: Optional[str] = None
    export_country_name: Optional[str] = None
    destination_country_code: Optional[str] = None
    destination_country_name: Optional[str] = None
    origin_country_name: Optional[str] = None


@dataclass
class TransportInfo:
    """Informations de transport"""
    vessel_identity: Optional[str] = None
    vessel_nationality: Optional[str] = None
    border_mode: Optional[str] = None
    container_flag: bool = False
    delivery_terms_code: Optional[str] = None
    border_office_code: Optional[str] = None
    border_office_name: Optional[str] = None
    loading_place_code: Optional[str] = None
    loading_place_name: Optional[str] = None
    location_of_goods: Optional[str] = None

    # Nouveaux champs PRIORITÉ 1
    bill_of_lading: Optional[str] = None        # No. Connaissement
    bl_date: Optional[str] = None               # Date Connaissement
    voyage_number: Optional[str] = None         # No. Voyage (ex: 535W)
    vessel_name: Optional[str] = None           # Nom navire/transporteur
    incoterm: Optional[str] = None              # CFR, FOB, CIF, etc.
    loading_location: Optional[str] = None      # Lieu chargement (ex: CNNGB)
    discharge_location: Optional[str] = None    # Lieu déchargement (ex: CIABJ)
    fcl_count: Optional[int] = None             # Nombre conteneurs complets
    lcl_count: Optional[int] = None             # Nombre conteneurs partiels


@dataclass
class Bank:
    """Informations bancaires"""
    code: Optional[str] = None
    name: Optional[str] = None
    branch: Optional[str] = None
    reference: Optional[str] = None


@dataclass
class Financial:
    """Informations financières"""
    transaction_code1: Optional[str] = None
    transaction_code2: Optional[str] = None
    bank: Optional[Bank] = None
    deferred_payment_ref: Optional[str] = None
    mode_of_payment: Optional[str] = None
    total_manual_taxes: Optional[float] = None
    global_taxes: Optional[float] = None
    total_taxes: Optional[float] = None

    # Nouveaux champs PRIORITÉ 2
    invoice_number: Optional[str] = None       # No. Facture (ex: 2025/GB/SN17705)
    invoice_date: Optional[str] = None         # Date Facture (DD/MM/YYYY)
    invoice_amount: Optional[float] = None     # Total Facture
    currency_code: Optional[str] = None        # Code Devise (USD, EUR, etc.)
    exchange_rate: Optional[float] = None      # Taux de Change


@dataclass
class CurrencyAmount:
    """Montant avec devise"""
    amount_national: Optional[float] = None
    amount_foreign: Optional[float] = None
    currency_code: Optional[str] = None
    currency_name: Optional[str] = None
    currency_rate: Optional[float] = None


@dataclass
class Valuation:
    """Informations de valorisation"""
    calculation_mode: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None  # Ajout PRIORITÉ 1
    total_cost: Optional[float] = None
    total_cif: Optional[float] = None
    invoice: Optional[CurrencyAmount] = None
    external_freight: Optional[CurrencyAmount] = None
    internal_freight: Optional[CurrencyAmount] = None
    insurance: Optional[CurrencyAmount] = None
    other_cost: Optional[CurrencyAmount] = None
    deduction: Optional[CurrencyAmount] = None
    total_invoice: Optional[float] = None
    total_weight: Optional[float] = None


@dataclass
class Container:
    """Informations conteneur"""
    item_number: Optional[int] = None
    identity: Optional[str] = None
    container_type: Optional[str] = None
    empty_full_indicator: Optional[str] = None
    gross_weight: Optional[float] = None
    packages_number: Optional[int] = None
    packages_weight: Optional[float] = None


@dataclass
class AttachedDocument:
    """Document attaché"""
    code: Optional[str] = None
    name: Optional[str] = None
    reference: Optional[str] = None
    from_rule: Optional[int] = None
    document_date: Optional[str] = None


@dataclass
class Package:
    """Informations colis"""
    number_of_packages: Optional[float] = None
    marks1: Optional[str] = None
    marks2: Optional[str] = None
    kind_code: Optional[str] = None
    kind_name: Optional[str] = None


@dataclass
class HSCode:
    """Code tarifaire HS"""
    commodity_code: Optional[str] = None
    precision_1: Optional[str] = None
    precision_2: Optional[str] = None
    precision_3: Optional[str] = None
    precision_4: Optional[str] = None


@dataclass
class SupplementaryUnit:
    """Unité supplémentaire"""
    code: Optional[str] = None
    name: Optional[str] = None
    quantity: Optional[float] = None


@dataclass
class Tarification:
    """Informations tarifaires"""
    hscode: Optional[HSCode] = None
    extended_procedure: Optional[str] = None
    national_procedure: Optional[str] = None
    supplementary_units: List[SupplementaryUnit] = field(default_factory=list)
    item_price: Optional[float] = None
    valuation_method: Optional[str] = None


@dataclass
class TaxationLine:
    """Ligne de taxation"""
    duty_tax_code: Optional[str] = None
    duty_tax_base: Optional[float] = None
    duty_tax_rate: Optional[float] = None
    duty_tax_amount: Optional[float] = None
    duty_tax_mp: Optional[str] = None
    duty_tax_calculation_type: Optional[str] = None


@dataclass
class Taxation:
    """Informations de taxation"""
    item_taxes_amount: Optional[float] = None
    item_taxes_guaranteed: Optional[float] = None
    taxation_lines: List[TaxationLine] = field(default_factory=list)


@dataclass
class ValuationItem:
    """Valorisation d'un article"""
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    total_cost: Optional[float] = None
    total_cif: Optional[float] = None
    rate_of_adjustment: Optional[float] = None
    statistical_value: Optional[float] = None
    invoice: Optional[CurrencyAmount] = None
    external_freight: Optional[CurrencyAmount] = None
    internal_freight: Optional[CurrencyAmount] = None
    insurance: Optional[CurrencyAmount] = None
    other_cost: Optional[CurrencyAmount] = None
    deduction: Optional[CurrencyAmount] = None


@dataclass
class Item:
    """Article de la déclaration"""
    attached_documents: List[AttachedDocument] = field(default_factory=list)
    packages: Optional[Package] = None
    incoterms_code: Optional[str] = None
    tarification: Optional[Tarification] = None
    goods_description: Optional[str] = None
    commercial_description: Optional[str] = None
    country_of_origin_code: Optional[str] = None
    summary_declaration: Optional[str] = None
    free_text_1: Optional[str] = None
    free_text_2: Optional[str] = None
    taxation: Optional[Taxation] = None
    valuation_item: Optional[ValuationItem] = None


@dataclass
class Property:
    """Propriétés du formulaire"""
    sad_flow: Optional[str] = None
    form_number: Optional[int] = None
    total_forms: Optional[int] = None
    total_items: Optional[int] = None
    total_packages: Optional[int] = None
    date_of_declaration: Optional[str] = None
    selected_page: Optional[int] = None

    # Nouveau champ PRIORITÉ 3
    package_type: Optional[str] = None  # Type de colisage (CARTONS, PACKAGES, COLIS, PALETTES)


@dataclass
class RFCVData:
    """Structure complète des données extraites du PDF RFCV"""
    property: Optional[Property] = None
    identification: Optional[Identification] = None
    exporter: Optional[Trader] = None
    consignee: Optional[Trader] = None
    declarant: Optional[Trader] = None
    country: Optional[Country] = None
    transport: Optional[TransportInfo] = None
    financial: Optional[Financial] = None
    valuation: Optional[Valuation] = None
    containers: List[Container] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)

    # Champs additionnels
    value_details: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire pour faciliter la manipulation"""
        return {
            'property': self.property,
            'identification': self.identification,
            'traders': {
                'exporter': self.exporter,
                'consignee': self.consignee,
                'declarant': self.declarant
            },
            'country': self.country,
            'transport': self.transport,
            'financial': self.financial,
            'valuation': self.valuation,
            'containers': self.containers,
            'items': self.items,
            'value_details': self.value_details
        }
