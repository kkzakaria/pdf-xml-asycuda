#!/usr/bin/env python3
"""
Tests unitaires pour ChassisSequenceManager
===========================================

Teste le gestionnaire de séquences uniques pour garantir qu'aucun
numéro de châssis ne soit généré deux fois.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
import json
import tempfile
from chassis_sequence_manager import ChassisSequenceManager


class TestChassisSequenceManager:
    """Tests du gestionnaire de séquences"""

    @pytest.fixture
    def temp_storage(self):
        """Fixture pour fichier temporaire de persistance"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def manager(self, temp_storage):
        """Fixture manager avec stockage temporaire"""
        return ChassisSequenceManager(temp_storage)

    def test_initialization_empty(self, temp_storage):
        """Test initialisation avec fichier inexistant"""
        manager = ChassisSequenceManager(temp_storage)
        assert len(manager.sequences) == 0
        assert manager.storage_path == Path(temp_storage)

    def test_initialization_with_data(self, temp_storage):
        """Test initialisation avec données existantes"""
        # Créer fichier avec données
        initial_data = {
            "LZSHCKZS2": 100,
            "LFVBA01A5": 50
        }
        with open(temp_storage, 'w') as f:
            json.dump(initial_data, f)

        manager = ChassisSequenceManager(temp_storage)
        assert len(manager.sequences) == 2
        assert manager.sequences["LZSHCKZS2"] == 100
        assert manager.sequences["LFVBA01A5"] == 50

    def test_get_next_sequence_new_prefix(self, manager):
        """Test première séquence pour un nouveau préfixe"""
        seq = manager.get_next_sequence("LZSHCKZS2")
        assert seq == 1

    def test_get_next_sequence_increment(self, manager):
        """Test incrémentation de séquence"""
        seq1 = manager.get_next_sequence("LZSHCKZS2")
        seq2 = manager.get_next_sequence("LZSHCKZS2")
        seq3 = manager.get_next_sequence("LZSHCKZS2")

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    def test_get_next_sequence_multiple_prefixes(self, manager):
        """Test séquences indépendantes pour différents préfixes"""
        # Apsonic
        aps1 = manager.get_next_sequence("LZSHCKZS2")
        aps2 = manager.get_next_sequence("LZSHCKZS2")

        # Lifan
        lif1 = manager.get_next_sequence("LFVBA01A5")
        lif2 = manager.get_next_sequence("LFVBA01A5")

        # Haojue
        hao1 = manager.get_next_sequence("LBVGW02B7")

        assert aps1 == 1
        assert aps2 == 2
        assert lif1 == 1
        assert lif2 == 2
        assert hao1 == 1

    def test_persistence_after_save(self, temp_storage):
        """Test persistance des séquences après sauvegarde"""
        # Session 1
        manager1 = ChassisSequenceManager(temp_storage)
        manager1.get_next_sequence("LZSHCKZS2")
        manager1.get_next_sequence("LZSHCKZS2")
        manager1.get_next_sequence("LZSHCKZS2")

        # Session 2 (nouveau manager)
        manager2 = ChassisSequenceManager(temp_storage)
        seq = manager2.get_next_sequence("LZSHCKZS2")

        assert seq == 4  # Continue depuis 3

    def test_get_current_sequence(self, manager):
        """Test récupération séquence actuelle"""
        assert manager.get_current_sequence("LZSHCKZS2") == 0

        manager.get_next_sequence("LZSHCKZS2")
        assert manager.get_current_sequence("LZSHCKZS2") == 1

        manager.get_next_sequence("LZSHCKZS2")
        manager.get_next_sequence("LZSHCKZS2")
        assert manager.get_current_sequence("LZSHCKZS2") == 3

    def test_reset_sequence(self, manager):
        """Test réinitialisation de séquence"""
        manager.get_next_sequence("LZSHCKZS2")
        manager.get_next_sequence("LZSHCKZS2")
        assert manager.get_current_sequence("LZSHCKZS2") == 2

        manager.reset_sequence("LZSHCKZS2", value=0)
        assert manager.get_current_sequence("LZSHCKZS2") == 0

        seq = manager.get_next_sequence("LZSHCKZS2")
        assert seq == 1

    def test_reset_sequence_custom_value(self, manager):
        """Test réinitialisation avec valeur personnalisée"""
        manager.reset_sequence("LZSHCKZS2", value=1000)
        seq = manager.get_next_sequence("LZSHCKZS2")
        assert seq == 1001

    def test_get_all_sequences(self, manager):
        """Test récupération toutes séquences"""
        manager.get_next_sequence("LZSHCKZS2")
        manager.get_next_sequence("LFVBA01A5")
        manager.get_next_sequence("LZSHCKZS2")

        all_seq = manager.get_all_sequences()
        assert len(all_seq) == 2
        assert all_seq["LZSHCKZS2"] == 2
        assert all_seq["LFVBA01A5"] == 1

    def test_clear_all_sequences(self, manager):
        """Test effacement toutes séquences"""
        manager.get_next_sequence("LZSHCKZS2")
        manager.get_next_sequence("LFVBA01A5")
        assert len(manager.sequences) == 2

        manager.clear_all_sequences()
        assert len(manager.sequences) == 0

    def test_get_statistics_empty(self, manager):
        """Test statistiques sur manager vide"""
        stats = manager.get_statistics()
        assert stats["total_prefixes"] == 0
        assert stats["total_vins_generated"] == 0
        assert stats["max_sequence"] == 0
        assert stats["average_sequence"] == 0

    def test_get_statistics_with_data(self, manager):
        """Test statistiques avec données"""
        # Générer séquences
        for _ in range(50):
            manager.get_next_sequence("LZSHCKZS2")
        for _ in range(30):
            manager.get_next_sequence("LFVBA01A5")
        for _ in range(20):
            manager.get_next_sequence("LBVGW02B7")

        stats = manager.get_statistics()
        assert stats["total_prefixes"] == 3
        assert stats["total_vins_generated"] == 100
        assert stats["max_sequence"] == 50
        assert stats["average_sequence"] == 33.33

    def test_sequence_limit_warning(self, manager, caplog):
        """Test avertissement limite 999999"""
        # Définir séquence proche de la limite
        manager.reset_sequence("LZSHCKZS2", value=999998)

        # Générer 2 séquences (dépasse limite)
        seq1 = manager.get_next_sequence("LZSHCKZS2")
        seq2 = manager.get_next_sequence("LZSHCKZS2")

        assert seq1 == 999999
        assert seq2 == 1000000  # Dépasse limite mais continue

        # Vérifier avertissement dans logs
        assert "atteint limite" in caplog.text.lower()

    def test_thread_safety(self, manager):
        """Test thread-safety basique (structure)"""
        import threading

        def generate_sequences(prefix, count):
            for _ in range(count):
                manager.get_next_sequence(prefix)

        # Créer 10 threads générant 100 séquences chacun
        threads = []
        for i in range(10):
            t = threading.Thread(
                target=generate_sequences,
                args=("LZSHCKZS2", 100)
            )
            threads.append(t)
            t.start()

        # Attendre fin de tous les threads
        for t in threads:
            t.join()

        # Vérifier total
        assert manager.get_current_sequence("LZSHCKZS2") == 1000

    def test_json_file_format(self, temp_storage, manager):
        """Test format du fichier JSON"""
        manager.get_next_sequence("LZSHCKZS2")
        manager.get_next_sequence("LFVBA01A5")

        # Lire fichier JSON
        with open(temp_storage, 'r') as f:
            data = json.load(f)

        assert isinstance(data, dict)
        assert "LZSHCKZS2" in data
        assert "LFVBA01A5" in data
        assert isinstance(data["LZSHCKZS2"], int)


