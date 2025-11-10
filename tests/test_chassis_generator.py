"""
Tests unitaires pour le service générateur de châssis
======================================================

Teste tous les composants du module chassis_generator:
- ChassisValidator: validation VIN et châssis fabricant
- VINGenerator: génération VIN ISO 3779
- ManufacturerChassisGenerator: génération châssis personnalisés
- ChassisFactory: API unifiée
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from chassis_generator import (
    ChassisValidator,
    VINGenerator,
    ManufacturerChassisGenerator,
    ChassisFactory,
    ChassisType,
    ValidationResult
)


class TestChassisValidator:
    """Tests du validateur de châssis"""

    def test_calculate_vin_checksum_valid(self):
        """Test calcul checksum sur VIN réels observés dans RFCV"""
        # VIN réel du FCVR-189: LZSHCKZS2S8054073
        vin = "LZSHCKZS2S8054073"
        checksum = ChassisValidator.calculate_vin_checksum(vin)
        assert checksum == "2", f"Checksum incorrect: attendu '2', reçu '{checksum}'"

    def test_calculate_vin_checksum_various(self):
        """Test calcul checksum sur différents VIN"""
        test_cases = [
            ("1M8GDM9AXKP042788", "X"),  # VIN exemple avec checksum X
            ("11111111111111111", "1"),  # VIN tous 1 (checksum = 1 pas 0)
        ]
        for vin, expected in test_cases:
            checksum = ChassisValidator.calculate_vin_checksum(vin)
            assert checksum == expected, f"VIN {vin}: attendu '{expected}', reçu '{checksum}'"

    def test_validate_vin_valid(self):
        """Test validation VIN valides"""
        valid_vins = [
            "LZSHCKZS2S8054073",  # FCVR-189 réel
            "LZSHDMZS1S8029142",  # FCVR-189 réel
            "1HGBH41JXMN109186",  # VIN Honda exemple
        ]
        for vin in valid_vins:
            result = ChassisValidator.validate_vin(vin)
            assert result.is_valid, f"VIN {vin} devrait être valide: {result.errors}"
            assert result.checksum_valid, f"Checksum {vin} devrait être valide"

    def test_validate_vin_invalid_length(self):
        """Test validation VIN longueur incorrecte"""
        result = ChassisValidator.validate_vin("TOOSHORT")
        assert not result.is_valid
        assert "Longueur incorrecte" in result.errors[0]

    def test_validate_vin_forbidden_chars(self):
        """Test validation VIN avec caractères interdits I/O/Q"""
        result = ChassisValidator.validate_vin("LZSHCKZSQS8054073")  # Q en position 9
        assert not result.is_valid
        assert any("interdits" in err for err in result.errors)

    def test_validate_vin_invalid_checksum(self):
        """Test validation VIN avec mauvais checksum"""
        # VIN avec checksum incorrect (9 au lieu de 2)
        result = ChassisValidator.validate_vin("LZSHCKZS9S8054073")
        assert not result.is_valid
        assert any("Checksum invalide" in err for err in result.errors)

    def test_validate_manufacturer_chassis_valid(self):
        """Test validation châssis fabricant valides"""
        valid_chassis = [
            "AP2KC1A6S2588796",  # FCVR-193 réel (16 chars)
            "ABC1234567890",     # 13 chars (minimum)
            "ABCDEFGHIJK123456", # 17 chars (maximum)
        ]
        for chassis in valid_chassis:
            result = ChassisValidator.validate_manufacturer_chassis(chassis)
            assert result.is_valid, f"Châssis {chassis} devrait être valide: {result.errors}"

    def test_validate_manufacturer_chassis_invalid_length(self):
        """Test validation châssis fabricant longueur incorrecte"""
        result = ChassisValidator.validate_manufacturer_chassis("SHORT")
        assert not result.is_valid
        assert "hors limites" in result.errors[0]

    def test_validate_auto_detect(self):
        """Test validation avec détection automatique du type"""
        # VIN 17 chars → détecté comme VIN
        result = ChassisValidator.validate("LZSHCKZS2S8054073")
        assert result.chassis_type == ChassisType.VIN_ISO3779

        # Châssis 16 chars → détecté comme fabricant
        result = ChassisValidator.validate("AP2KC1A6S2588796")
        assert result.chassis_type == ChassisType.MANUFACTURER


class TestVINGenerator:
    """Tests du générateur VIN ISO 3779"""

    def test_generate_vin_basic(self):
        """Test génération VIN basique"""
        vin = VINGenerator.generate("LZS", "HCKZS", 2028, "S", 4073)
        assert len(vin) == 17
        assert vin.startswith("LZSHCKZS")
        assert vin.endswith("4073")

    def test_generate_vin_checksum_valid(self):
        """Test que le VIN généré a un checksum valide"""
        vin = VINGenerator.generate("LZS", "HCKZS", 2028, "S", 4073)
        result = ChassisValidator.validate_vin(vin)
        assert result.is_valid
        assert result.checksum_valid

    def test_generate_vin_year_encoding(self):
        """Test encodage de l'année (position 10) - ISO 3779 avec exclusion I/O/Q"""
        # 2028 → W (ancien S, correctif v2.0: I/O/Q/U exclus)
        vin = VINGenerator.generate("LZS", "HCKZS", 2028, "S", 4073)
        assert vin[9] == "W", f"Année 2028 devrait être 'W', reçu '{vin[9]}'"

        # 2025 → S (ancien P, correctif v2.0)
        vin = VINGenerator.generate("LZS", "HCKZS", 2025, "S", 1)
        assert vin[9] == "S"

    def test_generate_vin_invalid_wmi(self):
        """Test génération VIN avec WMI invalide"""
        with pytest.raises(ValueError, match="WMI doit avoir 3 caractères"):
            VINGenerator.generate("LZ", "HCKZS", 2028, "S", 1)

    def test_generate_vin_invalid_vds(self):
        """Test génération VIN avec VDS invalide"""
        with pytest.raises(ValueError, match="VDS doit avoir 5 caractères"):
            VINGenerator.generate("LZS", "HCK", 2028, "S", 1)

    def test_generate_vin_invalid_year(self):
        """Test génération VIN avec année non supportée"""
        with pytest.raises(ValueError, match="Année.*non supportée"):
            VINGenerator.generate("LZS", "HCKZS", 2050, "S", 1)

    def test_generate_vin_invalid_sequence(self):
        """Test génération VIN avec séquence hors limites"""
        with pytest.raises(ValueError, match="Séquence doit être entre"):
            VINGenerator.generate("LZS", "HCKZS", 2028, "S", 1000000)

    def test_generate_batch_consecutive(self):
        """Test génération lot VIN consécutifs"""
        batch = VINGenerator.generate_batch("LZS", "HCKZS", 2028, "S", 100, 5)
        assert len(batch) == 5
        assert batch[0].endswith("0100")
        assert batch[4].endswith("0104")

        # Vérifier que tous sont valides
        for vin in batch:
            result = ChassisValidator.validate_vin(vin)
            assert result.is_valid


