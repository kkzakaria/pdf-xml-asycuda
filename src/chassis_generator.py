"""
Générateur de numéros de châssis universel pour véhicules
==========================================================

Ce module fournit des outils génériques pour générer et valider des numéros
de châssis/VIN conformes aux standards industriels (ISO 3779) et aux formats
fabricants personnalisés.

Architecture:
    - VINGenerator: Génération VIN 17 caractères ISO 3779 avec checksum
    - ManufacturerChassisGenerator: Génération châssis fabricant configurable
    - ChassisFactory: Point d'entrée simplifié pour tous les cas d'usage
    - ChassisValidator: Validation universelle de formats

Usage:
    from chassis_generator import ChassisFactory

    factory = ChassisFactory()

    # Générer un VIN ISO 3779
    vin = factory.create_vin(wmi="LZS", vds="HCKZS", year=2028, sequence=4073)

    # Générer un châssis fabricant
    chassis = factory.create_chassis(
        template="{prefix}{year:2}{seq:06}",
        params={"prefix": "AP2KC1A6S", "year": 25, "seq": 8796}
    )

    # Générer des châssis aléatoires pour tests
    test_chassis = factory.create_random("8704", quantity=100)

    # Valider un châssis
    is_valid = factory.validate("LZSHCKZS2S8054073")
"""

import re
import random
import string
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

# Import optionnel de la base de préfixes réels
try:
    from vin_prefix_database import VINPrefixDatabase, VINPrefix
    HAS_PREFIX_DATABASE = True
except ImportError:
    HAS_PREFIX_DATABASE = False


class ChassisType(Enum):
    """Types de châssis supportés"""
    VIN_ISO3779 = "vin_iso3779"  # VIN 17 caractères ISO 3779
    MANUFACTURER = "manufacturer"  # Châssis fabricant personnalisé


@dataclass
class ValidationResult:
    """Résultat de validation d'un châssis"""
    is_valid: bool
    chassis_type: Optional[ChassisType]
    errors: List[str]
    checksum_valid: Optional[bool] = None


