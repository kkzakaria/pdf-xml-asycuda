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


def convert_pdf_to_xml(pdf_path: str, output_path: str = None, verbose: bool = False) -> bool:
    """
    Convertit un PDF RFCV en XML ASYCUDA

    Args:
        pdf_path: Chemin vers le fichier PDF RFCV
        output_path: Chemin de sortie pour le XML (optionnel)
        verbose: Afficher les détails de la conversion

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

        parser = RFCVParser(pdf_path)
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
  %(prog)s "DOSSIER 18236.pdf"
  %(prog)s "DOSSIER 18236.pdf" -o output/dossier_18236.xml
  %(prog)s "DOSSIER 18236.pdf" -v
  %(prog)s *.pdf --batch
        """
    )

    parser.add_argument(
        'pdf_files',
        nargs='+',
        help='Fichier(s) PDF RFCV à convertir'
    )

    parser.add_argument(
        '-o', '--output',
        help='Chemin de sortie pour le fichier XML (un seul fichier seulement)',
        default=None
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

    args = parser.parse_args()

    # Mode batch ou fichier unique
    if len(args.pdf_files) > 1 or args.batch:
        if args.output:
            print("Avertissement: L'option -o est ignorée en mode batch.", file=sys.stderr)

        success_count = 0
        total_count = len(args.pdf_files)

        print(f"Conversion de {total_count} fichier(s)...")
        print("=" * 60)

        for pdf_file in args.pdf_files:
            print(f"\n[{success_count + 1}/{total_count}] {pdf_file}")
            if convert_pdf_to_xml(pdf_file, verbose=args.verbose):
                success_count += 1

        print("\n" + "=" * 60)
        print(f"Résultat: {success_count}/{total_count} conversions réussies")

        sys.exit(0 if success_count == total_count else 1)

    else:
        # Conversion d'un seul fichier
        pdf_file = args.pdf_files[0]
        success = convert_pdf_to_xml(pdf_file, args.output, args.verbose)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