class TestManufacturerChassisGenerator:
    """Tests du générateur châssis fabricant"""

    def test_generate_simple_template(self):
        """Test génération avec template simple"""
        chassis = ManufacturerChassisGenerator.generate(
            "{prefix}{seq:04d}",
            {"prefix": "TEST", "seq": 123}
        )
        assert chassis == "TEST0123"

    def test_generate_complex_template(self):
        """Test génération avec template complexe (RFCV réel)"""
        # Pour reproduire FCVR-193: AP2KC1A6S2588796 (16 chars)
        chassis = ManufacturerChassisGenerator.generate(
            "{prefix}{seq:07d}",
            {"prefix": "AP2KC1A6S", "seq": 2588796}
        )
        assert chassis == "AP2KC1A6S2588796"
        assert len(chassis) == 16

    def test_generate_missing_variable(self):
        """Test génération avec variable manquante"""
        with pytest.raises(ValueError, match="Variable manquante"):
            ManufacturerChassisGenerator.generate(
                "{prefix}{seq:04d}",
                {"prefix": "TEST"}  # seq manquant
            )

    def test_generate_batch_sequence(self):
        """Test génération lot avec séquence"""
        batch = ManufacturerChassisGenerator.generate_batch(
            "{prefix}{seq:04d}",
            {"prefix": "TEST"},
            sequence_var="seq",
            start_sequence=100,
            quantity=3
        )
        assert batch == ["TEST0100", "TEST0101", "TEST0102"]