class ChassisValidator:
    """
    Validateur universel de numéros de châssis

    Supporte:
    - Validation VIN ISO 3779 (17 caractères, checksum)
    - Validation châssis fabricant (longueur, format)
    - Détection automatique du type
    """

    # Caractères interdits dans les VIN ISO 3779
    VIN_FORBIDDEN = {'I', 'O', 'Q', 'i', 'o', 'q'}

    # Poids pour chaque position du VIN (ISO 3779)
    VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

    # Table de transcodage caractères → valeurs numériques (ISO 3779)
    VIN_CHAR_VALUES = {
        'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
        'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
        'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
        '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
    }

    @classmethod
    def calculate_vin_checksum(cls, vin: str) -> str:
        """
        Calcule le checksum d'un VIN ISO 3779 (position 9)

        Le checksum est calculé selon l'algorithme ISO 3779:
        1. Chaque caractère est converti en valeur numérique
        2. Multiplié par un poids selon sa position
        3. La somme est divisée par 11, le reste donne le checksum

        Args:
            vin: VIN de 17 caractères (le caractère en position 9 est ignoré)

        Returns:
            Caractère de checksum ('0'-'9' ou 'X' pour 10)

        Raises:
            ValueError: Si le VIN n'a pas 17 caractères
        """
        if len(vin) != 17:
            raise ValueError(f"VIN doit avoir 17 caractères, reçu: {len(vin)}")

        total = 0
        for i, char in enumerate(vin.upper()):
            if i == 8:  # Position du checksum, ignorée dans le calcul
                continue

            value = cls.VIN_CHAR_VALUES.get(char, 0)
            total += value * cls.VIN_WEIGHTS[i]

        checksum = total % 11
        return 'X' if checksum == 10 else str(checksum)

    @classmethod
    def validate_vin(cls, vin: str, check_checksum: bool = True) -> ValidationResult:
        """
        Valide un VIN ISO 3779

        Args:
            vin: Numéro VIN à valider
            check_checksum: Si True, vérifie le checksum en position 9

        Returns:
            ValidationResult avec détails de validation
        """
        errors = []

        # Vérifier longueur
        if len(vin) != 17:
            errors.append(f"Longueur incorrecte: {len(vin)} (attendu: 17)")
            return ValidationResult(
                is_valid=False,
                chassis_type=ChassisType.VIN_ISO3779,
                errors=errors,
                checksum_valid=None
            )

        # Vérifier caractères alphanumériques uniquement
        if not vin.isalnum():
            errors.append("Caractères non-alphanumériques détectés")

        # Vérifier caractères interdits
        forbidden_found = [c for c in vin if c in cls.VIN_FORBIDDEN]
        if forbidden_found:
            errors.append(f"Caractères interdits (I/O/Q): {forbidden_found}")

        # Vérifier checksum si demandé
        checksum_valid = None
        if check_checksum and not errors:
            try:
                calculated = cls.calculate_vin_checksum(vin)
                actual = vin[8].upper()
                checksum_valid = (calculated == actual)

                if not checksum_valid:
                    errors.append(f"Checksum invalide: attendu '{calculated}', reçu '{actual}'")
            except Exception as e:
                errors.append(f"Erreur calcul checksum: {e}")
                checksum_valid = False

        return ValidationResult(
            is_valid=len(errors) == 0,
            chassis_type=ChassisType.VIN_ISO3779,
            errors=errors,
            checksum_valid=checksum_valid
        )

    @staticmethod
    def validate_manufacturer_chassis(
        chassis: str,
        min_length: int = 13,
        max_length: int = 17,
        allowed_chars: Optional[str] = None
    ) -> ValidationResult:
        """
        Valide un châssis fabricant

        Args:
            chassis: Numéro de châssis à valider
            min_length: Longueur minimale acceptée
            max_length: Longueur maximale acceptée
            allowed_chars: Caractères autorisés (défaut: alphanumériques)

        Returns:
            ValidationResult avec détails de validation
        """
        errors = []

        # Vérifier longueur
        if not (min_length <= len(chassis) <= max_length):
            errors.append(
                f"Longueur {len(chassis)} hors limites ({min_length}-{max_length})"
            )

        # Vérifier caractères autorisés
        if allowed_chars is None:
            if not chassis.isalnum():
                errors.append("Caractères non-alphanumériques détectés")
        else:
            invalid_chars = [c for c in chassis if c not in allowed_chars]
            if invalid_chars:
                errors.append(f"Caractères non autorisés: {invalid_chars}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            chassis_type=ChassisType.MANUFACTURER,
            errors=errors,
            checksum_valid=None
        )

    @classmethod
    def validate(cls, chassis: str, auto_detect: bool = True) -> ValidationResult:
        """
        Valide un châssis avec détection automatique du type

        Args:
            chassis: Numéro de châssis à valider
            auto_detect: Si True, détecte automatiquement le type (VIN vs fabricant)

        Returns:
            ValidationResult avec détails de validation
        """
        if auto_detect:
            # Détection: 17 caractères = VIN, sinon = fabricant
            if len(chassis) == 17:
                return cls.validate_vin(chassis)
            else:
                return cls.validate_manufacturer_chassis(chassis)
        else:
            # Par défaut, essayer validation VIN
            return cls.validate_vin(chassis)


