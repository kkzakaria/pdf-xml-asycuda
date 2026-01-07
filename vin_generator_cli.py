#!/usr/bin/env python3
"""
CLI de génération de VINs ISO 3779
Génère des numéros de châssis VIN indépendamment du PDF RFCV

Usage:
    python vin_generator_cli.py --quantity 180 --wmi LZS --year 2025
    python vin_generator_cli.py -n 100 -w LFV -y 2026 --format csv -o vins.csv
    python vin_generator_cli.py -n 50 -w LZS -y 2025 --vds ABCDE --plant A
"""

import sys
import argparse
import json
import csv
from pathlib import Path
from datetime import datetime, timezone

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from chassis_generator import ChassisFactory, VINGenerator


def generate_vins(
    quantity: int,
    wmi: str,
    vds: str,
    year: int,
    plant_code: str
) -> dict:
    """
    Génère des VINs ISO 3779 uniques

    Args:
        quantity: Nombre de VINs à générer
        wmi: World Manufacturer Identifier (3 caractères)
        vds: Vehicle Descriptor Section (5 caractères)
        year: Année modèle (2001-2030)
        plant_code: Code usine (1 caractère)

    Returns:
        Dictionnaire avec VINs et métadonnées
    """
    factory = ChassisFactory(ensure_unique=True)

    # Construire le préfixe pour tracking
    year_code = VINGenerator.YEAR_CODES.get(year, "S")
    prefix = f"{wmi}{vds}{year_code}"

    # Récupérer séquence de départ
    start_sequence = factory.sequence_manager.get_current_sequence(prefix) + 1

    # Générer les VINs
    vins = factory.create_unique_vin_batch(
        wmi=wmi,
        vds=vds,
        year=year,
        plant=plant_code,
        quantity=quantity
    )

    return {
        "success": True,
        "vins": vins,
        "quantity_generated": len(vins),
        "wmi": wmi,
        "vds": vds,
        "year": year,
        "plant_code": plant_code,
        "prefix": prefix,
        "start_sequence": start_sequence,
        "end_sequence": start_sequence + quantity - 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }


def export_json(result: dict) -> str:
    """Exporte en JSON"""
    output = {
        "success": result["success"],
        "vins": result["vins"],
        "metadata": {
            "quantity": result["quantity_generated"],
            "wmi": result["wmi"],
            "vds": result["vds"],
            "year": result["year"],
            "plant_code": result["plant_code"],
            "prefix": result["prefix"],
            "start_sequence": result["start_sequence"],
            "end_sequence": result["end_sequence"],
            "generated_at": result["generated_at"]
        }
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def export_csv(result: dict) -> str:
    """Exporte en CSV"""
    import io
    output = io.StringIO()
    writer = csv.writer(output)

    # En-tête
    writer.writerow(["index", "vin", "wmi", "vds", "year", "plant_code", "sequence"])

    # Données
    start_seq = result["start_sequence"]
    for i, vin in enumerate(result["vins"]):
        writer.writerow([
            i + 1,
            vin,
            result["wmi"],
            result["vds"],
            result["year"],
            result["plant_code"],
            start_seq + i
        ])

    return output.getvalue()


def export_text(result: dict) -> str:
    """Exporte en texte simple"""
    header = f"""# VINs générés le {result['generated_at']}
# Quantité: {result['quantity_generated']}
# WMI: {result['wmi']} | VDS: {result['vds']} | Année: {result['year']}
# Séquences: {result['start_sequence']} à {result['end_sequence']}
# =========================================================

"""
    return header + "\n".join(result["vins"])


def main():
    parser = argparse.ArgumentParser(
        description="Génère des VINs ISO 3779 indépendamment du PDF RFCV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s --quantity 180 --wmi LZS --year 2025
  %(prog)s -n 100 -w LFV -y 2026 --format csv -o vins.csv
  %(prog)s -n 50 -w LZS -y 2025 --vds ABCDE --plant A --format text

Structure VIN ISO 3779:
  Position:  1-3    4-8    9        10    11     12-17
             ----   -----  ----     ----  -----  ------
             WMI    VDS    Checksum Year  Plant  Séquence
             LZS    HCKZS  2        S     8      054073
"""
    )

    # Arguments requis
    parser.add_argument(
        "-n", "--quantity",
        type=int,
        required=True,
        help="Nombre de VINs à générer (1-10000)"
    )
    parser.add_argument(
        "-w", "--wmi",
        type=str,
        required=True,
        help="World Manufacturer Identifier - 3 caractères (ex: LZS, LFV)"
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        required=True,
        help="Année modèle (2001-2030)"
    )

    # Arguments optionnels
    parser.add_argument(
        "--vds",
        type=str,
        default="HCKZS",
        help="Vehicle Descriptor Section - 5 caractères (défaut: HCKZS)"
    )
    parser.add_argument(
        "--plant",
        type=str,
        default="S",
        help="Code usine - 1 caractère (défaut: S)"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["json", "csv", "text"],
        default="json",
        help="Format de sortie (défaut: json)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Fichier de sortie (défaut: stdout)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mode verbeux"
    )

    args = parser.parse_args()

    # Validation
    if args.quantity < 1 or args.quantity > 10000:
        parser.error("La quantité doit être entre 1 et 10000")

    if len(args.wmi) != 3:
        parser.error("Le WMI doit avoir exactement 3 caractères")

    if len(args.vds) != 5:
        parser.error("Le VDS doit avoir exactement 5 caractères")

    if len(args.plant) != 1:
        parser.error("Le code usine doit avoir exactement 1 caractère")

    if args.year < 2001 or args.year > 2030:
        parser.error("L'année doit être entre 2001 et 2030")

    # Génération
    if args.verbose:
        print(f"Génération de {args.quantity} VINs...", file=sys.stderr)
        print(f"  WMI: {args.wmi.upper()}", file=sys.stderr)
        print(f"  VDS: {args.vds.upper()}", file=sys.stderr)
        print(f"  Année: {args.year}", file=sys.stderr)
        print(f"  Usine: {args.plant.upper()}", file=sys.stderr)

    try:
        result = generate_vins(
            quantity=args.quantity,
            wmi=args.wmi.upper(),
            vds=args.vds.upper(),
            year=args.year,
            plant_code=args.plant.upper()
        )

        # Export selon format
        if args.format == "json":
            output = export_json(result)
        elif args.format == "csv":
            output = export_csv(result)
        else:  # text
            output = export_text(result)

        # Sortie
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            if args.verbose:
                print(f"\n✓ {result['quantity_generated']} VINs générés", file=sys.stderr)
                print(f"✓ Séquences: {result['start_sequence']} → {result['end_sequence']}", file=sys.stderr)
                print(f"✓ Fichier: {args.output}", file=sys.stderr)
        else:
            print(output)

    except ValueError as e:
        print(f"Erreur: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erreur inattendue: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
