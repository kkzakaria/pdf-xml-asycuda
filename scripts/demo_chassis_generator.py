#!/usr/bin/env python3
"""
Script de démonstration du service générateur de châssis
=========================================================

Démontre toutes les fonctionnalités du module chassis_generator:
- Génération VIN ISO 3779 avec checksum
- Génération châssis fabricant personnalisés
- Validation universelle
- Continuation de séquences
- Génération aléatoire pour tests
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from chassis_generator import ChassisFactory, ChassisType


def print_section(title: str):
    """Affiche un séparateur de section"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)


def demo_vin_generation():
    """Démo génération VIN ISO 3779"""
    print_section("1. Génération VIN ISO 3779")

    factory = ChassisFactory()

    print("\n📋 VIN unique:")
    vin = factory.create_vin("LZS", "HCKZS", 2028, "S", 4073)
    print(f"  {vin}")

    # Validation
    result = factory.validate(vin)
    print(f"\n  ✓ Validation: {'✅ Valide' if result.is_valid else '❌ Invalide'}")
    print(f"  ✓ Checksum (pos 9): {vin[8]} {'✅' if result.checksum_valid else '❌'}")
    print(f"  ✓ Longueur: {len(vin)} caractères")

    print("\n📋 Lot de 5 VIN consécutifs (Apsonic AP150ZK):")
    batch = factory.create_vin_batch("LZS", "HCKZS", 2028, "S", 4073, 5)
    for i, v in enumerate(batch, 1):
        print(f"  {i}. {v}")


def demo_manufacturer_chassis():
    """Démo génération châssis fabricant"""
    print_section("2. Génération Châssis Fabricant Configurable")

    factory = ChassisFactory()

    print("\n📋 Châssis FCVR-193 (Apsonic 150ZH):")
    print("  Template: {prefix}{seq:07d}")
    chassis = factory.create_chassis(
        "{prefix}{seq:07d}",
        {"prefix": "AP2KC1A6S", "seq": 2588796}
    )
    print(f"  Résultat: {chassis}")

    # Validation
    result = factory.validate(chassis)
    print(f"  ✓ Validation: {'✅ Valide' if result.is_valid else '❌ Invalide'}")
    print(f"  ✓ Longueur: {len(chassis)} caractères")

    print("\n📋 Lot de 10 châssis consécutifs:")
    batch = factory.create_chassis_batch(
        "{prefix}{seq:07d}",
        {"prefix": "AP2KC1A6S"},
        start_sequence=2588796,
        quantity=10
    )
    for i, c in enumerate(batch, 1):
        print(f"  {i:2d}. {c}")


def demo_random_generation():
    """Démo génération aléatoire pour tests"""
    print_section("3. Génération Aléatoire pour Tests")

    factory = ChassisFactory()

    print("\n📋 5 VIN aléatoires (différents fabricants):")
    random_vins = []
    attempts = 0
    while len(random_vins) < 5 and attempts < 20:
        try:
            batch = factory.create_random("8704", quantity=5 - len(random_vins), chassis_type=ChassisType.VIN_ISO3779)
            random_vins.extend(batch)
        except ValueError:
            pass
        attempts += 1

    for i, v in enumerate(random_vins[:5], 1):
        result = factory.validate(v)
        checkmark = "✅" if result.checksum_valid else "❌"
        print(f"  {i}. {v} {checkmark}")

    print("\n📋 3 châssis fabricant aléatoires:")
    random_chassis = factory.create_random("8704", quantity=3, chassis_type=ChassisType.MANUFACTURER)
    for i, c in enumerate(random_chassis, 1):
        print(f"  {i}. {c}")


def demo_sequence_continuation():
    """Démo détection et continuation de séquences"""
    print_section("4. Détection et Continuation de Séquences")

    factory = ChassisFactory()

    # Séquence avec incrément 1
    print("\n📋 Séquence existante (incrément 1):")
    existing1 = ["ABC0100", "ABC0101", "ABC0102"]
    print(f"  Existants: {existing1}")

    continued1, pattern1 = factory.continue_sequence(existing1, 5)
    print(f"  Pattern détecté: {pattern1}")
    print(f"  Suite générée:")
    for i, c in enumerate(continued1, 1):
        print(f"    {i}. {c}")

    # Séquence avec incrément 2
    print("\n📋 Séquence existante (incrément 2):")
    existing2 = ["TEST0100", "TEST0102", "TEST0104"]
    print(f"  Existants: {existing2}")

    continued2, pattern2 = factory.continue_sequence(existing2, 4)
    print(f"  Pattern détecté: {pattern2}")
    print(f"  Suite générée:")
    for i, c in enumerate(continued2, 1):
        print(f"    {i}. {c}")