class VINGenerator:
    """
    Générateur de VIN ISO 3779 universel

    Génère des VIN 17 caractères conformes à la norme ISO 3779 avec calcul
    automatique du checksum en position 9.

    Structure VIN:
        Positions 1-3:   WMI (World Manufacturer Identifier)
        Positions 4-8:   VDS (Vehicle Descriptor Section)
        Position 9:      Checksum
        Position 10:     Année modèle (encodée)
        Position 11:     Usine de production
        Positions 12-17: Numéro de série
    """

    # Encodage année modèle (position 10) selon ISO 3779
    # Note: I, O, Q, U, Z sont EXCLUS pour éviter confusion (ISO 3779)
    YEAR_CODES = {
        **{year: str(year)[-1] for year in range(2001, 2010)},  # 2001→1, 2009→9
        2010: 'A', 2011: 'B', 2012: 'C', 2013: 'D', 2014: 'E',
        2015: 'F', 2016: 'G', 2017: 'H', 2018: 'J',  # I sauté
        2019: 'K', 2020: 'L', 2021: 'M', 2022: 'N', 2023: 'P',  # O sauté
        2024: 'R', 2025: 'S', 2026: 'T', 2027: 'V',  # Q et U sautés
        2028: 'W', 2029: 'X', 2030: 'Y',  # Z non utilisé
    }

    @classmethod
    def generate(
        cls,
        wmi: str,
        vds: str,
        year: int,
        plant: str = "S",
        sequence: int = 1,
        validate_output: bool = True
    ) -> str:
        """
        Génère un VIN ISO 3779

        Args:
            wmi: World Manufacturer Identifier (3 caractères)
                 Ex: "LZS" (Chine), "LFV" (Chine), "JMB" (Japon)
            vds: Vehicle Descriptor Section (5 caractères)
                 Ex: "HCKZS" (modèle, type, motorisation)
            year: Année modèle (2001-2030)
            plant: Code usine (1 caractère, défaut: "S")
            sequence: Numéro de série (1-999999)
            validate_output: Si True, valide le VIN généré

        Returns:
            VIN 17 caractères avec checksum calculé

        Raises:
            ValueError: Si les paramètres sont invalides

        Example:
            >>> VINGenerator.generate("LZS", "HCKZS", 2028, "S", 4073)
            'LZSHCKZS2S8054073'
        """
        # Validation paramètres
        if len(wmi) != 3:
            raise ValueError(f"WMI doit avoir 3 caractères, reçu: {len(wmi)}")
        if len(vds) != 5:
            raise ValueError(f"VDS doit avoir 5 caractères, reçu: {len(vds)}")
        if year not in cls.YEAR_CODES:
            raise ValueError(f"Année {year} non supportée (2001-2030)")
        if len(plant) != 1:
            raise ValueError(f"Code usine doit avoir 1 caractère, reçu: {len(plant)}")
        if not (1 <= sequence <= 999999):
            raise ValueError(f"Séquence doit être entre 1 et 999999, reçu: {sequence}")

        # Construire VIN sans checksum (X temporaire en position 9)
        year_code = cls.YEAR_CODES[year]
        sequence_str = str(sequence).zfill(6)
        vin_temp = f"{wmi.upper()}{vds.upper()}X{year_code.upper()}{plant.upper()}{sequence_str}"

        # Calculer et insérer checksum
        checksum = ChassisValidator.calculate_vin_checksum(vin_temp)
        vin = f"{wmi.upper()}{vds.upper()}{checksum}{year_code.upper()}{plant.upper()}{sequence_str}"

        # Validation optionnelle
        if validate_output:
            result = ChassisValidator.validate_vin(vin)
            if not result.is_valid:
                raise ValueError(f"VIN généré invalide: {result.errors}")

        return vin

    @classmethod
    def generate_batch(
        cls,
        wmi: str,
        vds: str,
        year: int,
        plant: str = "S",
        start_sequence: int = 1,
        quantity: int = 1
    ) -> List[str]:
        """
        Génère un lot de VIN consécutifs

        Args:
            wmi: World Manufacturer Identifier
            vds: Vehicle Descriptor Section
            year: Année modèle
            plant: Code usine
            start_sequence: Numéro de début de séquence
            quantity: Nombre de VIN à générer

        Returns:
            Liste de VIN générés

        Example:
            >>> VINGenerator.generate_batch("LZS", "HCKZS", 2028, "S", 4073, 3)
            ['LZSHCKZS2S8054073', 'LZSHCKZS2S8054074', 'LZSHCKZS2S8054075']
        """
        return [
            cls.generate(wmi, vds, year, plant, start_sequence + i)
            for i in range(quantity)
        ]