class TestChassisFactoryIntegration:
    """Tests d'intégration avec ChassisFactory"""

    @pytest.fixture
    def temp_storage(self):
        """Fixture pour fichier temporaire"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_factory_unique_mode_enabled(self, temp_storage):
        """Test factory avec mode unique activé"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )
        assert factory.sequence_manager is not None

    def test_factory_unique_mode_disabled(self):
        """Test factory avec mode unique désactivé"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(ensure_unique=False)
        assert factory.sequence_manager is None

    def test_create_unique_vin_basic(self, temp_storage):
        """Test création VIN unique"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )

        vin1 = factory.create_unique_vin("LZS", "HCKZS", 2028, "S")
        vin2 = factory.create_unique_vin("LZS", "HCKZS", 2028, "S")
        vin3 = factory.create_unique_vin("LZS", "HCKZS", 2028, "S")

        # Vérifier unicité
        assert vin1 != vin2 != vin3
        assert len({vin1, vin2, vin3}) == 3

        # Vérifier séquences consécutives
        seq1 = int(vin1[-6:])
        seq2 = int(vin2[-6:])
        seq3 = int(vin3[-6:])

        assert seq2 == seq1 + 1
        assert seq3 == seq2 + 1

    def test_create_unique_vin_batch(self, temp_storage):
        """Test création lot VIN uniques"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )

        batch = factory.create_unique_vin_batch("LZS", "HCKZS", 2028, "S", 50)

        # Vérifier quantité
        assert len(batch) == 50

        # Vérifier unicité
        assert len(set(batch)) == 50

        # Vérifier séquences consécutives
        for i in range(49):
            seq1 = int(batch[i][-6:])
            seq2 = int(batch[i+1][-6:])
            assert seq2 == seq1 + 1

    def test_unique_mode_without_init_raises(self):
        """Test erreur si mode unique non activé"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(ensure_unique=False)

        with pytest.raises(RuntimeError, match="ensure_unique=True"):
            factory.create_unique_vin("LZS", "HCKZS", 2028, "S")

    def test_persistence_across_factory_instances(self, temp_storage):
        """Test persistance entre instances factory"""
        from chassis_generator import ChassisFactory

        # Factory 1
        factory1 = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )
        vin1 = factory1.create_unique_vin("LZS", "HCKZS", 2028, "S")
        seq1 = int(vin1[-6:])

        # Factory 2 (nouveau)
        factory2 = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )
        vin2 = factory2.create_unique_vin("LZS", "HCKZS", 2028, "S")
        seq2 = int(vin2[-6:])

        # Séquence continue
        assert seq2 == seq1 + 1

    def test_get_sequence_statistics(self, temp_storage):
        """Test statistiques via factory"""
        from chassis_generator import ChassisFactory

        factory = ChassisFactory(
            ensure_unique=True,
            sequence_storage_path=temp_storage
        )

        factory.create_unique_vin_batch("LZS", "HCKZS", 2028, "S", 50)
        factory.create_unique_vin_batch("LFV", "BA01A", 2025, "S", 30)

        stats = factory.get_sequence_statistics()
        assert stats["total_prefixes"] == 2
        assert stats["total_vins_generated"] == 80


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
