#!/usr/bin/env python3
"""
Tests automatisés pour le convertisseur PDF RFCV → XML ASYCUDA
"""
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pdf_extractor import PDFExtractor
from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator
from metrics import ConversionMetrics, MetricsCollector


class ConverterTester:
    """Testeur pour le convertisseur PDF → XML"""

    def __init__(self, output_dir: str = "output/tests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.collector = MetricsCollector()

    def test_single_pdf(self, pdf_path: str, verbose: bool = False, taux_douane: float = 573.139) -> ConversionMetrics:
        """
        Teste la conversion d'un seul PDF

        Args:
            pdf_path: Chemin du PDF à tester
            verbose: Afficher les détails
            taux_douane: Taux de change douanier (défaut: 573.139 pour tests)

        Returns:
            Métriques de la conversion
        """
        metrics = ConversionMetrics(pdf_file=pdf_path)

        try:
            if verbose:
                print(f"\n{'='*70}")
                print(f"Test: {Path(pdf_path).name}")
                print(f"{'='*70}")

            # Étape 1: Extraction PDF
            start_extract = time.time()
            with PDFExtractor(pdf_path) as extractor:
                text = extractor.extract_all_text()
                tables = extractor.extract_all_tables()

                metrics.pages_count = extractor.get_page_count()
                metrics.text_size = len(text)
                metrics.tables_count = len(tables)

            metrics.extraction_time = time.time() - start_extract

            if verbose:
                print(f"  Extraction: {metrics.extraction_time*1000:.2f}ms")
                print(f"  Pages: {metrics.pages_count}")
                print(f"  Texte: {metrics.text_size} caractères")
                print(f"  Tables: {metrics.tables_count}")

            # Étape 2: Parsing RFCV
            start_parse = time.time()
            parser = RFCVParser(pdf_path, taux_douane=taux_douane)
            rfcv_data = parser.parse()
            parse_time = time.time() - start_parse

            # Collecter métriques depuis RFCV
            temp_metrics = self.collector.collect_from_rfcv(pdf_path, rfcv_data)

            # Copier les métriques collectées
            metrics.has_exporter = temp_metrics.has_exporter
            metrics.has_consignee = temp_metrics.has_consignee
            metrics.has_transport = temp_metrics.has_transport
            metrics.has_financial = temp_metrics.has_financial
            metrics.has_valuation = temp_metrics.has_valuation
            metrics.items_count = temp_metrics.items_count
            metrics.containers_count = temp_metrics.containers_count
            metrics.total_cif = temp_metrics.total_cif
            metrics.total_fob = temp_metrics.total_fob
            metrics.total_weight = temp_metrics.total_weight
            metrics.total_packages = temp_metrics.total_packages
            metrics.fields_filled_rate = temp_metrics.fields_filled_rate
            metrics.warnings = temp_metrics.warnings

            if verbose:
                print(f"  Parsing: {parse_time*1000:.2f}ms")
                print(f"  Exportateur: {'✓' if metrics.has_exporter else '✗'}")
                print(f"  Importateur: {'✓' if metrics.has_consignee else '✗'}")
                print(f"  Articles: {metrics.items_count}")
                print(f"  Conteneurs: {metrics.containers_count}")
                print(f"  Valeur CIF: {metrics.total_cif}")
                print(f"  Taux remplissage: {metrics.fields_filled_rate:.1f}%")

            # Étape 3: Génération XML
            start_gen = time.time()
            generator = XMLGenerator(rfcv_data)
            generator.generate()

            output_xml = self.output_dir / f"{Path(pdf_path).stem}.xml"
            generator.save(str(output_xml), pretty_print=True)

            metrics.generation_time = time.time() - start_gen
            metrics.total_time = metrics.extraction_time + parse_time + metrics.generation_time

            if verbose:
                print(f"  Génération XML: {metrics.generation_time*1000:.2f}ms")
                print(f"  Total: {metrics.total_time*1000:.2f}ms")

            # Étape 4: Validation XML
            xml_valid = self.collector.validate_xml(str(output_xml), metrics)

            if verbose:
                print(f"  XML valide: {'✓' if xml_valid else '✗'}")
                print(f"  Taille XML: {metrics.xml_size/1024:.2f} KB")

                if metrics.warnings:
                    print(f"\n  ⚠️  Warnings ({len(metrics.warnings)}):")
                    for warning in metrics.warnings:
                        print(f"    - {warning}")

            metrics.success = True

        except Exception as e:
            metrics.success = False
            metrics.error_message = str(e)
            if verbose:
                print(f"  ❌ ERREUR: {e}")

        return metrics

    def test_batch(self, pdf_files: List[str], verbose: bool = False) -> MetricsCollector:
        """
        Teste plusieurs PDFs en batch

        Args:
            pdf_files: Liste des chemins PDF
            verbose: Afficher les détails

        Returns:
            Collecteur avec toutes les métriques
        """
        print(f"\n{'='*70}")
        print(f"TEST BATCH: {len(pdf_files)} fichiers")
        print(f"{'='*70}")

        for i, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] {Path(pdf_file).name}")

            metrics = self.test_single_pdf(pdf_file, verbose=verbose)
            self.collector.add_metrics(metrics)

            # Résumé court
            if metrics.success:
                print(f"  ✓ Succès - {metrics.items_count} articles, {metrics.fields_filled_rate:.1f}% remplis")
            else:
                print(f"  ✗ Échec - {metrics.error_message}")

        return self.collector

    def print_summary(self):
        """Affiche le résumé des tests"""
        summary = self.collector.get_summary()

        print(f"\n{'='*70}")
        print("RÉSUMÉ DES TESTS")
        print(f"{'='*70}")
        print(f"Total conversions: {summary['total_conversions']}")
        print(f"Réussies: {summary['successful']} ({summary['success_rate']:.1f}%)")
        print(f"Échouées: {summary['failed']}")
        print(f"\nTemps moyen:")
        print(f"  Extraction: {summary['avg_extraction_time_ms']:.2f}ms")
        print(f"  Génération: {summary['avg_generation_time_ms']:.2f}ms")
        print(f"  Total: {summary['avg_total_time_ms']:.2f}ms")
        print(f"\nDonnées extraites (moyenne):")
        print(f"  Articles: {summary['avg_items_count']:.1f}")
        print(f"  Conteneurs: {summary['avg_containers_count']:.1f}")
        print(f"  Taux remplissage: {summary['avg_fill_rate']:.1f}%")
        print(f"\nQualité:")
        print(f"  XMLs valides: {summary['xml_valid_count']}/{summary['total_conversions']}")
        print(f"  Total warnings: {summary['total_warnings']}")


