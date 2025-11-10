#!/usr/bin/env python3
"""
Tests pour VINPrefixDatabase
==============================

Tests unitaires pour la base de données de préfixes VIN réels.
"""

import sys
from pathlib import Path
import pytest

# Ajouter src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from vin_prefix_database import VINPrefixDatabase, VINPrefix, WMI_REGISTRY


class TestVINPrefix:
    """Tests pour la dataclass VINPrefix"""

    def test_vinprefix_creation_valid(self):
        """Test création VINPrefix valide"""
        prefix = VINPrefix(
            wmi_vds="1FAHP58U",
            year_code="5",
            wmi="1FA"
        )
        assert prefix.wmi_vds == "1FAHP58U"
        assert prefix.year_code == "5"
        assert prefix.wmi == "1FA"

    def test_vinprefix_auto_deduction(self):
        """Test déduction automatique manufacturer et country depuis WMI_REGISTRY"""
        prefix = VINPrefix(
            wmi_vds="LZSHCKZS",
            year_code="2",
            wmi="LZS"
        )
        assert prefix.manufacturer == "Apsonic"
        assert prefix.country == "China"

    def test_vinprefix_invalid_wmi_vds_length(self):
        """Test erreur si wmi_vds n'a pas 8 caractères"""
        with pytest.raises(ValueError, match="wmi_vds doit avoir 8 caractères"):
            VINPrefix(wmi_vds="1FA", year_code="5", wmi="1FA")

    def test_vinprefix_invalid_year_code_length(self):
        """Test erreur si year_code n'a pas 1 caractère"""
        with pytest.raises(ValueError, match="year_code doit avoir 1 caractère"):
            VINPrefix(wmi_vds="1FAHP58U", year_code="AB", wmi="1FA")


class TestVINPrefixDatabase:
    """Tests pour VINPrefixDatabase"""

    @pytest.fixture
    def database(self):
        """Fixture qui retourne une instance de VINPrefixDatabase"""
        return VINPrefixDatabase()

    def test_database_loads_successfully(self, database):
        """Test que la base de données se charge correctement"""
        assert database.db_path.exists()
        assert len(database.prefixes) > 60000  # 62,177 préfixes attendus
        assert len(database._wmi_index) > 300  # 309 WMI uniques
        assert len(database._manufacturer_index) >= 20
        assert len(database._country_index) >= 6

    def test_database_indexing(self, database):
        """Test que les index sont correctement créés"""
        # Test WMI index
        assert "1FA" in database._wmi_index  # Ford USA
        ford_prefixes = database._wmi_index["1FA"]
        assert len(ford_prefixes) > 0
        assert all(p.wmi == "1FA" for p in ford_prefixes)

        # Test manufacturer index
        assert "Ford" in database._manufacturer_index
        ford_mfr_prefixes = database._manufacturer_index["Ford"]
        assert len(ford_mfr_prefixes) > 0

    def test_get_random_prefix_no_filters(self, database):
        """Test récupération préfixe aléatoire sans filtre"""
        prefix = database.get_random_prefix()
        assert isinstance(prefix, VINPrefix)
        assert len(prefix.wmi_vds) == 8
        assert len(prefix.year_code) == 1

    def test_get_random_prefix_by_wmi(self, database):
        """Test filtrage par WMI"""
        prefix = database.get_random_prefix(wmi="1FA")
        assert prefix.wmi == "1FA"
        assert prefix.manufacturer == "Ford"
        assert prefix.country == "USA"

    def test_get_random_prefix_by_manufacturer(self, database):
        """Test filtrage par fabricant"""
        prefix = database.get_random_prefix(manufacturer="Toyota")
        assert prefix.manufacturer == "Toyota"
        assert prefix.country == "Japan"

    def test_get_random_prefix_by_country(self, database):
        """Test filtrage par pays"""
        prefix = database.get_random_prefix(country="Germany")
        assert prefix.country == "Germany"

    def test_get_random_prefix_by_year_code(self, database):
        """Test filtrage par code année"""
        prefix = database.get_random_prefix(year_code="5")
        assert prefix.year_code == "5"

    def test_get_random_prefix_combined_filters(self, database):
        """Test filtrage combiné"""
        prefix = database.get_random_prefix(manufacturer="Ford", country="USA", year_code="5")
        assert "Ford" in (prefix.manufacturer or "")  # Peut être "Ford" ou "Ford Trucks"
        assert prefix.country == "USA"
        assert prefix.year_code == "5"

    def test_get_random_prefix_no_match(self, database):
        """Test erreur si aucun préfixe ne correspond"""
        with pytest.raises(ValueError, match="Aucun préfixe trouvé pour WMI"):
            database.get_random_prefix(wmi="XXX")

        with pytest.raises(ValueError, match="Aucun préfixe trouvé pour fabricant"):
            database.get_random_prefix(manufacturer="NonExistent")

    def test_search_by_wmi(self, database):
        """Test recherche par WMI"""
        results = database.search_by_wmi("1FA")
        assert len(results) > 0
        assert all(p.wmi == "1FA" for p in results)

    def test_search_by_wmi_case_insensitive(self, database):
        """Test recherche WMI case-insensitive"""
        results_upper = database.search_by_wmi("1FA")
        results_lower = database.search_by_wmi("1fa")
        assert len(results_upper) == len(results_lower)

    def test_search_by_manufacturer(self, database):
        """Test recherche par fabricant"""
        results = database.search_by_manufacturer("Ford")
        assert len(results) > 0
        assert all("Ford" in (p.manufacturer or "") for p in results)

    def test_search_by_manufacturer_partial(self, database):
        """Test recherche fabricant partielle (case-insensitive)"""
        results = database.search_by_manufacturer("ford")
        assert len(results) > 0

    def test_get_statistics(self, database):
        """Test génération statistiques"""
        stats = database.get_statistics()
        assert stats["total_prefixes"] > 60000
        assert stats["unique_wmis"] > 300
        assert stats["indexed_manufacturers"] >= 20
        assert stats["indexed_countries"] >= 6
        assert "manufacturers" in stats
        assert "countries" in stats
        assert "top_10_wmis" in stats
        assert len(stats["top_10_wmis"]) == 10

    def test_list_manufacturers(self, database):
        """Test liste fabricants"""
        manufacturers = database.list_manufacturers()
        assert len(manufacturers) >= 20
        assert "Ford" in manufacturers
        assert "Toyota" in manufacturers
        assert "BMW" in manufacturers

    def test_list_countries(self, database):
        """Test liste pays"""
        countries = database.list_countries()
        assert len(countries) >= 6
        assert "USA" in countries
        assert "Germany" in countries
        assert "Japan" in countries

    def test_list_wmis(self, database):
        """Test liste WMI"""
        wmis = database.list_wmis()
        assert len(wmis) > 300
        assert "1FA" in wmis
        assert "JT2" in wmis
        assert "WBA" in wmis


