#!/usr/bin/env python3
"""
Script de démonstration de la génération unique de châssis
===========================================================

Démontre les capacités du ChassisSequenceManager pour garantir
qu'aucun numéro de châssis ne soit généré deux fois.

Usage:
    python3 scripts/demo_unique_generation.py
"""

import sys
from pathlib import Path

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chassis_generator import ChassisFactory, ChassisValidator
from chassis_sequence_manager import ChassisSequenceManager


def demo_basic_uniqueness():
    """Démonstration basique de l'unicité"""
    print("=" * 70)
    print("  1. Démonstration Basique - Unicité Garantie".center(70))
    print("=" * 70)

    factory = ChassisFactory(ensure_unique=True)

    print("\n🔧 Génération de 10 VIN Apsonic (même préfixe)")
    print("-" * 70)

    vins = []
    for i in range(10):
        vin = factory.create_unique_vin("LZS", "HCKZS", 2028, "S")
        vins.append(vin)
        print(f"  {i+1:2d}. {vin}")

    # Vérifier unicité
    unique_count = len(set(vins))
    print(f"\n✅ Unicité vérifiée: {unique_count}/10 VIN uniques")
    print(f"📊 Séquences: {vins[0][-6:]} → {vins[-1][-6:]}")


def demo_persistence():
    """Démonstration de la persistance entre sessions"""
    print("\n" + "=" * 70)
    print("  2. Démonstration Persistance - Reprise de Séquence".center(70))
    print("=" * 70)

    print("\n📝 Session 1: Génération de 5 VIN")
    print("-" * 70)

    # Session 1
    factory1 = ChassisFactory(
        ensure_unique=True,
        sequence_storage_path="data/demo_sequences.json"
    )

    vins_session1 = []
    for i in range(5):
        vin = factory1.create_unique_vin("LZS", "HCKZS", 2028, "S")
        vins_session1.append(vin)
        print(f"  Session 1.{i+1}: {vin}")

    last_seq_session1 = int(vins_session1[-1][-6:])
    print(f"  Dernière séquence session 1: {last_seq_session1}")

    # Session 2 (nouveau factory)
    print("\n📝 Session 2: Nouvelle instance ChassisFactory (redémarrage simulé)")
    print("-" * 70)

    factory2 = ChassisFactory(
        ensure_unique=True,
        sequence_storage_path="data/demo_sequences.json"
    )

    vins_session2 = []
    for i in range(5):
        vin = factory2.create_unique_vin("LZS", "HCKZS", 2028, "S")
        vins_session2.append(vin)
        print(f"  Session 2.{i+1}: {vin}")

    first_seq_session2 = int(vins_session2[0][-6:])
    print(f"  Première séquence session 2: {first_seq_session2}")

    # Vérification
    if first_seq_session2 == last_seq_session1 + 1:
        print(f"\n✅ Persistance vérifiée: séquence reprise correctement")
        print(f"   {last_seq_session1} (session 1) → {first_seq_session2} (session 2)")
    else:
        print(f"\n❌ Erreur: séquence non continue")


def demo_multiple_prefixes():
    """Démonstration avec plusieurs préfixes simultanés"""
    print("\n" + "=" * 70)
    print("  3. Démonstration Multi-Préfixes - Séquences Indépendantes".center(70))
    print("=" * 70)

    factory = ChassisFactory(ensure_unique=True)

    print("\n🚗 Génération simultanée pour 3 fabricants différents")
    print("-" * 70)

    # Apsonic
    print("\n📋 Apsonic (LZS):")
    apsonic_vins = factory.create_unique_vin_batch("LZS", "HCKZS", 2028, "S", 3)
    for i, vin in enumerate(apsonic_vins, 1):
        print(f"  {i}. {vin}")

    # Lifan
    print("\n📋 Lifan (LFV):")
    lifan_vins = factory.create_unique_vin_batch("LFV", "BA01A", 2025, "S", 3)
    for i, vin in enumerate(lifan_vins, 1):
        print(f"  {i}. {vin}")

    # Haojue
    print("\n📋 Haojue/Suzuki (LBV):")
    haojue_vins = factory.create_unique_vin_batch("LBV", "GW02B", 2027, "S", 3)
    for i, vin in enumerate(haojue_vins, 1):
        print(f"  {i}. {vin}")

    print("\n✅ 3 séquences indépendantes maintenues simultanément")


