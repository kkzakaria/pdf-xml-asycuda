"""
Module de métriques pour évaluer la qualité de la conversion PDF → XML
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from models import RFCVData, Trader, Item


@dataclass
class ConversionMetrics:
    """Métriques d'une conversion PDF → XML"""

    # Identification
    pdf_file: str
    success: bool = False
    error_message: Optional[str] = None

    # Temps d'exécution
    extraction_time: float = 0.0
    generation_time: float = 0.0
    total_time: float = 0.0

    # Métriques d'extraction
    pages_count: int = 0
    text_size: int = 0
    tables_count: int = 0

    # Complétude des données
    has_exporter: bool = False
    has_consignee: bool = False
    has_transport: bool = False
    has_financial: bool = False
    has_valuation: bool = False

    # Articles et conteneurs
    items_count: int = 0
    containers_count: int = 0

    # Valeurs extraites
    total_cif: Optional[float] = None
    total_fob: Optional[float] = None
    total_weight: Optional[float] = None
    total_packages: Optional[int] = None

    # Qualité XML
    xml_size: int = 0
    xml_valid: bool = False

    # Taux de remplissage (0-100%)
    fields_filled_rate: float = 0.0

    # Erreurs détectées
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            'pdf_file': Path(self.pdf_file).name,
            'success': self.success,
            'error_message': self.error_message,
            'extraction_time_ms': round(self.extraction_time * 1000, 2),
            'generation_time_ms': round(self.generation_time * 1000, 2),
            'total_time_ms': round(self.total_time * 1000, 2),
            'pages_count': self.pages_count,
            'text_size': self.text_size,
            'tables_count': self.tables_count,
            'has_exporter': self.has_exporter,
            'has_consignee': self.has_consignee,
            'has_transport': self.has_transport,
            'has_financial': self.has_financial,
            'has_valuation': self.has_valuation,
            'items_count': self.items_count,
            'containers_count': self.containers_count,
            'total_cif': self.total_cif,
            'total_fob': self.total_fob,
            'total_weight': self.total_weight,
            'total_packages': self.total_packages,
            'xml_size_kb': round(self.xml_size / 1024, 2),
            'xml_valid': self.xml_valid,
            'fields_filled_rate': round(self.fields_filled_rate, 2),
            'warnings_count': len(self.warnings),
            'warnings': self.warnings
        }