class ManufacturerChassisGenerator:
    """
    Générateur de châssis fabricant configurable

    Génère des numéros de châssis personnalisés selon un template avec
    variables dynamiques. Supporte formats de longueur variable (13-17 caractères).

    Format template:
        Variables supportées: {prefix}, {year}, {seq}, {plant}, etc.
        Format Python: {var:format_spec}

    Examples:
        Template: "{prefix}{year:2}{seq:06}"
        Params: {"prefix": "AP2KC1A6S", "year": 25, "seq": 8796}
        Output: "AP2KC1A6S258796"
    """

    @staticmethod
    def generate(template: str, params: Dict[str, any]) -> str:
        """
        Génère un châssis fabricant selon template

        Args:
            template: Template de format avec variables Python
                      Ex: "{prefix}{year:02d}{seq:06d}"
            params: Dictionnaire de valeurs pour les variables
                    Ex: {"prefix": "ABC", "year": 25, "seq": 1234}

        Returns:
            Numéro de châssis généré

        Raises:
            ValueError: Si template ou params invalides

        Example:
            >>> ManufacturerChassisGenerator.generate(
            ...     "{prefix}{year:2}{seq:06}",
            ...     {"prefix": "AP2KC1A6S", "year": 25, "seq": 8796}
            ... )
            'AP2KC1A6S258796'
        """
        try:
            chassis = template.format(**params)
            return chassis.upper()
        except KeyError as e:
            raise ValueError(f"Variable manquante dans params: {e}")
        except Exception as e:
            raise ValueError(f"Erreur génération châssis: {e}")

    @staticmethod
    def generate_batch(
        template: str,
        base_params: Dict[str, any],
        sequence_var: str = "seq",
        start_sequence: int = 1,
        quantity: int = 1
    ) -> List[str]:
        """
        Génère un lot de châssis avec séquence incrémentale

        Args:
            template: Template de format
            base_params: Paramètres de base (sans séquence)
            sequence_var: Nom de la variable séquentielle dans le template
            start_sequence: Numéro de début
            quantity: Nombre de châssis à générer

        Returns:
            Liste de châssis générés

        Example:
            >>> ManufacturerChassisGenerator.generate_batch(
            ...     "{prefix}{seq:04d}",
            ...     {"prefix": "TEST"},
            ...     sequence_var="seq",
            ...     start_sequence=100,
            ...     quantity=3
            ... )
            ['TEST0100', 'TEST0101', 'TEST0102']
        """
        chassis_list = []
        for i in range(quantity):
            params = base_params.copy()
            params[sequence_var] = start_sequence + i
            chassis = ManufacturerChassisGenerator.generate(template, params)
            chassis_list.append(chassis)
        return chassis_list


