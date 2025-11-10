"""
Service de conversion PDF → XML
Wrapper autour de rfcv_parser et xml_generator
"""
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

# Ajouter src au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator
from metrics import MetricsCollector


class ConversionService:
    """Service de conversion PDF RFCV → XML ASYCUDA"""

    @staticmethod
    def convert_pdf_to_xml(
        pdf_path: str,
        output_path: str,
        verbose: bool = False,
        taux_douane: float = None,
        rapport_paiement: str = None,
        chassis_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convertit un PDF RFCV en XML ASYCUDA

        Args:
            pdf_path: Chemin du fichier PDF
            output_path: Chemin de sortie XML
            verbose: Mode verbeux
            taux_douane: Taux de change douanier pour calcul assurance (optionnel)
            rapport_paiement: Numéro de rapport de paiement/quittance Trésor (optionnel)
            chassis_config: Configuration pour génération automatique châssis VIN (optionnel)

        Returns:
            Dictionnaire avec résultats et métriques
        """
        start_time = time.time()
        result = {
            'success': False,
            'pdf_file': pdf_path,
            'output_file': None,
            'error_message': None,
            'processing_time': 0.0,
            'metrics': None
        }

        try:
            # Vérifier que le fichier existe
            if not Path(pdf_path).exists():
                result['error_message'] = f"Fichier introuvable: {pdf_path}"
                return result

            # Parser le PDF
            if verbose:
                print(f"Parsing PDF: {pdf_path}")
                if taux_douane:
                    print(f"  Taux douanier: {taux_douane:.4f}")
                if rapport_paiement:
                    print(f"  Rapport de paiement: {rapport_paiement}")

            parser = RFCVParser(pdf_path, taux_douane=taux_douane, rapport_paiement=rapport_paiement, chassis_config=chassis_config)
            rfcv_data = parser.parse()

            # Générer le XML
            if verbose:
                print(f"Generating XML: {output_path}")

            generator = XMLGenerator(rfcv_data)
            generator.generate()

            # Créer le dossier output si nécessaire
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            generator.save(output_path, pretty_print=True)

            # Collecter les métriques
            collector = MetricsCollector()
            metrics = collector.collect_from_rfcv(pdf_path, rfcv_data)
            metrics.success = True
            metrics.total_time = time.time() - start_time

            # Valider le XML
            collector.validate_xml(output_path, metrics)

            result['success'] = True
            result['output_file'] = output_path
            result['processing_time'] = metrics.total_time
            result['metrics'] = metrics

            if verbose:
                print(f"✓ Conversion successful: {Path(pdf_path).name} → {Path(output_path).name}")

        except Exception as e:
            result['error_message'] = str(e)
            result['processing_time'] = time.time() - start_time

            if verbose:
                print(f"✗ Conversion failed: {e}")
                traceback.print_exc()

        return result

    @staticmethod
    def validate_pdf(pdf_path: str, taux_douane: float = None) -> Dict[str, Any]:
        """
        Valide un PDF RFCV sans faire la conversion complète

        Args:
            pdf_path: Chemin du fichier PDF
            taux_douane: Taux de change douanier (optionnel)

        Returns:
            Résultat de validation
        """
        result = {
            'valid': False,
            'pdf_file': pdf_path,
            'error_message': None,
            'warnings': []
        }

        try:
            # Vérifier que le fichier existe
            if not Path(pdf_path).exists():
                result['error_message'] = f"Fichier introuvable: {pdf_path}"
                return result

            # Essayer de parser sans générer XML
            parser = RFCVParser(pdf_path, taux_douane=taux_douane)
            rfcv_data = parser.parse()

            # Vérifications basiques
            if not rfcv_data.exporter or not rfcv_data.exporter.name:
                result['warnings'].append("Exportateur non extrait")

            if not rfcv_data.consignee or not rfcv_data.consignee.name:
                result['warnings'].append("Importateur/Consignataire non extrait")

            if not rfcv_data.items or len(rfcv_data.items) == 0:
                result['warnings'].append("Aucun article extrait")

            if not rfcv_data.valuation or not rfcv_data.valuation.total_cif:
                result['warnings'].append("Valeur CIF manquante")

            result['valid'] = True

        except Exception as e:
            result['error_message'] = str(e)

        return result


# Instance globale
conversion_service = ConversionService()
