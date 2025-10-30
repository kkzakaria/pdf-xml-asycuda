#!/usr/bin/env python3
"""
Convertisseur PDF RFCV → XML ASYCUDA
Script CLI principal pour convertir les fichiers PDF RFCV en format XML ASYCUDA
"""
import argparse
import sys
import os
from pathlib import Path

# Ajouter le dossier src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from rfcv_parser import RFCVParser
from xml_generator import XMLGenerator
from batch_processor import BatchProcessor, BatchConfig
from batch_report import BatchReportGenerator


def convert_pdf_to_xml(pdf_path: str, output_path: str = None, verbose: bool = False, taux_douane: float = None) -> bool:
    """
    Convertit un PDF RFCV en XML ASYCUDA

    Args:
        pdf_path: Chemin vers le fichier PDF RFCV
        output_path: Chemin de sortie pour le XML (optionnel)
        verbose: Afficher les détails de la conversion
        taux_douane: Taux de change douanier pour calcul assurance (format: 573.1390)

    Returns:
        True si la conversion a réussi, False sinon
    """
    try:
        # Vérifier que le fichier existe
        if not os.path.exists(pdf_path):
            print(f"Erreur: Le fichier '{pdf_path}' n'existe pas.", file=sys.stderr)
            return False

        # Générer le chemin de sortie si non spécifié
        if output_path is None:
            pdf_name = Path(pdf_path).stem
            output_path = f"output/{pdf_name}.xml"

        # Créer le dossier output s'il n'existe pas
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        if verbose:
            print(f"Conversion de: {pdf_path}")
            print(f"Sortie vers: {output_path}")
            print("-" * 60)

        # Étape 1: Parser le PDF RFCV
        if verbose:
            print("Étape 1/2: Extraction et parsing du PDF...")
            if taux_douane:
                print(f"  - Taux douanier: {taux_douane:.4f}")

        parser = RFCVParser(pdf_path, taux_douane=taux_douane)
        rfcv_data = parser.parse()

        if verbose:
            print(f"  ✓ Extraction réussie")
            print(f"  - Importateur: {rfcv_data.consignee.name if rfcv_data.consignee else 'N/A'}")
            print(f"  - Exportateur: {rfcv_data.exporter.name if rfcv_data.exporter else 'N/A'}")
            print(f"  - Nombre d'articles: {len(rfcv_data.items)}")
            print(f"  - Nombre de conteneurs: {len(rfcv_data.containers)}")
            print(f"  - Valeur CIF totale: {rfcv_data.valuation.total_cif if rfcv_data.valuation else 'N/A'}")

        # Étape 2: Générer le XML ASYCUDA
        if verbose:
            print("\nÉtape 2/2: Génération du XML ASYCUDA...")

        generator = XMLGenerator(rfcv_data)
        generator.generate()
        generator.save(output_path, pretty_print=True)

        if verbose:
            print(f"  ✓ Génération XML réussie")
            print("-" * 60)

        print(f"✓ Conversion terminée avec succès!")
        print(f"  Fichier XML généré: {output_path}")

        return True

    except Exception as e:
        print(f"Erreur lors de la conversion: {e}", file=sys.stderr)
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Point d'entrée principal du script"""
    parser = argparse.ArgumentParser(
        description="Convertit les fichiers PDF RFCV en format XML ASYCUDA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  # Fichier unique
  %(prog)s "DOSSIER 18236.pdf"
  %(prog)s "DOSSIER 18236.pdf" -o output/dossier_18236.xml

  # Batch simple
  %(prog)s *.pdf --batch
  %(prog)s "DOSSIER 18236.pdf" "DOSSIER 18237.pdf" --batch

  # Batch avec dossier
  %(prog)s -d tests/ --batch
  %(prog)s -d tests/ --recursive --batch

  # Batch parallèle avec rapport
  %(prog)s -d pdfs/ --batch --workers 4 --report batch_results
  %(prog)s -d tests/ --pattern "RFCV*.pdf" --batch --workers 2
        """
    )

    parser.add_argument(
        'pdf_files',
        nargs='*',
        help='Fichier(s) PDF RFCV à convertir'
    )

    parser.add_argument(
        '-d', '--directory',
        help='Dossier contenant les fichiers PDF à traiter',
        default=None
    )

    parser.add_argument(
        '-o', '--output',
        help='Chemin de sortie pour le fichier XML (un seul fichier) ou dossier (batch)',
        default='output'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Afficher les détails de la conversion'
    )

    parser.add_argument(
        '--batch',
        action='store_true',
        help='Mode batch: convertir plusieurs fichiers'
    )

    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Recherche récursive dans les sous-dossiers (avec -d)'
    )

    parser.add_argument(
        '--pattern',
        default='*.pdf',
        help='Pattern pour filtrer les fichiers PDF (défaut: *.pdf)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='Nombre de workers pour traitement parallèle (défaut: 1)'
    )

    parser.add_argument(
        '--report',
        default=None,
        help='Générer un rapport batch (formats: .json, .csv, .md ou sans extension pour tous)'
    )

    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Désactiver la barre de progression'
    )

    parser.add_argument(
        '--taux-douane',
        type=float,
        default=None,
        help='Taux de change douanier pour calcul assurance (format: 573.1390, avec 4 décimales)'
    )

    args = parser.parse_args()

    # Déterminer le mode d'opération
    is_batch_mode = args.batch or args.directory or len(args.pdf_files) > 1 or args.workers > 1

    if is_batch_mode:
        # MODE BATCH
        if args.output and not Path(args.output).is_dir() and len(args.pdf_files) <= 1 and not args.directory:
            print("Avertissement: En mode batch, -o spécifie un dossier, pas un fichier.", file=sys.stderr)

        # Construire la liste des inputs
        input_paths = []
        if args.directory:
            input_paths.append(args.directory)
        if args.pdf_files:
            input_paths.extend(args.pdf_files)

        if not input_paths:
            print("Erreur: Aucun fichier ou dossier spécifié.", file=sys.stderr)
            print("Utilisez -d pour un dossier ou spécifiez des fichiers PDF.", file=sys.stderr)
            sys.exit(1)

        # Créer la configuration batch
        config = BatchConfig(
            input_paths=input_paths,
            output_dir=args.output,
            recursive=args.recursive,
            pattern=args.pattern,
            workers=args.workers,
            continue_on_error=True,
            verbose=args.verbose,
            progress_bar=not args.no_progress
        )

        # Exécuter le traitement batch
        processor = BatchProcessor(config)
        batch_results = processor.process()

        # Générer les rapports si demandé
        if args.report:
            report_gen = BatchReportGenerator(batch_results)

            # Déterminer le format
            report_path = Path(args.report)
            if report_path.suffix:
                # Format spécifique
                if report_path.suffix == '.json':
                    report_gen.generate_json(str(report_path))
                elif report_path.suffix == '.csv':
                    report_gen.generate_csv(str(report_path))
                elif report_path.suffix == '.md':
                    report_gen.generate_markdown(str(report_path))
                else:
                    print(f"Warning: Format '{report_path.suffix}' non supporté. Utilisation de tous les formats.", file=sys.stderr)
                    report_gen.generate_all(report_path.stem)
            else:
                # Tous les formats
                report_gen.generate_all(args.report)

        # Code de sortie
        sys.exit(0 if batch_results['success'] else 1)

    else:
        # MODE FICHIER UNIQUE
        if not args.pdf_files:
            print("Erreur: Aucun fichier PDF spécifié.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

        # Vérifier que le taux douanier est fourni
        if args.taux_douane is None:
            print("Erreur: Le taux douanier est obligatoire (--taux-douane).", file=sys.stderr)
            print("Exemple: --taux-douane 573.1390", file=sys.stderr)
            sys.exit(1)

        pdf_file = args.pdf_files[0]
        success = convert_pdf_to_xml(
            pdf_file,
            args.output if args.output != 'output' else None,
            args.verbose,
            taux_douane=args.taux_douane
        )
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