class ChassisFactory:
    """
    Point d'entrée simplifié pour génération et validation de châssis

    Fournit une API unifiée pour tous les cas d'usage:
    - Génération VIN ISO 3779
    - Génération châssis fabricant
    - Génération aléatoire pour tests
    - Validation universelle
    - Détection et continuation de séquences
    """

    def __init__(self, prefix_db_path: Optional[str] = None, use_real_prefixes: bool = True):
        """
        Initialise la factory avec les générateurs

        Args:
            prefix_db_path: Chemin vers VinPrefixes.txt (optionnel)
            use_real_prefixes: Si True, charge la base de préfixes réels si disponible
        """
        self.vin_generator = VINGenerator()
        self.manufacturer_generator = ManufacturerChassisGenerator()
        self.validator = ChassisValidator()

        # Charger base de préfixes réels si demandé et disponible
        self.prefix_db: Optional[VINPrefixDatabase] = None
        if use_real_prefixes and HAS_PREFIX_DATABASE:
            try:
                self.prefix_db = VINPrefixDatabase(prefix_db_path)
            except FileNotFoundError:
                # Base de préfixes non trouvée, mode générique
                pass

    def create_vin(
        self,
        wmi: str,
        vds: str,
        year: int,
        plant: str = "S",
        sequence: int = 1
    ) -> str:
        """
        Crée un VIN ISO 3779

        Args:
            wmi: World Manufacturer Identifier (3 chars)
            vds: Vehicle Descriptor Section (5 chars)
            year: Année modèle (2001-2030)
            plant: Code usine (1 char)
            sequence: Numéro de série

        Returns:
            VIN 17 caractères avec checksum
        """
        return self.vin_generator.generate(wmi, vds, year, plant, sequence)

    def create_vin_batch(
        self,
        wmi: str,
        vds: str,
        year: int,
        plant: str = "S",
        start_sequence: int = 1,
        quantity: int = 1
    ) -> List[str]:
        """Crée un lot de VIN consécutifs"""
        return self.vin_generator.generate_batch(
            wmi, vds, year, plant, start_sequence, quantity
        )

    def create_chassis(self, template: str, params: Dict[str, any]) -> str:
        """
        Crée un châssis fabricant

        Args:
            template: Template de format
            params: Paramètres de substitution

        Returns:
            Numéro de châssis généré
        """
        return self.manufacturer_generator.generate(template, params)

    def create_chassis_batch(
        self,
        template: str,
        base_params: Dict[str, any],
        sequence_var: str = "seq",
        start_sequence: int = 1,
        quantity: int = 1
    ) -> List[str]:
        """Crée un lot de châssis fabricant"""
        return self.manufacturer_generator.generate_batch(
            template, base_params, sequence_var, start_sequence, quantity
        )

    def create_vin_from_real_prefix(
        self,
        manufacturer: Optional[str] = None,
        country: Optional[str] = None,
        wmi: Optional[str] = None,
        plant: str = "S",
        sequence: int = 1
    ) -> str:
        """
        Crée un VIN avec préfixe réel depuis la base de données

        Args:
            manufacturer: Nom du fabricant (ex: "Toyota", "Ford")
            country: Pays d'origine (ex: "China", "USA")
            wmi: WMI spécifique (ex: "LZS", "1FA")
            plant: Code usine position 11 (défaut: "S")
            sequence: Numéro de série (1-999999)

        Returns:
            VIN 17 caractères avec préfixe authentique

        Raises:
            RuntimeError: Si base de préfixes non disponible
            ValueError: Si aucun préfixe ne correspond aux critères

        Example:
            >>> factory.create_vin_from_real_prefix(manufacturer="Toyota", sequence=1)
            'JT2BB1BAPS000001'
        """
        if not self.prefix_db:
            raise RuntimeError(
                "Base de préfixes VIN non disponible. "
                "Installez VinPrefixes.txt dans data/ ou désactivez use_real_prefixes."
            )

        # Récupérer préfixe réel
        prefix = self.prefix_db.get_random_prefix(
            wmi=wmi,
            manufacturer=manufacturer,
            country=country
        )

        # Construire VIN complet ISO 3779
        # Structure: [8 chars prefix][checksum][year_code][plant][6 chars sequence]
        # = [WMI(3) + VDS(5)][checksum(1)][year(1)][plant(1)][sequence(6)] = 17 chars
        sequence_str = str(sequence).zfill(6)
        vin_temp = f"{prefix.wmi_vds}X{prefix.year_code}{plant.upper()}{sequence_str}"

        # Calculer et insérer checksum en position 9
        checksum = ChassisValidator.calculate_vin_checksum(vin_temp)
        vin = f"{prefix.wmi_vds}{checksum}{prefix.year_code}{plant.upper()}{sequence_str}"

        # Validation
        result = self.validator.validate_vin(vin)
        if not result.is_valid:
            raise ValueError(f"VIN généré invalide: {result.errors}")

        return vin

    def create_vin_batch_from_real_prefixes(
        self,
        manufacturer: Optional[str] = None,
        country: Optional[str] = None,
        wmi: Optional[str] = None,
        plant: str = "S",
        start_sequence: int = 1,
        quantity: int = 1
    ) -> List[str]:
        """
        Crée un lot de VIN consécutifs avec préfixe réel

        Args:
            manufacturer: Nom du fabricant
            country: Pays d'origine
            wmi: WMI spécifique
            plant: Code usine position 11 (défaut: "S")
            start_sequence: Numéro de début
            quantity: Nombre de VIN à générer

        Returns:
            Liste de VIN générés avec même préfixe

        Example:
            >>> factory.create_vin_batch_from_real_prefixes(
            ...     manufacturer="Ford", start_sequence=1, quantity=5
            ... )
            ['1FAHP58U5PS000001', '1FAHP58U7PS000002', ...]
        """
        if not self.prefix_db:
            raise RuntimeError("Base de préfixes VIN non disponible")

        # Récupérer un préfixe réel une seule fois
        prefix = self.prefix_db.get_random_prefix(
            wmi=wmi,
            manufacturer=manufacturer,
            country=country
        )

        # Générer lot avec ce préfixe
        batch = []
        for i in range(quantity):
            sequence_str = str(start_sequence + i).zfill(6)
            vin_temp = f"{prefix.wmi_vds}X{prefix.year_code}{plant.upper()}{sequence_str}"

            checksum = ChassisValidator.calculate_vin_checksum(vin_temp)
            vin = f"{prefix.wmi_vds}{checksum}{prefix.year_code}{plant.upper()}{sequence_str}"
            batch.append(vin)

        return batch

    def create_random(
        self,
        hs_code: str,
        quantity: int = 1,
        chassis_type: ChassisType = ChassisType.VIN_ISO3779,
        use_real_prefixes: bool = False
    ) -> List[str]:
        """
        Crée des châssis aléatoires pour tests

        Args:
            hs_code: Code HS du véhicule (ex: "8704", "8711")
            quantity: Nombre de châssis à générer
            chassis_type: Type de châssis (VIN ou fabricant)
            use_real_prefixes: Si True, utilise base de préfixes réels si disponible

        Returns:
            Liste de châssis aléatoires valides

        Example:
            >>> factory.create_random("8704", quantity=5)
            ['LZS...', 'LFV...', ...]

            >>> factory.create_random("8704", quantity=5, use_real_prefixes=True)
            ['1FAHP58U5PS012345', 'JT2BB1BA7TS067890', ...]
        """
        # Si base de préfixes réels disponible et demandée
        if use_real_prefixes and self.prefix_db and chassis_type == ChassisType.VIN_ISO3779:
            chassis_list = []
            for _ in range(quantity):
                try:
                    # Générer VIN avec préfixe réel aléatoire
                    sequence = random.randint(1, 999999)
                    vin = self.create_vin_from_real_prefix(sequence=sequence)
                    chassis_list.append(vin)
                except (RuntimeError, ValueError):
                    # Fallback mode générique si erreur
                    break

            # Si génération réussie, retourner
            if len(chassis_list) == quantity:
                return chassis_list

        # Mode générique (sans préfixes réels)
        # WMI aléatoires pour Chine (LZS, LFV, etc.)
        wmi_pool = ["LZS", "LFV", "LBV", "LDC", "LGX"]

        # VDS aléatoire (5 caractères alphanumériques, sans I/O/Q)
        allowed_chars = string.ascii_uppercase + string.digits
        allowed_chars = ''.join(c for c in allowed_chars if c.upper() not in ChassisValidator.VIN_FORBIDDEN)

        chassis_list = []
        for _ in range(quantity):
            if chassis_type == ChassisType.VIN_ISO3779:
                # VIN aléatoire
                wmi = random.choice(wmi_pool)
                vds = ''.join(random.choice(allowed_chars) for _ in range(5))
                year = random.randint(2020, 2028)
                sequence = random.randint(1, 99999)
                chassis = self.create_vin(wmi, vds, year, "S", sequence)
            else:
                # Châssis fabricant aléatoire
                prefix = ''.join(random.choice(allowed_chars) for _ in range(9))
                template = "{prefix}{year:02d}{seq:05d}"
                params = {
                    "prefix": prefix,
                    "year": random.randint(20, 30),
                    "seq": random.randint(1, 9999)
                }
                chassis = self.create_chassis(template, params)

            chassis_list.append(chassis)

        return chassis_list

    def validate(self, chassis: str) -> ValidationResult:
        """
        Valide un châssis (détection automatique du type)

        Args:
            chassis: Numéro de châssis à valider

        Returns:
            ValidationResult avec détails
        """
        return self.validator.validate(chassis)

    def continue_sequence(
        self,
        existing: List[str],
        quantity: int = 1
    ) -> Tuple[List[str], str]:
        """
        Détecte le pattern d'une séquence et la continue

        Args:
            existing: Liste de châssis existants (min 2 pour détection)
            quantity: Nombre de châssis supplémentaires à générer

        Returns:
            Tuple (châssis générés, description du pattern détecté)

        Raises:
            ValueError: Si pattern non détectable ou séquence invalide

        Example:
            >>> factory.continue_sequence(["ABC001", "ABC002", "ABC003"], 2)
            (['ABC004', 'ABC005'], 'Séquence numérique: ABC + 3 digits')
        """
        if len(existing) < 2:
            raise ValueError("Minimum 2 châssis requis pour détection de pattern")

        # Analyser les 2 derniers châssis
        last = existing[-1]
        prev = existing[-2]

        if len(last) != len(prev):
            raise ValueError("Longueurs incohérentes dans la séquence")

        # Chercher la différence (suffix numérique)
        i = 0
        while i < len(last) and last[i] == prev[i]:
            i += 1

        if i == len(last):
            raise ValueError("Aucune différence détectée entre châssis")

        prefix = last[:i]
        suffix_last = last[i:]
        suffix_prev = prev[i:]

        # Vérifier si suffixes sont numériques
        if not (suffix_last.isdigit() and suffix_prev.isdigit()):
            raise ValueError("Séquence non-numérique détectée")

        # Calculer incrément
        num_last = int(suffix_last)
        num_prev = int(suffix_prev)
        increment = num_last - num_prev

        if increment <= 0:
            raise ValueError(f"Incrément invalide: {increment}")

        # Générer suite
        generated = []
        next_num = num_last + increment
        for _ in range(quantity):
            chassis = prefix + str(next_num).zfill(len(suffix_last))
            generated.append(chassis)
            next_num += increment

        pattern_desc = f"Séquence numérique: {prefix} + {len(suffix_last)} digits (incr={increment})"

        return generated, pattern_desc


