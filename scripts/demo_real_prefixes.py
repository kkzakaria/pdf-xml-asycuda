#!/usr/bin/env python3
"""
Démonstration des préfixes VIN réels
=====================================

Démontre l'utilisation de la base de 62,000+ préfixes VIN réels
pour générer des VIN authentiques avec fabricants mondiaux.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chassis_generator import ChassisFactory
from vin_prefix_database import VINPrefixDatabase


def print_section(title: str):
    """Affiche un séparateur de section"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def demo_prefix_database():
    """Démonstration base de données préfixes"""
    print_section("1. Base de Données Préfixes VIN Réels")

    db = VINPrefixDatabase()

    # Statistiques
    stats = db.get_statistics()
    print(f"\n📊 Statistiques globales:")
    print(f"  - Total préfixes: {stats['total_prefixes']:,}")
    print(f"  - WMI uniques: {stats['unique_wmis']}")
    print(f"  - Fabricants indexés: {stats['indexed_manufacturers']}")
    print(f"  - Pays indexés: {stats['indexed_countries']}")

    print(f"\n🏭 Fabricants disponibles ({len(stats['manufacturers'])}):")
    for mfr in stats['manufacturers']:
        count = len(db.search_by_manufacturer(mfr))
        print(f"  - {mfr}: {count:,} préfixes")

    print(f"\n🌍 Pays disponibles:")
    for country in stats['countries']:
        count = len(db._country_index[country])
        print(f"  - {country}: {count:,} préfixes")

    print(f"\n🔝 Top 10 WMI (par nombre de préfixes):")
    for wmi in stats['top_10_wmis']:
        count = len(db._wmi_index[wmi])
        prefix_sample = db._wmi_index[wmi][0]
        mfr = prefix_sample.manufacturer or "Inconnu"
        print(f"  - {wmi}: {count:,} préfixes ({mfr})")


def demo_factory_with_real_prefixes():
    """Démonstration génération VIN avec préfixes réels"""
    print_section("2. Génération VIN avec Préfixes Réels")

    factory = ChassisFactory()

    if not factory.prefix_db:
        print("\n⚠️  Base de préfixes non disponible")
        return

    # Fabricants spécifiques
    manufacturers = ["Ford", "Toyota", "BMW", "Chevrolet"]

    print(f"\n📋 VIN par fabricant:")
    for mfr in manufacturers:
        try:
            vin = factory.create_vin_from_real_prefix(manufacturer=mfr, sequence=1)
            result = factory.validate(vin)
            checkmark = "✅" if result.checksum_valid else "❌"
            print(f"  {mfr:12s} → {vin} {checkmark}")
        except ValueError as e:
            print(f"  {mfr:12s} → Erreur: {e}")

    # Lot consécutif Ford
    print(f"\n📋 Lot de 10 VIN consécutifs (Ford):")
    try:
        batch = factory.create_vin_batch_from_real_prefixes(
            manufacturer="Ford",
            start_sequence=1,
            quantity=10
        )
        for i, vin in enumerate(batch, 1):
            print(f"  {i:2d}. {vin}")
    except ValueError as e:
        print(f"  Erreur: {e}")


def demo_random_with_real_prefixes():
    """Démonstration génération aléatoire avec préfixes réels"""
    print_section("3. Génération Aléatoire avec Préfixes Réels")

    factory = ChassisFactory()

    if not factory.prefix_db:
        print("\n⚠️  Base de préfixes non disponible")
        return

    print(f"\n📋 10 VIN aléatoires (fabricants mondiaux):")
    random_vins = factory.create_random(
        "8704",
        quantity=10,
        use_real_prefixes=True
    )

    for i, vin in enumerate(random_vins, 1):
        # Identifier fabricant depuis WMI
        wmi = vin[:3]
        try:
            prefixes = factory.prefix_db.search_by_wmi(wmi)
            if prefixes:
                mfr = prefixes[0].manufacturer or "Inconnu"
                country = prefixes[0].country or "?"
            else:
                mfr = "Inconnu"
                country = "?"
        except:
            mfr = "Inconnu"
            country = "?"

        result = factory.validate(vin)
        checkmark = "✅" if result.checksum_valid else "❌"
        print(f"  {i:2d}. {vin} {checkmark} ({mfr}, {country})")


def demo_country_filter():
    """Démonstration filtrage par pays"""
    print_section("4. Filtrage par Pays")

    factory = ChassisFactory()

    if not factory.prefix_db:
        print("\n⚠️  Base de préfixes non disponible")
        return

    countries = ["USA", "Germany", "Japan"]

    for country in countries:
        print(f"\n📋 5 VIN {country}:")
        try:
            batch = factory.create_vin_batch_from_real_prefixes(
                country=country,
                start_sequence=1,
                quantity=5
            )
            for i, vin in enumerate(batch, 1):
                wmi = vin[:3]
                prefixes = factory.prefix_db.search_by_wmi(wmi)
                mfr = prefixes[0].manufacturer if prefixes else "Inconnu"
                print(f"  {i}. {vin} ({mfr})")
        except ValueError as e:
            print(f"  Erreur: {e}")


def demo_comparison_generic_vs_real():
    """Comparaison mode générique vs préfixes réels"""
    print_section("5. Comparaison: Générique vs Préfixes Réels")

    factory = ChassisFactory()

    print(f"\n📋 Mode GÉNÉRIQUE (sans préfixes réels):")
    generic_vins = factory.create_random("8704", quantity=5, use_real_prefixes=False)
    for i, vin in enumerate(generic_vins, 1):
        wmi = vin[:3]
        print(f"  {i}. {vin} (WMI: {wmi} - Fabricant non authentifié)")

    if factory.prefix_db:
        print(f"\n📋 Mode PRÉFIXES RÉELS (fabricants authentiques):")
        real_vins = factory.create_random("8704", quantity=5, use_real_prefixes=True)
        for i, vin in enumerate(real_vins, 1):
            wmi = vin[:3]
            prefixes = factory.prefix_db.search_by_wmi(wmi)
            mfr = prefixes[0].manufacturer if prefixes else "Inconnu"
            country = prefixes[0].country if prefixes else "?"
            print(f"  {i}. {vin} (WMI: {wmi} - {mfr}, {country})")

        print(f"\n💡 Avantage: VIN avec préfixes réels = fabricants authentiques mondiaux")
    else:
        print(f"\n⚠️  Base de préfixes non disponible pour comparaison")


def main():
    """Fonction principale"""
    print("\n" + "=" * 70)
    print("  BASE DE DONNÉES PRÉFIXES VIN RÉELS".center(70))
    print("  62,000+ Préfixes Constructeurs Mondiaux".center(70))
    print("=" * 70)

    try:
        demo_prefix_database()
        demo_factory_with_real_prefixes()
        demo_random_with_real_prefixes()
        demo_country_filter()
        demo_comparison_generic_vs_real()

        print("\n" + "=" * 70)
        print("  ✅ Démonstration terminée avec succès".center(70))
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
