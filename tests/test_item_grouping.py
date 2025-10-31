"""
Tests unitaires pour le regroupement d'articles par code HS

Teste la fonctionnalité de regroupement d'articles sans châssis
avec gestion des quantités selon le nombre de colis total.
"""

import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from models import Item, Package, Tarification, HSCode, SupplementaryUnit
from item_grouper import group_items_by_hs_code


def create_test_item(hs_code: str, quantity: float = 100.0, chassis: str = None) -> Item:
    """
    Crée un article de test.

    Args:
        hs_code: Code HS à 8 chiffres (ex: "87032319")
        quantity: Quantité de l'article
        chassis: Numéro de châssis (None = pas de châssis)

    Returns:
        Item configuré pour les tests
    """
    item = Item()

    # Tarification avec code HS et quantité
    item.tarification = Tarification(
        hscode=HSCode(commodity_code=hs_code),
        supplementary_units=[
            SupplementaryUnit(
                code='QA',
                name='Unité d\'apurement',
                quantity=quantity
            )
        ]
    )

    # Package avec ou sans châssis
    item.packages = Package(
        chassis_number=chassis
    )

    item.goods_description = f"Test article HS {hs_code}"

    return item


class TestItemGrouping:
    """Tests de regroupement d'articles"""

    def test_no_items(self):
        """Test avec liste vide"""
        result = group_items_by_hs_code([], total_packages=35.0)
        assert result == []

    def test_single_item_no_chassis(self):
        """Test avec un seul article sans châssis"""
        items = [create_test_item("87032319", quantity=100.0)]
        result = group_items_by_hs_code(items, total_packages=35.0)

        assert len(result) == 1
        # Un seul article = pas de regroupement = quantité inchangée
        assert result[0].tarification.supplementary_units[0].quantity == 100.0

    def test_multiple_items_same_hs_code_no_chassis(self):
        """Test avec plusieurs articles même code HS sans châssis"""
        items = [
            create_test_item("87032319", quantity=100.0),
            create_test_item("87032319", quantity=200.0),
            create_test_item("87032319", quantity=300.0)
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # Doit être regroupé en 1 seul article
        assert len(result) == 1
        assert result[0].tarification.hscode.commodity_code == "87032319"
        # Quantité = total_packages (premier article du premier groupe)
        assert result[0].tarification.supplementary_units[0].quantity == 35.0

    def test_multiple_items_different_hs_codes_no_chassis(self):
        """Test avec plusieurs articles de codes HS différents sans châssis"""
        items = [
            create_test_item("87032319", quantity=100.0),  # Groupe 1 - 2 articles
            create_test_item("87032319", quantity=200.0),  # Groupe 1
            create_test_item("87042110", quantity=150.0),  # Groupe 2 - 2 articles
            create_test_item("87042110", quantity=250.0),  # Groupe 2
            create_test_item("87112090", quantity=300.0),  # Groupe 3 - 1 article
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # Doit être regroupé en 3 articles (3 groupes)
        assert len(result) == 3

        # Vérifier les codes HS
        hs_codes = {item.tarification.hscode.commodity_code for item in result}
        assert hs_codes == {"87032319", "87042110", "87112090"}

        # Vérifier les quantités
        # Premier article du premier groupe : quantité = total_packages
        first_item = result[0]
        assert first_item.tarification.hscode.commodity_code == "87032319"
        assert first_item.tarification.supplementary_units[0].quantity == 35.0

        # Tous les autres articles : quantité = 0
        for item in result[1:]:
            assert item.tarification.supplementary_units[0].quantity == 0.0

    def test_all_different_hs_codes_no_grouping(self):
        """Test que si tous les codes HS sont différents, pas de regroupement"""
        items = [
            create_test_item("87032319", quantity=100.0),
            create_test_item("87042110", quantity=150.0),
            create_test_item("87112090", quantity=200.0)
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # Pas de regroupement : 3 articles → 3 articles
        assert len(result) == 3

        # Les quantités doivent rester inchangées
        assert result[0].tarification.supplementary_units[0].quantity == 100.0
        assert result[1].tarification.supplementary_units[0].quantity == 150.0
        assert result[2].tarification.supplementary_units[0].quantity == 200.0

    def test_items_with_chassis_not_grouped(self):
        """Test que les articles avec châssis ne sont PAS regroupés"""
        items = [
            create_test_item("87032319", quantity=100.0, chassis="VIN123456789012345"),
            create_test_item("87032319", quantity=200.0, chassis="VIN987654321098765"),
            create_test_item("87032319", quantity=300.0)  # Sans châssis
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # 2 articles avec châssis + 1 groupe sans châssis = 3 articles
        assert len(result) == 3

        # Vérifier que les 2 premiers ont leur châssis
        chassis_items = [item for item in result if item.packages.chassis_number]
        assert len(chassis_items) == 2
        assert chassis_items[0].packages.chassis_number == "VIN123456789012345"
        assert chassis_items[1].packages.chassis_number == "VIN987654321098765"

    def test_mixed_items_with_and_without_chassis(self):
        """Test avec mélange d'articles avec et sans châssis"""
        items = [
            create_test_item("87032319", quantity=100.0, chassis="VIN111111111111111"),
            create_test_item("87042110", quantity=150.0),  # Sans châssis - Groupe 1
            create_test_item("87042110", quantity=250.0),  # Sans châssis - Groupe 1
            create_test_item("87112090", quantity=300.0, chassis="VIN222222222222222"),
            create_test_item("87112090", quantity=400.0),  # Sans châssis - Groupe 2
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # 2 articles avec châssis + 2 groupes sans châssis = 4 articles
        assert len(result) == 4

        # Vérifier articles avec châssis (non modifiés)
        chassis_items = [item for item in result if item.packages.chassis_number]
        assert len(chassis_items) == 2

        # Vérifier articles sans châssis (regroupés)
        no_chassis_items = [item for item in result if not item.packages.chassis_number]
        assert len(no_chassis_items) == 2

        # Premier article du premier groupe sans châssis : quantité = total_packages
        # Les autres : quantité = 0
        # Comme les articles avec châssis sont en premier, le premier sans châssis est à l'index 2
        assert result[2].tarification.supplementary_units[0].quantity == 35.0
        assert result[3].tarification.supplementary_units[0].quantity == 0.0

    def test_no_total_packages(self):
        """Test sans nombre de colis total (total_packages=None)"""
        items = [
            create_test_item("87032319", quantity=100.0),
            create_test_item("87032319", quantity=200.0)
        ]
        result = group_items_by_hs_code(items, total_packages=None)

        # Regroupement effectué mais pas de modification de quantité
        assert len(result) == 1
        # Quantité reste celle de l'article original
        assert result[0].tarification.supplementary_units[0].quantity == 100.0

    def test_item_without_hs_code(self):
        """Test avec article sans code HS valide"""
        # Créer un article sans tarification
        item_no_hs = Item()
        item_no_hs.packages = Package()
        item_no_hs.goods_description = "Article sans HS"

        items = [
            create_test_item("87032319", quantity=100.0),
            item_no_hs
        ]
        result = group_items_by_hs_code(items, total_packages=35.0)

        # 1 groupe HS valide + 1 article sans HS = 2 articles
        assert len(result) == 2

    def test_preserves_first_item_data(self):
        """Test que les données du premier article sont préservées"""
        items = [
            create_test_item("87032319", quantity=100.0),
            create_test_item("87032319", quantity=200.0),
            create_test_item("87032319", quantity=300.0)
        ]

        # Modifier la description du premier article
        items[0].goods_description = "First article description"

        result = group_items_by_hs_code(items, total_packages=35.0)

        assert len(result) == 1
        # Vérifier que c'est bien le premier article qui est gardé
        assert result[0].goods_description == "First article description"
        # Avec la quantité mise à jour
        assert result[0].tarification.supplementary_units[0].quantity == 35.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