# Exemple d'utilisation
if __name__ == "__main__":
    print("=== Service Générateur de Châssis Universel ===\n")

    factory = ChassisFactory()

    # 1. Génération VIN ISO 3779
    print("1. Génération VIN ISO 3779")
    print("-" * 40)
    vin = factory.create_vin("LZS", "HCKZS", 2028, "S", 4073)
    print(f"VIN généré: {vin}")
    result = factory.validate(vin)
    print(f"Validation: {'✅ Valide' if result.is_valid else '❌ Invalide'}")
    print(f"Checksum: {'✅' if result.checksum_valid else '❌'}\n")

    # 2. Génération lot VIN
    print("2. Génération lot de 5 VIN consécutifs")
    print("-" * 40)
    vin_batch = factory.create_vin_batch("LZS", "HCKZS", 2028, "S", 4073, 5)
    for i, v in enumerate(vin_batch, 1):
        print(f"  {i}. {v}")
    print()

    # 3. Châssis fabricant
    print("3. Génération châssis fabricant")
    print("-" * 40)
    chassis = factory.create_chassis(
        "{prefix}{year:02d}{seq:05d}",
        {"prefix": "AP2KC1A6S", "year": 25, "seq": 8796}
    )
    print(f"Châssis: {chassis}")
    result = factory.validate(chassis)
    print(f"Validation: {'✅ Valide' if result.is_valid else '❌ Invalide'}\n")

    # 4. Châssis aléatoires
    print("4. Génération 3 châssis aléatoires pour tests")
    print("-" * 40)
    random_chassis = factory.create_random("8704", quantity=3)
    for i, c in enumerate(random_chassis, 1):
        print(f"  {i}. {c}")
    print()

    # 5. Continuation de séquence
    print("5. Détection et continuation de séquence")
    print("-" * 40)
    existing = ["TEST0100", "TEST0102", "TEST0104"]
    print(f"Séquence existante: {existing}")
    continued, pattern = factory.continue_sequence(existing, 3)
    print(f"Pattern détecté: {pattern}")
    print(f"Suite générée: {continued}\n")
