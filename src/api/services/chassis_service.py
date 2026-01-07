"""
Service de génération de VINs ISO 3779
Génération indépendante sans PDF RFCV
"""
import sys
import json
import csv
import io
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Ajouter src au path pour imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from chassis_generator import ChassisFactory, VINGenerator


class ChassisService:
    """Service de génération de VINs ISO 3779 indépendant"""

    def __init__(self):
        """Initialise le service avec la factory de châssis"""
        self.factory = ChassisFactory(ensure_unique=True)

    def generate_vins(
        self,
        quantity: int,
        wmi: str,
        vds: str = "HCKZS",
        year: int = 2025,
        plant_code: str = "S"
    ) -> Dict[str, Any]:
        """
        Génère une liste de VINs ISO 3779 uniques

        Args:
            quantity: Nombre de VINs à générer (1-10000)
            wmi: World Manufacturer Identifier (3 caractères)
            vds: Vehicle Descriptor Section (5 caractères)
            year: Année modèle (2001-2030)
            plant_code: Code usine (1 caractère)

        Returns:
            Dictionnaire avec VINs générés et métadonnées
        """
        # Construire le préfixe pour tracking séquence
        year_code = VINGenerator.YEAR_CODES.get(year, "S")
        prefix = f"{wmi}{vds}{year_code}"

        # Récupérer séquence de départ
        start_sequence = self.factory.sequence_manager.get_current_sequence(prefix) + 1

        # Générer les VINs
        vins = self.factory.create_unique_vin_batch(
            wmi=wmi,
            vds=vds,
            year=year,
            plant=plant_code,
            quantity=quantity
        )

        end_sequence = start_sequence + quantity - 1

        return {
            "success": True,
            "vins": vins,
            "quantity_generated": len(vins),
            "wmi": wmi,
            "vds": vds,
            "year": year,
            "plant_code": plant_code,
            "prefix": prefix,
            "start_sequence": start_sequence,
            "end_sequence": end_sequence,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }

    def export_to_json(self, generation_result: Dict[str, Any]) -> str:
        """
        Exporte les VINs générés en format JSON

        Args:
            generation_result: Résultat de generate_vins()

        Returns:
            String JSON formaté
        """
        output = {
            "success": generation_result["success"],
            "vins": generation_result["vins"],
            "metadata": {
                "quantity": generation_result["quantity_generated"],
                "wmi": generation_result["wmi"],
                "vds": generation_result["vds"],
                "year": generation_result["year"],
                "plant_code": generation_result["plant_code"],
                "prefix": generation_result["prefix"],
                "start_sequence": generation_result["start_sequence"],
                "end_sequence": generation_result["end_sequence"],
                "generated_at": generation_result["generated_at"]
            }
        }
        return json.dumps(output, indent=2, ensure_ascii=False)

    def export_to_csv(self, generation_result: Dict[str, Any]) -> str:
        """
        Exporte les VINs générés en format CSV

        Args:
            generation_result: Résultat de generate_vins()

        Returns:
            String CSV
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # En-tête
        writer.writerow(["index", "vin", "wmi", "vds", "year", "plant_code", "sequence"])

        # Données
        start_seq = generation_result["start_sequence"]
        for i, vin in enumerate(generation_result["vins"]):
            writer.writerow([
                i + 1,
                vin,
                generation_result["wmi"],
                generation_result["vds"],
                generation_result["year"],
                generation_result["plant_code"],
                start_seq + i
            ])

        return output.getvalue()

    def export_to_text(self, generation_result: Dict[str, Any]) -> str:
        """
        Exporte les VINs générés en format texte simple (un VIN par ligne)

        Args:
            generation_result: Résultat de generate_vins()

        Returns:
            String avec un VIN par ligne
        """
        header = f"""# VINs générés le {generation_result['generated_at']}
# Quantité: {generation_result['quantity_generated']}
# WMI: {generation_result['wmi']} | VDS: {generation_result['vds']} | Année: {generation_result['year']}
# Séquences: {generation_result['start_sequence']} à {generation_result['end_sequence']}
# =========================================================

"""
        vins_text = "\n".join(generation_result["vins"])
        return header + vins_text

    def get_sequences_status(self) -> Dict[str, Any]:
        """
        Récupère l'état actuel des séquences de VINs

        Returns:
            Dictionnaire avec statistiques des séquences
        """
        return self.factory.get_sequence_statistics()


# Instance singleton pour l'API
chassis_service = ChassisService()