def demo_real_prefixes():
    """Démonstration avec préfixes réels de la base de données"""
    print("\n" + "=" * 70)
    print("  4. Démonstration Préfixes Réels - Authenticité + Unicité".center(70))
    print("=" * 70)

    factory = ChassisFactory(ensure_unique=True, use_real_prefixes=True)

    if factory.prefix_db is None:
        print("\n⚠️  Base de préfixes réels non disponible")
        return

    print("\n🌏 Génération VIN chinois avec préfixes authentiques")
    print("-" * 70)

    chinese_vins = []
    for i in range(5):
        vin = factory.create_unique_vin_from_real_prefix(country="China")
        chinese_vins.append(vin)

        # Valider
        result = factory.validate(vin)
        status = "✅" if result.is_valid else "❌"
        print(f"  {i+1}. {vin} {status}")

    print(f"\n✅ 5 VIN chinois authentiques et uniques générés")


def demo_statistics():
    """Démonstration des statistiques de génération"""
    print("\n" + "=" * 70)
    print("  5. Démonstration Statistiques - Suivi de Génération".center(70))
    print("=" * 70)

    factory = ChassisFactory(ensure_unique=True)

    print("\n📊 Génération de VIN pour plusieurs fabricants")
    print("-" * 70)

    # Apsonic - 50 VIN
    print("  Génération 50 VIN Apsonic...")
    factory.create_unique_vin_batch("LZS", "HCKZS", 2028, "S", 50)

    # Lifan - 30 VIN
    print("  Génération 30 VIN Lifan...")
    factory.create_unique_vin_batch("LFV", "BA01A", 2025, "S", 30)

    # Haojue - 20 VIN
    print("  Génération 20 VIN Haojue...")
    factory.create_unique_vin_batch("LBV", "GW02B", 2027, "S", 20)

    # Statistiques
    stats = factory.get_sequence_statistics()

    print(f"\n📈 Statistiques de génération:")
    print("-" * 70)
    print(f"  Préfixes enregistrés: {stats['total_prefixes']}")
    print(f"  VIN générés au total: {stats['total_vins_generated']}")
    print(f"  Séquence maximale: {stats['max_sequence']}")
    print(f"  Séquence moyenne: {stats['average_sequence']}")


def demo_validation():
    """Démonstration validation et conformité"""
    print("\n" + "=" * 70)
    print("  6. Démonstration Validation - Conformité ISO 3779".center(70))
    print("=" * 70)

    factory = ChassisFactory(ensure_unique=True)
    validator = ChassisValidator()

    print("\n🔍 Génération et validation de 10 VIN")
    print("-" * 70)

    vins = factory.create_unique_vin_batch("LZS", "HCKZS", 2028, "S", 10)

    valid_count = 0
    for i, vin in enumerate(vins, 1):
        result = validator.validate_vin(vin)
        status = "✅" if result.is_valid else "❌"
        checksum = "✓" if result.checksum_valid else "✗"

        print(f"  {i:2d}. {vin} {status} (checksum: {checksum})")

        if result.is_valid:
            valid_count += 1

    print(f"\n✅ Validation: {valid_count}/10 VIN conformes ISO 3779")


def main():
    """Point d'entrée principal"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + "  Démonstration Génération Unique de Châssis".center(68) + "║")
    print("║" + "  ChassisSequenceManager + ChassisFactory".center(68) + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        demo_basic_uniqueness()
        demo_persistence()
        demo_multiple_prefixes()
        demo_real_prefixes()
        demo_statistics()
        demo_validation()

        print("\n" + "=" * 70)
        print("  ✅ Démonstration Complète Terminée".center(70))
        print("=" * 70)

        print("\n📁 Fichier de persistance: data/chassis_sequences.json")
        print("📁 Fichier demo: data/demo_sequences.json")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