def demo_validation():
    """Démo validation avec détection automatique"""
    print_section("5. Validation Universelle")

    factory = ChassisFactory()

    test_cases = [
        ("LZSHCKZS2S8054073", "VIN ISO 3779 valide (FCVR-189 réel)"),
        ("AP2KC1A6S2588796", "Châssis fabricant valide (FCVR-193 réel)"),
        ("LZSHCKZS9S8054073", "VIN avec mauvais checksum"),
        ("TOOSHORT", "Châssis trop court"),
        ("LZSHCKZSQS8054073", "VIN avec caractère interdit (Q)"),
    ]

    for chassis, description in test_cases:
        result = factory.validate(chassis)
        status = "✅" if result.is_valid else "❌"

        print(f"\n  {status} {description}")
        print(f"     Châssis: {chassis}")
        print(f"     Type: {result.chassis_type.value if result.chassis_type else 'inconnu'}")

        if not result.is_valid:
            print(f"     Erreurs: {', '.join(result.errors)}")
        elif result.checksum_valid is not None:
            print(f"     Checksum: {'✅ Valide' if result.checksum_valid else '❌ Invalide'}")


def demo_real_world_scenarios():
    """Démo scénarios réels RFCV"""
    print_section("6. Reproduction Patterns RFCV Réels")

    factory = ChassisFactory()

    # FCVR-189: 180 tricycles Apsonic AP150ZK
    print("\n📋 FCVR-189: Tricycles Apsonic AP150ZK")
    print("  Pattern observé: LZSHCKZS[C]S805407[3-252]")
    print("  Reproduction des 5 premiers:")
    fcvr189_batch = factory.create_vin_batch("LZS", "HCKZS", 2028, "S", 4073, 5)
    for i, v in enumerate(fcvr189_batch, 1):
        print(f"    {i}. {v}")

    # FCVR-193: 15 tricycles Apsonic 150ZH
    print("\n📋 FCVR-193: Tricycles Apsonic 150ZH")
    print("  Pattern observé: AP2KC1A6S258879[6-810]")
    print("  Reproduction des 5 premiers:")
    fcvr193_batch = factory.create_chassis_batch(
        "{prefix}{seq:07d}",
        {"prefix": "AP2KC1A6S"},
        start_sequence=2588796,
        quantity=5
    )
    for i, c in enumerate(fcvr193_batch, 1):
        print(f"    {i}. {c}")


def demo_multiple_manufacturers():
    """Démo génération pour différents fabricants"""
    print_section("7. Support Multi-Fabricants")

    factory = ChassisFactory()

    manufacturers = [
        ("LZS", "HCKZS", "Apsonic (Chine)"),
        ("LFV", "BA01A", "Lifan (Chine)"),
        ("LBV", "GW02B", "Haojue (Chine)"),
        ("LGX", "ZA02C", "Zongshen (Chine)"),
    ]

    print("\n📋 VIN pour différents fabricants chinois:")
    for wmi, vds, name in manufacturers:
        vin = factory.create_vin(wmi, vds, 2025, "S", 1)
        result = factory.validate(vin)
        checkmark = "✅" if result.checksum_valid else "❌"
        print(f"  {name:20s} → {vin} {checkmark}")


def main():
    """Fonction principale"""
    print("\n" + "=" * 70)
    print("  SERVICE GÉNÉRATEUR DE CHÂSSIS UNIVERSEL".center(70))
    print("  Démonstration Complète".center(70))
    print("=" * 70)

    try:
        demo_vin_generation()
        demo_manufacturer_chassis()
        demo_random_generation()
        demo_sequence_continuation()
        demo_validation()
        demo_real_world_scenarios()
        demo_multiple_manufacturers()

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