def main():
    """Point d'entrée principal"""
    import argparse
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    from generate_report import ReportGenerator

    parser = argparse.ArgumentParser(description="Teste le convertisseur PDF → XML")
    parser.add_argument('pdf_files', nargs='*', help='Fichiers PDF à tester')
    parser.add_argument('-d', '--directory', help='Dossier contenant les PDFs')
    parser.add_argument('-v', '--verbose', action='store_true', help='Mode verbeux')
    parser.add_argument('-o', '--output', default='output/tests', help='Dossier de sortie')
    parser.add_argument('--no-report', action='store_true', help='Ne pas générer de rapport')

    args = parser.parse_args()

    # Déterminer les fichiers à tester
    pdf_files = []

    if args.directory:
        test_dir = Path(args.directory)
        pdf_files = list(test_dir.glob('*.pdf'))
    elif args.pdf_files:
        pdf_files = [Path(f) for f in args.pdf_files]
    else:
        # Par défaut: tous les PDFs dans tests/
        tests_dir = Path('tests')
        if tests_dir.exists():
            pdf_files = list(tests_dir.glob('*.pdf'))

    if not pdf_files:
        print("Aucun fichier PDF à tester.")
        print("Usage: python tests/test_converter.py -d tests/ -v")
        sys.exit(1)

    # Convertir en strings
    pdf_files = [str(f) for f in pdf_files]

    # Exécuter les tests
    tester = ConverterTester(output_dir=args.output)
    tester.test_batch(pdf_files, verbose=args.verbose)
    tester.print_summary()

    # Générer les rapports
    if not args.no_report:
        print(f"\n{'='*70}")
        print("GÉNÉRATION DES RAPPORTS")
        print(f"{'='*70}")
        report_gen = ReportGenerator(tester.collector)
        report_gen.generate_all()

    # Retourner code d'erreur si des tests ont échoué
    summary = tester.collector.get_summary()
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