class TestWMIRegistry:
    """Tests pour WMI_REGISTRY"""

    def test_registry_format(self):
        """Test format du registre WMI"""
        for wmi, data in WMI_REGISTRY.items():
            assert len(wmi) == 3, f"WMI {wmi} doit avoir 3 caractères"
            assert "manufacturer" in data
            assert "country" in data
            assert isinstance(data["manufacturer"], str)
            assert isinstance(data["country"], str)

    def test_registry_chinese_manufacturers(self):
        """Test fabricants chinois dans registre"""
        chinese_wmis = ["LZS", "LFV", "LBV", "LDC", "LGX", "LJD", "LYL"]
        for wmi in chinese_wmis:
            assert wmi in WMI_REGISTRY
            assert WMI_REGISTRY[wmi]["country"] == "China"

    def test_registry_usa_manufacturers(self):
        """Test fabricants USA dans registre"""
        usa_wmis = ["1G1", "1GC", "1GT", "1FA", "1FT", "1N4", "1N6"]
        for wmi in usa_wmis:
            assert wmi in WMI_REGISTRY
            assert WMI_REGISTRY[wmi]["country"] == "USA"


class TestIntegration:
    """Tests d'intégration"""

    def test_no_forbidden_chars_in_prefixes(self):
        """Test qu'aucun préfixe ne contient I/O/Q"""
        db = VINPrefixDatabase()
        forbidden = {'I', 'O', 'Q', 'i', 'o', 'q'}
        problematic = [p for p in db.prefixes if any(c in forbidden for c in p.wmi_vds)]
        assert len(problematic) == 0, f"Trouvé {len(problematic)} préfixes avec caractères interdits"

    def test_all_prefixes_have_valid_format(self):
        """Test que tous les préfixes ont format valide"""
        db = VINPrefixDatabase()
        for prefix in db.prefixes[:1000]:  # Échantillon
            assert len(prefix.wmi_vds) == 8
            assert len(prefix.year_code) == 1
            assert len(prefix.wmi) == 3
            assert prefix.wmi_vds[:3] == prefix.wmi

    def test_manufacturer_consistency(self):
        """Test cohérence fabricant dans base"""
        db = VINPrefixDatabase()
        # Tous les préfixes Ford doivent avoir WMI commençant par 1F
        ford_prefixes = db.search_by_manufacturer("Ford")
        for p in ford_prefixes:
            assert p.wmi.startswith("1F"), f"Préfixe Ford invalide: {p.wmi}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
