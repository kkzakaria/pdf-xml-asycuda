#!/usr/bin/env python3
"""
Script d'ajout de préfixes VIN chinois
========================================

Ajoute les préfixes VIN chinois observés dans les RFCV réels
à la base de données VinPrefixes.txt.

Usage:
    python3 scripts/add_chinese_prefixes.py
"""

import sys
from pathlib import Path

# Préfixes chinois observés dans les RFCV réels
CHINESE_PREFIXES = [
    # Format: (wmi_vds_8chars, year_code, wmi, manufacturer)

    # Apsonic (LZS) - Observé dans FCVR-189
    ("LZSHCKZS", "2", "LZS", "Apsonic"),
    ("LZSHCKZA", "2", "LZS", "Apsonic"),
    ("LZSHCKZD", "2", "LZS", "Apsonic"),

    # Lifan (LFV)
    ("LFVBA01A", "5", "LFV", "Lifan"),
    ("LFVBA02A", "6", "LFV", "Lifan"),

    # Haojue/Suzuki (LBV)
    ("LBVGW02B", "7", "LBV", "Haojue/Suzuki"),
    ("LBVGW03B", "8", "LBV", "Haojue/Suzuki"),

    # Jianshe (LDC)
    ("LDCJS01C", "5", "LDC", "Jianshe"),
    ("LDCJS02C", "6", "LDC", "Jianshe"),

    # Zongshen (LGX)
    ("LGXZS01X", "7", "LGX", "Zongshen"),
    ("LGXZS02X", "8", "LGX", "Zongshen"),

    # Qingqi (LJD)
    ("LJDQQ01D", "5", "LJD", "Qingqi"),
    ("LJDQQ02D", "6", "LJD", "Qingqi"),

    # Dayun (LYL)
    ("LYLDY01L", "7", "LYL", "Dayun"),
    ("LYLDY02L", "8", "LYL", "Dayun"),
]


def add_chinese_prefixes():
    """Ajoute les préfixes chinois à VinPrefixes.txt"""

    db_path = Path(__file__).parent.parent / "data" / "VinPrefixes.txt"

    if not db_path.exists():
        print(f"❌ Fichier non trouvé: {db_path}")
        return False

    # Lire préfixes existants
    with open(db_path, "r") as f:
        existing_lines = f.read().splitlines()

    # Extraire préfixes existants (sans header)
    existing_prefixes = set()
    for line in existing_lines:
        if line and not line.startswith("VinPos"):
            parts = line.split()
            if len(parts) >= 2:
                existing_prefixes.add((parts[0], parts[1]))

    print(f"📊 Préfixes existants: {len(existing_prefixes)}")

    # Ajouter nouveaux préfixes chinois
    new_prefixes = []
    for wmi_vds, year_code, wmi, manufacturer in CHINESE_PREFIXES:
        key = (wmi_vds, year_code)
        if key not in existing_prefixes:
            new_prefixes.append(f"{wmi_vds}   {year_code}")
            print(f"  ➕ Ajout: {wmi_vds} {year_code} ({manufacturer})")

    if not new_prefixes:
        print("\n✅ Tous les préfixes chinois sont déjà présents")
        return True

    # Écrire fichier mis à jour
    with open(db_path, "a") as f:
        f.write("\n")
        f.write("# Préfixes chinois ajoutés manuellement\n")
        for prefix in new_prefixes:
            f.write(prefix + "\n")

    print(f"\n✅ {len(new_prefixes)} nouveaux préfixes chinois ajoutés")
    print(f"📊 Total préfixes: {len(existing_prefixes) + len(new_prefixes)}")

    return True


def verify_chinese_indexing():
    """Vérifie que la Chine est maintenant indexée"""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

    from vin_prefix_database import VINPrefixDatabase

    print("\n🔍 Vérification indexation...")

    # Recharger base de données
    db = VINPrefixDatabase()

    # Vérifier pays
    countries = db.list_countries()
    print(f"\n📍 Pays indexés ({len(countries)}): {countries}")

    if "China" in countries:
        china_count = len(db._country_index["China"])
        print(f"✅ China indexé avec {china_count} préfixes")

        # Afficher quelques exemples
        print("\n📋 Exemples de préfixes chinois:")
        for prefix in db._country_index["China"][:5]:
            print(f"  - {prefix.wmi_vds} {prefix.year_code} ({prefix.manufacturer})")
    else:
        print("❌ China non indexé")

    return "China" in countries


if __name__ == "__main__":
    print("=" * 70)
    print("  Ajout Préfixes VIN Chinois".center(70))
    print("=" * 70)

    success = add_chinese_prefixes()

    if success:
        verify_chinese_indexing()

    print("\n" + "=" * 70)
