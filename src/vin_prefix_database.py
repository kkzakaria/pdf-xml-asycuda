"""
Base de données de préfixes VIN réels
======================================

Ce module gère une base de données de 62,000+ préfixes VIN réels provenant
de constructeurs automobiles mondiaux. Les préfixes incluent le WMI (World
Manufacturer Identifier) et VDS (Vehicle Descriptor Section) ainsi que le
code année correspondant.

Source: VinGenerator project (https://github.com/yanigisawa/VinGenerator)
Format: 8 premiers caractères du VIN + code année

Usage:
    from vin_prefix_database import VINPrefixDatabase

    db = VINPrefixDatabase()
    prefix = db.get_random_prefix()
    print(f"WMI+VDS: {prefix.wmi_vds}, Année: {prefix.year_code}")
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Set, Tuple
from pathlib import Path
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class VINPrefix:
    """
    Préfixe VIN réel avec métadonnées

    Attributes:
        wmi_vds: Les 8 premiers caractères du VIN (WMI + VDS)
        year_code: Code année position 10 (A-Y pour 2010-2039, 1-9 pour 2001-2009)
        wmi: World Manufacturer Identifier (3 premiers caractères)
        manufacturer: Nom du fabricant (optionnel, déduit si possible)
        country: Pays d'origine (optionnel, déduit du WMI)
    """
    wmi_vds: str
    year_code: str
    wmi: str
    manufacturer: Optional[str] = None
    country: Optional[str] = None

    def __post_init__(self):
        """Validation et déduction automatique des métadonnées"""
        if len(self.wmi_vds) != 8:
            raise ValueError(f"wmi_vds doit avoir 8 caractères, reçu: {len(self.wmi_vds)}")
        if len(self.year_code) != 1:
            raise ValueError(f"year_code doit avoir 1 caractère, reçu: {len(self.year_code)}")

        # Déduire manufacturer et country si pas fournis
        if not self.manufacturer:
            self.manufacturer = WMI_REGISTRY.get(self.wmi, {}).get("manufacturer")
        if not self.country:
            self.country = WMI_REGISTRY.get(self.wmi, {}).get("country")


# Registre WMI connus (extrait partiel, extensible)
WMI_REGISTRY: Dict[str, Dict[str, str]] = {
    # Chine
    "LZS": {"manufacturer": "Apsonic", "country": "China"},
    "LFV": {"manufacturer": "Lifan", "country": "China"},
    "LBV": {"manufacturer": "Haojue/Suzuki", "country": "China"},
    "LDC": {"manufacturer": "Jianshe", "country": "China"},
    "LGX": {"manufacturer": "Zongshen", "country": "China"},
    "LJD": {"manufacturer": "Qingqi", "country": "China"},
    "LYL": {"manufacturer": "Dayun", "country": "China"},

    # États-Unis
    "1G1": {"manufacturer": "Chevrolet", "country": "USA"},
    "1GC": {"manufacturer": "Chevrolet Trucks", "country": "USA"},
    "1GT": {"manufacturer": "GMC Trucks", "country": "USA"},
    "1FA": {"manufacturer": "Ford", "country": "USA"},
    "1FT": {"manufacturer": "Ford Trucks", "country": "USA"},
    "1N4": {"manufacturer": "Nissan USA", "country": "USA"},
    "1N6": {"manufacturer": "Nissan Trucks USA", "country": "USA"},

    # Allemagne
    "WBA": {"manufacturer": "BMW", "country": "Germany"},
    "WDB": {"manufacturer": "Mercedes-Benz", "country": "Germany"},
    "WDC": {"manufacturer": "DaimlerChrysler", "country": "Germany"},
    "WVW": {"manufacturer": "Volkswagen", "country": "Germany"},
    "WAU": {"manufacturer": "Audi", "country": "Germany"},

    # Japon
    "JMB": {"manufacturer": "Mitsubishi", "country": "Japan"},
    "JN1": {"manufacturer": "Nissan", "country": "Japan"},
    "JT2": {"manufacturer": "Toyota", "country": "Japan"},

    # Corée
    "KM8": {"manufacturer": "Hyundai", "country": "South Korea"},
    "KNA": {"manufacturer": "Kia", "country": "South Korea"},

    # France
    "VF1": {"manufacturer": "Renault", "country": "France"},
    "VF3": {"manufacturer": "Peugeot", "country": "France"},
    "VF7": {"manufacturer": "Citroën", "country": "France"},

    # Royaume-Uni
    "SAJ": {"manufacturer": "Jaguar", "country": "UK"},
    "SAL": {"manufacturer": "Land Rover", "country": "UK"},

    # Italie
    "ZAR": {"manufacturer": "Alfa Romeo", "country": "Italy"},
    "ZFA": {"manufacturer": "Fiat", "country": "Italy"},
    "ZFF": {"manufacturer": "Ferrari", "country": "Italy"},

    # Suède
    "YS3": {"manufacturer": "Saab", "country": "Sweden"},
    "YV1": {"manufacturer": "Volvo", "country": "Sweden"},
}


class VINPrefixDatabase:
    """
    Gestionnaire de base de données de préfixes VIN réels

    Charge et indexe 62,000+ préfixes VIN réels pour génération
    de VIN authentiques avec constructeurs mondiaux.

    Usage:
        db = VINPrefixDatabase()

        # Préfixe aléatoire
        prefix = db.get_random_prefix()

        # Filtré par fabricant
        toyota = db.get_random_prefix(manufacturer="Toyota")

        # Filtré par pays
        china = db.get_random_prefix(country="China")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialise la base de données

        Args:
            db_path: Chemin vers VinPrefixes.txt (défaut: data/VinPrefixes.txt)
        """
        if db_path is None:
            # Chercher dans plusieurs emplacements possibles
            search_paths = [
                Path(__file__).parent.parent / "data" / "VinPrefixes.txt",
                Path("data/VinPrefixes.txt"),
                Path("VinPrefixes.txt"),
            ]
            for path in search_paths:
                if path.exists():
                    db_path = str(path)
                    break

        if db_path is None or not Path(db_path).exists():
            raise FileNotFoundError(
                f"Fichier VinPrefixes.txt introuvable. Chemins recherchés: {search_paths}"
            )

        self.db_path = Path(db_path)
        self.prefixes: List[VINPrefix] = []
        self._wmi_index: Dict[str, List[VINPrefix]] = {}
        self._manufacturer_index: Dict[str, List[VINPrefix]] = {}
        self._country_index: Dict[str, List[VINPrefix]] = {}

        self._load_database()

    def _load_database(self) -> None:
        """Charge et indexe la base de données"""
        logger.info(f"Chargement base de données VIN depuis {self.db_path}")

        with open(self.db_path, "r") as f:
            for line in f:
                line = line.strip()

                # Skip header et lignes vides
                if not line or line.startswith("VinPos"):
                    continue

                parts = line.split()
                if len(parts) != 2:
                    logger.warning(f"Ligne invalide ignorée: {line}")
                    continue

                wmi_vds = parts[0].upper()
                year_code = parts[1].upper()
                wmi = wmi_vds[:3]

                # Créer préfixe avec métadonnées
                try:
                    prefix = VINPrefix(
                        wmi_vds=wmi_vds,
                        year_code=year_code,
                        wmi=wmi
                    )
                    self.prefixes.append(prefix)

                    # Indexer par WMI
                    if wmi not in self._wmi_index:
                        self._wmi_index[wmi] = []
                    self._wmi_index[wmi].append(prefix)

                    # Indexer par manufacturer
                    if prefix.manufacturer:
                        if prefix.manufacturer not in self._manufacturer_index:
                            self._manufacturer_index[prefix.manufacturer] = []
                        self._manufacturer_index[prefix.manufacturer].append(prefix)

                    # Indexer par country
                    if prefix.country:
                        if prefix.country not in self._country_index:
                            self._country_index[prefix.country] = []
                        self._country_index[prefix.country].append(prefix)

                except ValueError as e:
                    logger.warning(f"Erreur validation préfixe {line}: {e}")
                    continue

        logger.info(f"Chargés {len(self.prefixes)} préfixes VIN réels")
        logger.info(f"  - {len(self._wmi_index)} WMI uniques")
        logger.info(f"  - {len(self._manufacturer_index)} fabricants indexés")
        logger.info(f"  - {len(self._country_index)} pays indexés")

    def get_random_prefix(
        self,
        wmi: Optional[str] = None,
        manufacturer: Optional[str] = None,
        country: Optional[str] = None,
        year_code: Optional[str] = None
    ) -> VINPrefix:
        """
        Récupère un préfixe VIN aléatoire avec filtres optionnels

        Args:
            wmi: Filtrer par WMI spécifique (ex: "LZS", "1FA")
            manufacturer: Filtrer par fabricant (ex: "Toyota", "Ford")
            country: Filtrer par pays (ex: "China", "USA")
            year_code: Filtrer par code année (ex: "A", "5")

        Returns:
            VINPrefix aléatoire correspondant aux critères

        Raises:
            ValueError: Si aucun préfixe ne correspond aux critères
        """
        # Appliquer filtres
        candidates = self.prefixes

        if wmi:
            candidates = self._wmi_index.get(wmi.upper(), [])
            if not candidates:
                raise ValueError(f"Aucun préfixe trouvé pour WMI: {wmi}")

        if manufacturer:
            # Recherche case-insensitive partielle
            manufacturer_lower = manufacturer.lower()
            candidates = [
                p for p in candidates
                if p.manufacturer and manufacturer_lower in p.manufacturer.lower()
            ]
            if not candidates:
                raise ValueError(f"Aucun préfixe trouvé pour fabricant: {manufacturer}")

        if country:
            country_lower = country.lower()
            candidates = [
                p for p in candidates
                if p.country and country_lower in p.country.lower()
            ]
            if not candidates:
                raise ValueError(f"Aucun préfixe trouvé pour pays: {country}")

        if year_code:
            year_code_upper = year_code.upper()
            candidates = [p for p in candidates if p.year_code == year_code_upper]
            if not candidates:
                raise ValueError(f"Aucun préfixe trouvé pour année: {year_code}")

        if not candidates:
            raise ValueError("Aucun préfixe ne correspond aux critères")

        return random.choice(candidates)

    def search_by_wmi(self, wmi: str) -> List[VINPrefix]:
        """
        Recherche tous les préfixes pour un WMI donné

        Args:
            wmi: World Manufacturer Identifier (3 caractères)

        Returns:
            Liste de préfixes correspondants
        """
        return self._wmi_index.get(wmi.upper(), [])

    def search_by_manufacturer(self, manufacturer: str) -> List[VINPrefix]:
        """
        Recherche tous les préfixes pour un fabricant

        Args:
            manufacturer: Nom du fabricant (recherche partielle case-insensitive)

        Returns:
            Liste de préfixes correspondants
        """
        manufacturer_lower = manufacturer.lower()
        results = []
        for mfr, prefixes in self._manufacturer_index.items():
            if manufacturer_lower in mfr.lower():
                results.extend(prefixes)
        return results

    def get_statistics(self) -> Dict[str, any]:
        """
        Retourne des statistiques sur la base de données

        Returns:
            Dictionnaire avec statistiques détaillées
        """
        return {
            "total_prefixes": len(self.prefixes),
            "unique_wmis": len(self._wmi_index),
            "indexed_manufacturers": len(self._manufacturer_index),
            "indexed_countries": len(self._country_index),
            "manufacturers": sorted(self._manufacturer_index.keys()),
            "countries": sorted(self._country_index.keys()),
            "top_10_wmis": sorted(
                self._wmi_index.keys(),
                key=lambda w: len(self._wmi_index[w]),
                reverse=True
            )[:10]
        }

    def list_manufacturers(self) -> List[str]:
        """Liste tous les fabricants indexés"""
        return sorted(self._manufacturer_index.keys())

    def list_countries(self) -> List[str]:
        """Liste tous les pays indexés"""
        return sorted(self._country_index.keys())

    def list_wmis(self) -> List[str]:
        """Liste tous les WMI uniques"""
        return sorted(self._wmi_index.keys())


# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Démonstration VINPrefixDatabase ===\n")

    # Charger base de données
    db = VINPrefixDatabase()

    # Statistiques
    stats = db.get_statistics()
    print(f"📊 Statistiques:")
    print(f"  - Total préfixes: {stats['total_prefixes']:,}")
    print(f"  - WMI uniques: {stats['unique_wmis']}")
    print(f"  - Fabricants: {stats['indexed_manufacturers']}")
    print(f"  - Pays: {stats['indexed_countries']}")

    print(f"\n📋 Fabricants disponibles:")
    for mfr in db.list_manufacturers()[:10]:
        count = len(db.search_by_manufacturer(mfr))
        print(f"  - {mfr}: {count} préfixes")

    print(f"\n🌍 Pays disponibles:")
    for country in db.list_countries():
        count = len(db._country_index[country])
        print(f"  - {country}: {count} préfixes")

    # Exemples de récupération
    print(f"\n🎲 Préfixes aléatoires:")

    # Aléatoire total
    prefix = db.get_random_prefix()
    print(f"\n  1. Aléatoire total:")
    print(f"     WMI+VDS: {prefix.wmi_vds}")
    print(f"     Année: {prefix.year_code}")
    print(f"     Fabricant: {prefix.manufacturer or 'Inconnu'}")
    print(f"     Pays: {prefix.country or 'Inconnu'}")

    # Chine
    try:
        prefix = db.get_random_prefix(country="China")
        print(f"\n  2. Fabricant chinois:")
        print(f"     WMI+VDS: {prefix.wmi_vds}")
        print(f"     Fabricant: {prefix.manufacturer or 'Inconnu'}")
    except ValueError as e:
        print(f"     Erreur: {e}")

    # Toyota
    try:
        prefix = db.get_random_prefix(manufacturer="Toyota")
        print(f"\n  3. Toyota:")
        print(f"     WMI+VDS: {prefix.wmi_vds}")
        print(f"     WMI: {prefix.wmi}")
    except ValueError as e:
        print(f"     Erreur: {e}")

    # WMI spécifique
    try:
        prefix = db.get_random_prefix(wmi="1FA")
        print(f"\n  4. WMI 1FA (Ford):")
        print(f"     WMI+VDS: {prefix.wmi_vds}")
        print(f"     Année: {prefix.year_code}")
    except ValueError as e:
        print(f"     Erreur: {e}")