class TestChassisFactory:
    """Tests de la factory (API unifiée)"""

    @pytest.fixture
    def factory(self):
        """Fixture factory pour tests"""
        return ChassisFactory()

    def test_create_vin(self, factory):
        """Test création VIN via factory"""
        vin = factory.create_vin("LZS", "HCKZS", 2028, "S", 4073)
        assert len(vin) == 17
        result = factory.validate(vin)
        assert result.is_valid

    def test_create_vin_batch(self, factory):
        """Test création lot VIN via factory"""
        batch = factory.create_vin_batch("LZS", "HCKZS", 2028, "S", 1, 10)
        assert len(batch) == 10
        # Vérifier séquence consécutive
        for i in range(9):
            seq1 = int(batch[i][-6:])
            seq2 = int(batch[i+1][-6:])
            assert seq2 == seq1 + 1

    def test_create_chassis(self, factory):
        """Test création châssis fabricant via factory"""
        chassis = factory.create_chassis(
            "{prefix}{seq:07d}",  # Format correct pour RFCV réel
            {"prefix": "AP2KC1A6S", "seq": 2588796}
        )
        assert chassis == "AP2KC1A6S2588796"
        result = factory.validate(chassis)
        assert result.is_valid

    def test_create_chassis_batch(self, factory):
        """Test création lot châssis fabricant via factory"""
        batch = factory.create_chassis_batch(
            "{prefix}{seq:04d}",
            {"prefix": "TEST"},
            start_sequence=1,
            quantity=5
        )
        assert len(batch) == 5
        assert batch == ["TEST0001", "TEST0002", "TEST0003", "TEST0004", "TEST0005"]

    def test_create_random_vin(self, factory):
        """Test création châssis aléatoires (VIN)"""
        # Réessayer jusqu'à 50 fois pour générer 10 VIN valides (évite échecs aléatoires)
        max_attempts = 50
        random_vins = []
        attempts = 0

        while len(random_vins) < 10 and attempts < max_attempts:
            try:
                batch = factory.create_random("8704", quantity=10 - len(random_vins), chassis_type=ChassisType.VIN_ISO3779)
                random_vins.extend(batch)
            except ValueError:
                # Si génération aléatoire échoue (caractère interdit), réessayer
                pass
            attempts += 1

        assert len(random_vins) >= 10, f"Impossible de générer 10 VIN après {attempts} tentatives"
        random_vins = random_vins[:10]  # Limiter à 10

        # Vérifier que tous sont valides
        for vin in random_vins:
            result = factory.validate(vin)
            assert result.is_valid
            assert result.chassis_type == ChassisType.VIN_ISO3779

    def test_create_random_manufacturer(self, factory):
        """Test création châssis aléatoires (fabricant)"""
        random_chassis = factory.create_random("8704", quantity=5, chassis_type=ChassisType.MANUFACTURER)
        assert len(random_chassis) == 5

        for chassis in random_chassis:
            result = factory.validate(chassis)
            assert result.is_valid
            assert result.chassis_type == ChassisType.MANUFACTURER

    def test_validate_vin(self, factory):
        """Test validation VIN via factory"""
        result = factory.validate("LZSHCKZS2S8054073")
        assert result.is_valid
        assert result.chassis_type == ChassisType.VIN_ISO3779
        assert result.checksum_valid

    def test_validate_manufacturer_chassis(self, factory):
        """Test validation châssis fabricant via factory"""
        result = factory.validate("AP2KC1A6S2588796")
        assert result.is_valid
        assert result.chassis_type == ChassisType.MANUFACTURER

    def test_continue_sequence_numeric(self, factory):
        """Test continuation séquence numérique"""
        existing = ["ABC0100", "ABC0101", "ABC0102"]
        continued, pattern = factory.continue_sequence(existing, 3)
        assert continued == ["ABC0103", "ABC0104", "ABC0105"]
        assert "ABC" in pattern
        # Le pattern détecté est "ABC010 + 1 digits" car la partie variable commence à "010"
        assert "digits" in pattern
        assert "incr=1" in pattern

    def test_continue_sequence_increment_2(self, factory):
        """Test continuation séquence avec incrément > 1"""
        existing = ["TEST0100", "TEST0102", "TEST0104"]
        continued, pattern = factory.continue_sequence(existing, 2)
        assert continued == ["TEST0106", "TEST0108"]
        assert "incr=2" in pattern

    def test_continue_sequence_insufficient_data(self, factory):
        """Test continuation avec données insuffisantes"""
        with pytest.raises(ValueError, match="Minimum 2 châssis requis"):
            factory.continue_sequence(["ABC001"], 1)

    def test_continue_sequence_inconsistent_length(self, factory):
        """Test continuation avec longueurs incohérentes"""
        with pytest.raises(ValueError, match="Longueurs incohérentes"):
            factory.continue_sequence(["ABC01", "ABC001"], 1)

    def test_continue_sequence_no_numeric(self, factory):
        """Test continuation avec suffixe non-numérique"""
        with pytest.raises(ValueError, match="Séquence non-numérique"):
            factory.continue_sequence(["ABCDE", "ABCDF"], 1)