class MetricsCollector:
    """Collecteur de métriques pour la conversion"""

    def __init__(self):
        self.metrics: List[ConversionMetrics] = []

    def collect_from_rfcv(self, pdf_path: str, rfcv_data: RFCVData) -> ConversionMetrics:
        """
        Collecte les métriques depuis les données RFCV

        Args:
            pdf_path: Chemin du PDF source
            rfcv_data: Données RFCV extraites

        Returns:
            Métriques collectées
        """
        metrics = ConversionMetrics(pdf_file=pdf_path)

        # Complétude des traders
        metrics.has_exporter = self._has_trader_data(rfcv_data.exporter)
        metrics.has_consignee = self._has_trader_data(rfcv_data.consignee)

        # Données de transport
        metrics.has_transport = rfcv_data.transport is not None and (
            rfcv_data.transport.vessel_identity is not None or
            rfcv_data.transport.delivery_terms_code is not None
        )

        # Données financières
        metrics.has_financial = rfcv_data.financial is not None and (
            rfcv_data.financial.mode_of_payment is not None
        )

        # Valorisation
        metrics.has_valuation = rfcv_data.valuation is not None
        if rfcv_data.valuation:
            metrics.total_cif = rfcv_data.valuation.total_cif
            metrics.total_fob = rfcv_data.valuation.total_cost
            metrics.total_weight = rfcv_data.valuation.total_weight

        # Articles et conteneurs
        metrics.items_count = len(rfcv_data.items) if rfcv_data.items else 0
        metrics.containers_count = len(rfcv_data.containers) if rfcv_data.containers else 0

        # Packages
        if rfcv_data.property and rfcv_data.property.total_packages:
            metrics.total_packages = rfcv_data.property.total_packages

        # Calcul du taux de remplissage
        metrics.fields_filled_rate = self._calculate_fill_rate(rfcv_data)

        # Warnings
        metrics.warnings = self._detect_warnings(rfcv_data)

        return metrics

    def _has_trader_data(self, trader: Optional[Trader]) -> bool:
        """Vérifie si un trader a des données"""
        if not trader:
            return False
        return trader.name is not None and trader.name.strip() != ""

    def _calculate_fill_rate(self, rfcv_data: RFCVData) -> float:
        """
        Calcule le taux de remplissage des champs (0-100%)

        Args:
            rfcv_data: Données RFCV

        Returns:
            Pourcentage de champs remplis
        """
        total_fields = 0
        filled_fields = 0

        # P3.7: Identification (4 nouveaux champs PRIORITÉ 3)
        total_fields += 4
        if rfcv_data.identification:
            if rfcv_data.identification.rfcv_date: filled_fields += 1
            if rfcv_data.identification.fdi_number: filled_fields += 1
            if rfcv_data.identification.fdi_date: filled_fields += 1
            if rfcv_data.identification.delivery_type: filled_fields += 1

        # P3.7: Property (1 nouveau champ PRIORITÉ 3)
        total_fields += 1
        if rfcv_data.property:
            if rfcv_data.property.package_type: filled_fields += 1

        # Traders (3 traders × 3 champs)
        for trader in [rfcv_data.exporter, rfcv_data.consignee, rfcv_data.declarant]:
            total_fields += 3
            if trader:
                if trader.code: filled_fields += 1
                if trader.name: filled_fields += 1
                if trader.address: filled_fields += 1

        # Transport (8 champs clés) - P4.2: ajout loading_place_name
        total_fields += 8
        if rfcv_data.transport:
            if rfcv_data.transport.vessel_identity: filled_fields += 1
            if rfcv_data.transport.border_mode: filled_fields += 1
            if rfcv_data.transport.delivery_terms_code: filled_fields += 1
            if rfcv_data.transport.loading_place_code: filled_fields += 1
            if rfcv_data.transport.location_of_goods: filled_fields += 1
            if rfcv_data.transport.border_office_code: filled_fields += 1
            if rfcv_data.transport.container_flag is not None: filled_fields += 1
            # P4.2: Nouveau champ
            if rfcv_data.transport.loading_place_name: filled_fields += 1

        # Valuation (5 champs clés)
        total_fields += 5
        if rfcv_data.valuation:
            if rfcv_data.valuation.total_cif: filled_fields += 1
            if rfcv_data.valuation.total_cost: filled_fields += 1
            if rfcv_data.valuation.total_weight: filled_fields += 1
            if rfcv_data.valuation.gross_weight: filled_fields += 1
            if rfcv_data.valuation.total_invoice: filled_fields += 1

        # Financial (7 champs clés) - P2: ajout de 5 nouveaux champs
        total_fields += 7
        if rfcv_data.financial:
            if rfcv_data.financial.mode_of_payment: filled_fields += 1
            if rfcv_data.financial.deferred_payment_ref: filled_fields += 1
            # P2: Nouveaux champs financiers
            if rfcv_data.financial.invoice_number: filled_fields += 1
            if rfcv_data.financial.invoice_date: filled_fields += 1
            if rfcv_data.financial.invoice_amount: filled_fields += 1
            if rfcv_data.financial.currency_code: filled_fields += 1
            if rfcv_data.financial.exchange_rate: filled_fields += 1

        # Country (5 champs clés) - P4.1: ajout trading_country
        total_fields += 5
        if rfcv_data.country:
            if rfcv_data.country.export_country_code: filled_fields += 1
            if rfcv_data.country.export_country_name: filled_fields += 1
            if rfcv_data.country.destination_country_code: filled_fields += 1
            if rfcv_data.country.origin_country_name: filled_fields += 1
            # P4.1: Nouveau champ
            if rfcv_data.country.trading_country: filled_fields += 1

        # Items et containers
        total_fields += 2
        if rfcv_data.items and len(rfcv_data.items) > 0: filled_fields += 1
        if rfcv_data.containers and len(rfcv_data.containers) > 0: filled_fields += 1

        return (filled_fields / total_fields * 100) if total_fields > 0 else 0

    def _detect_warnings(self, rfcv_data: RFCVData) -> List[str]:
        """
        Détecte les problèmes potentiels dans les données

        Args:
            rfcv_data: Données RFCV

        Returns:
            Liste de warnings
        """
        warnings = []

        # Traders manquants
        if not self._has_trader_data(rfcv_data.exporter):
            warnings.append("Exportateur non extrait")

        if not self._has_trader_data(rfcv_data.consignee):
            warnings.append("Importateur/Destinataire non extrait")

        # Valeurs numériques manquantes
        if not rfcv_data.valuation or not rfcv_data.valuation.total_cif:
            warnings.append("Valeur CIF manquante")

        if not rfcv_data.valuation or not rfcv_data.valuation.total_weight:
            warnings.append("Poids total manquant")

        # Articles
        if not rfcv_data.items or len(rfcv_data.items) == 0:
            warnings.append("Aucun article extrait")

        # Conteneurs
        if rfcv_data.transport and rfcv_data.transport.container_flag:
            if not rfcv_data.containers or len(rfcv_data.containers) == 0:
                warnings.append("Conteneurs marqués mais non extraits")

        return warnings

    def validate_xml(self, xml_path: str, metrics: ConversionMetrics) -> bool:
        """
        Valide le XML généré

        Args:
            xml_path: Chemin du fichier XML
            metrics: Métriques à mettre à jour

        Returns:
            True si le XML est valide
        """
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Taille du fichier
            metrics.xml_size = Path(xml_path).stat().st_size

            # Vérification structure basique
            required_sections = [
                'Property', 'Identification', 'Traders', 'Transport',
                'Financial', 'Valuation'
            ]

            for section in required_sections:
                if root.find(section) is None:
                    metrics.warnings.append(f"Section XML manquante: {section}")
                    return False

            metrics.xml_valid = True
            return True

        except ET.ParseError as e:
            metrics.warnings.append(f"Erreur parsing XML: {str(e)}")
            return False
        except Exception as e:
            metrics.warnings.append(f"Erreur validation XML: {str(e)}")
            return False

    def add_metrics(self, metrics: ConversionMetrics):
        """Ajoute des métriques à la collection"""
        self.metrics.append(metrics)

    def get_summary(self) -> Dict[str, Any]:
        """
        Génère un résumé des métriques

        Returns:
            Dictionnaire de statistiques globales
        """
        if not self.metrics:
            return {}

        total = len(self.metrics)
        success = sum(1 for m in self.metrics if m.success)

        return {
            'total_conversions': total,
            'successful': success,
            'failed': total - success,
            'success_rate': round((success / total * 100), 2),
            'avg_extraction_time_ms': round(
                sum(m.extraction_time for m in self.metrics) / total * 1000, 2
            ),
            'avg_generation_time_ms': round(
                sum(m.generation_time for m in self.metrics) / total * 1000, 2
            ),
            'avg_total_time_ms': round(
                sum(m.total_time for m in self.metrics) / total * 1000, 2
            ),
            'avg_items_count': round(
                sum(m.items_count for m in self.metrics) / total, 2
            ),
            'avg_containers_count': round(
                sum(m.containers_count for m in self.metrics) / total, 2
            ),
            'avg_fill_rate': round(
                sum(m.fields_filled_rate for m in self.metrics) / total, 2
            ),
            'total_warnings': sum(len(m.warnings) for m in self.metrics),
            'xml_valid_count': sum(1 for m in self.metrics if m.xml_valid),
        }

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Retourne toutes les métriques en format dict"""
        return [m.to_dict() for m in self.metrics]


def measure_conversion_time(func):
    """Décorateur pour mesurer le temps d'exécution"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        return result, elapsed
    return wrapper
