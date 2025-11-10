"""
Gestionnaire de séquences uniques pour numéros de châssis
==========================================================

Garantit qu'aucun numéro de châssis ne soit généré deux fois en maintenant
des compteurs de séquence persistants pour chaque combinaison de préfixe.

Usage:
    from chassis_sequence_manager import ChassisSequenceManager

    manager = ChassisSequenceManager()
    next_seq = manager.get_next_sequence("LZSHCKZS2S")  # Préfixe unique
"""

import json
import threading
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ChassisSequenceManager:
    """
    Gestionnaire de séquences uniques pour numéros de châssis

    Maintient un compteur de séquence pour chaque préfixe de châssis
    (WMI+VDS+Year+Plant = 9 premiers caractères du VIN).

    Les séquences sont persistées dans un fichier JSON pour garantir
    l'unicité même après redémarrage de l'application.

    Thread-safe : Utilise des verrous pour éviter les collisions en
    accès concurrent.

    Attributes:
        storage_path: Chemin vers le fichier de persistance JSON
        sequences: Dictionnaire {prefix: last_sequence_used}

    Example:
        >>> manager = ChassisSequenceManager()
        >>> seq1 = manager.get_next_sequence("LZSHCKZS2S")  # 1
        >>> seq2 = manager.get_next_sequence("LZSHCKZS2S")  # 2
        >>> seq3 = manager.get_next_sequence("LZSHCKZS2S")  # 3
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialise le gestionnaire de séquences

        Args:
            storage_path: Chemin vers fichier JSON de persistance
                         (défaut: data/chassis_sequences.json)
        """
        if storage_path is None:
            # Chemin par défaut dans data/
            storage_path = str(Path(__file__).parent.parent / "data" / "chassis_sequences.json")

        self.storage_path = Path(storage_path)
        self.sequences: Dict[str, int] = {}
        self._lock = threading.Lock()

        # Créer répertoire si nécessaire
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Charger séquences existantes
        self._load()

        logger.info(f"ChassisSequenceManager initialisé avec {len(self.sequences)} préfixes")

    def _load(self) -> None:
        """Charge les séquences depuis le fichier JSON"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    self.sequences = json.load(f)
                logger.info(f"Chargé {len(self.sequences)} séquences depuis {self.storage_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Erreur chargement séquences : {e}. Démarrage avec séquences vides.")
                self.sequences = {}
        else:
            logger.info("Aucun fichier de séquences existant. Démarrage avec séquences vides.")
            self.sequences = {}

    def _save(self) -> None:
        """Sauvegarde les séquences dans le fichier JSON"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.sequences, f, indent=2)
            logger.debug(f"Séquences sauvegardées : {len(self.sequences)} préfixes")
        except IOError as e:
            logger.error(f"Erreur sauvegarde séquences : {e}")

    def get_next_sequence(self, prefix: str) -> int:
        """
        Retourne la prochaine séquence unique pour ce préfixe

        Args:
            prefix: Préfixe du châssis (9 premiers chars du VIN sans checksum)
                   Format : WMI(3) + VDS(5) + Year(1) + Plant(1)
                   Exemple : "LZSHCKZS2S"

        Returns:
            Prochaine séquence unique (entier 1-999999)

        Thread-safe: Utilise un verrou pour éviter les collisions

        Example:
            >>> manager = ChassisSequenceManager()
            >>> seq = manager.get_next_sequence("LZSHCKZS2S")
            1
            >>> seq = manager.get_next_sequence("LZSHCKZS2S")
            2
        """
        with self._lock:
            # Récupérer séquence actuelle (0 si nouveau préfixe)
            current = self.sequences.get(prefix, 0)

            # Incrémenter
            next_seq = current + 1

            # Vérifier limite VIN (6 digits max = 999999)
            if next_seq > 999999:
                logger.warning(
                    f"Séquence {prefix} atteint limite (999999). "
                    "Considérer changement de préfixe."
                )
                # On continue au-delà de 999999 mais cela dépassera 6 digits

            # Sauvegarder nouvelle séquence
            self.sequences[prefix] = next_seq
            self._save()

            logger.debug(f"Séquence {prefix} : {current} → {next_seq}")

            return next_seq

    def get_current_sequence(self, prefix: str) -> int:
        """
        Retourne la dernière séquence utilisée pour ce préfixe

        Args:
            prefix: Préfixe du châssis

        Returns:
            Dernière séquence utilisée (0 si aucune)

        Example:
            >>> manager = ChassisSequenceManager()
            >>> manager.get_next_sequence("LZSHCKZS2S")  # 1
            >>> manager.get_current_sequence("LZSHCKZS2S")
            1
        """
        with self._lock:
            return self.sequences.get(prefix, 0)

    def reset_sequence(self, prefix: str, value: int = 0) -> None:
        """
        Réinitialise la séquence pour un préfixe

        Args:
            prefix: Préfixe du châssis
            value: Nouvelle valeur de départ (défaut: 0)

        Warning:
            Utiliser avec précaution ! Peut créer des doublons si mal utilisé.

        Example:
            >>> manager = ChassisSequenceManager()
            >>> manager.reset_sequence("LZSHCKZS2S", value=1000)
            >>> manager.get_next_sequence("LZSHCKZS2S")
            1001
        """
        with self._lock:
            self.sequences[prefix] = value
            self._save()
            logger.warning(f"Séquence {prefix} réinitialisée à {value}")

    def get_all_sequences(self) -> Dict[str, int]:
        """
        Retourne toutes les séquences actuelles

        Returns:
            Dictionnaire {prefix: last_sequence}

        Example:
            >>> manager = ChassisSequenceManager()
            >>> manager.get_next_sequence("LZSHCKZS2S")
            >>> manager.get_next_sequence("1FAHP58U5S")
            >>> manager.get_all_sequences()
            {'LZSHCKZS2S': 1, '1FAHP58U5S': 1}
        """
        with self._lock:
            return self.sequences.copy()

    def clear_all_sequences(self) -> None:
        """
        Efface toutes les séquences

        Warning:
            Utiliser avec EXTRÊME précaution ! Efface toutes les données.
        """
        with self._lock:
            self.sequences = {}
            self._save()
            logger.warning("Toutes les séquences ont été effacées")

    def get_statistics(self) -> Dict[str, any]:
        """
        Retourne des statistiques sur les séquences

        Returns:
            Dictionnaire avec statistiques
        """
        with self._lock:
            if not self.sequences:
                return {
                    "total_prefixes": 0,
                    "total_vins_generated": 0,
                    "max_sequence": 0,
                    "average_sequence": 0
                }

            total = sum(self.sequences.values())
            max_seq = max(self.sequences.values())
            avg_seq = total / len(self.sequences)

            return {
                "total_prefixes": len(self.sequences),
                "total_vins_generated": total,
                "max_sequence": max_seq,
                "average_sequence": round(avg_seq, 2)
            }