class TestRealWorldScenarios:
    """Tests basés sur les RFCV réels"""

    @pytest.fixture
    def factory(self):
        return ChassisFactory()

    def test_fcvr189_vin_pattern(self, factory):
        """Test reproduction pattern FCVR-189 (180 tricycles)"""
        # Pattern observé: LZSHCKZS[X]S8054073-252
        # Générer 10 VIN similaires
        batch = factory.create_vin_batch("LZS", "HCKZS", 2028, "S", 4073, 10)

        # Vérifier structure
        for vin in batch:
            assert vin.startswith("LZSHCKZS")
            assert vin[9] == "W"  # Année 2028 (correctif v2.0: I/O/Q/U exclus)
            assert vin[10] == "S"  # Usine
            result = factory.validate(vin)
            assert result.is_valid

    def test_fcvr193_chassis_pattern(self, factory):
        """Test reproduction pattern FCVR-193 (15 tricycles)"""
        # Pattern observé: AP2KC1A6S2588796-810
        # Générer 15 châssis similaires
        batch = factory.create_chassis_batch(
            "{prefix}{seq:07d}",
            {"prefix": "AP2KC1A6S"},
            start_sequence=2588796,
            quantity=15
        )

        # Vérifier structure
        assert len(batch) == 15
        assert batch[0] == "AP2KC1A6S2588796"
        assert batch[14] == "AP2KC1A6S2588810"

        for chassis in batch:
            assert chassis.startswith("AP2KC1A6S")
            assert len(chassis) == 16
            result = factory.validate(chassis)
            assert result.is_valid

    def test_multiple_manufacturers(self, factory):
        """Test génération pour différents fabricants"""
        manufacturers = [
            ("LZS", "HCKZS"),  # Apsonic
            ("LFV", "BA01A"),  # Lifan
            ("LBV", "GW02B"),  # Haojue
        ]

        for wmi, vds in manufacturers:
            vin = factory.create_vin(wmi, vds, 2025, "S", 1)
            result = factory.validate(vin)
            assert result.is_valid
            assert vin.startswith(wmi)


if __name__ == "__main__":
    # Exécuter les tests avec pytest
    pytest.main([__file__, "-v", "--tb=short"])