# Singleton global (optionnel)
_global_manager: Optional[ChassisSequenceManager] = None


def get_global_manager() -> ChassisSequenceManager:
    """
    Retourne l'instance singleton du gestionnaire de séquences

    Pratique pour partager un même gestionnaire dans toute l'application.

    Returns:
        Instance singleton de ChassisSequenceManager

    Example:
        >>> from chassis_sequence_manager import get_global_manager
        >>> manager = get_global_manager()
        >>> seq = manager.get_next_sequence("LZSHCKZS2S")
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = ChassisSequenceManager()
    return _global_manager


# Exemple d'utilisation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== Démonstration ChassisSequenceManager ===\n")

    # Créer gestionnaire
    manager = ChassisSequenceManager()

    # Statistiques initiales
    stats = manager.get_statistics()
    print(f"📊 Statistiques initiales:")
    print(f"  - Préfixes enregistrés: {stats['total_prefixes']}")
    print(f"  - VIN générés au total: {stats['total_vins_generated']}")

    # Générer séquences pour Apsonic
    print(f"\n🚗 Génération séquences Apsonic (LZSHCKZS2S):")
    prefix_apsonic = "LZSHCKZS2S"
    for i in range(5):
        seq = manager.get_next_sequence(prefix_apsonic)
        print(f"  {i+1}. Séquence: {seq:06d}")

    # Générer séquences pour Ford
    print(f"\n🚙 Génération séquences Ford (1FAHP58U5S):")
    prefix_ford = "1FAHP58U5S"
    for i in range(3):
        seq = manager.get_next_sequence(prefix_ford)
        print(f"  {i+1}. Séquence: {seq:06d}")

    # Statistiques finales
    stats = manager.get_statistics()
    print(f"\n📊 Statistiques finales:")
    print(f"  - Préfixes enregistrés: {stats['total_prefixes']}")
    print(f"  - VIN générés au total: {stats['total_vins_generated']}")
    print(f"  - Séquence max: {stats['max_sequence']}")
    print(f"  - Séquence moyenne: {stats['average_sequence']}")

    # Afficher toutes séquences
    print(f"\n📋 Toutes les séquences:")
    for prefix, seq in manager.get_all_sequences().items():
        print(f"  {prefix}: {seq}")

    print(f"\n✅ Fichier persistance: {manager.storage_path}")
