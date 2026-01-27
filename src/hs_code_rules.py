"""
Règles de nomenclature HS pour identification des marchandises
nécessitant des numéros de châssis

Liste officielle des codes HS (4 premiers chiffres) nécessitant OBLIGATOIREMENT un châssis:
- 8701: Tracteurs
- 8702: Véhicules pour transport de personnes (≥10 places)
- 8703: Voitures automobiles
- 8704: Véhicules pour transport de marchandises (camions, tricycles)
- 8705: Véhicules à usages spéciaux
- 8711: Motocycles, cyclomoteurs et cycles équipés d'un moteur auxiliaire
- 8427: Chariots de manutention automoteurs
- 8429: Bulldozers, niveleuses, scrapers, pelles mécaniques, excavateurs
- 8716: Remorques et semi-remorques

Note: Les marchandises avec numéro de série ou IMEI (électronique)
sont traitées comme des marchandises ordinaires (pas de traitement spécial).
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class HSCodeAnalyzer:
    """Analyseur de codes HS pour détection de châssis obligatoires"""

    # Liste officielle: Codes HS nécessitant OBLIGATOIREMENT un châssis
    CHASSIS_REQUIRED_CHAPTERS = {
        '8701': 'Tracteurs',
        '8702': 'Véhicules transport personnes ≥10',
        '8703': 'Voitures automobiles',
        '8704': 'Véhicules transport marchandises',
        '8705': 'Véhicules à usages spéciaux',
        '8711': 'Motocycles et cyclomoteurs',
        '8427': 'Chariots de manutention',
        '8429': 'Engins de travaux publics',
        '8716': 'Remorques et semi-remorques',
    }

    # Mots-clés pour détection fallback (si code HS absent/invalide)
    VEHICLE_KEYWORDS = [
        'MOTORCYCLE', 'MOTO', 'MOTOCYCLE', 'SCOOTER',
        'TRICYCLE', 'TRIPORTEUR', 'THREE WHEEL',
        'VEHICLE', 'VEHICULE', 'VOITURE', 'CAR', 'AUTOMOBILE',
        'TRUCK', 'CAMION', 'LORRY',
        'TRACTOR', 'TRACTEUR',
        'BUS', 'AUTOCAR', 'COACH',
        'BULLDOZER', 'EXCAVATEUR', 'CHARIOT'
    ]

    # Mots-clés spécifiques pour motos (code document 6122)
    MOTORCYCLE_KEYWORDS = [
        'MOTORCYCLE', 'MOTO', 'MOTOCYCLE', 'SCOOTER',
        'CYCLOMOTEUR', 'MOTOBIKE', 'BIKE'
    ]

    @staticmethod
    def requires_chassis(hs_code: Optional[str], description: str = '') -> Dict[str, any]:
        """
        Détermine si une marchandise nécessite un numéro de châssis

        Args:
            hs_code: Code HS (format: "87043119" ou "8704.31.19.90")
            description: Description de la marchandise (optionnel, pour fallback)

        Returns:
            {
                'required': bool,      # True si châssis requis
                'confidence': float,   # 0.0-1.0 (niveau de confiance)
                'source': str,         # 'hs_code', 'keywords', 'none'
                'category': str        # Nom de la catégorie de véhicule
            }
        """
        # Cas 1: Code HS fourni et valide
        if hs_code:
            # Nettoyer le code HS (enlever points, espaces)
            hs_clean = str(hs_code).replace('.', '').replace(' ', '').strip()

            if len(hs_clean) >= 4:
                # Extraire chapitre (4 premiers chiffres)
                chapter = hs_clean[:4]

                if chapter in HSCodeAnalyzer.CHASSIS_REQUIRED_CHAPTERS:
                    category = HSCodeAnalyzer.CHASSIS_REQUIRED_CHAPTERS[chapter]
                    logger.debug(f"Code HS {chapter} identifié: {category} - Châssis REQUIS")
                    return {
                        'required': True,
                        'confidence': 1.0,
                        'source': 'hs_code',
                        'category': category
                    }
                else:
                    # Code HS valide mais pas dans la liste
                    logger.debug(f"Code HS {chapter} - Pas de châssis requis")
                    return {
                        'required': False,
                        'confidence': 1.0,
                        'source': 'hs_code',
                        'category': 'Marchandise générale'
                    }

        # Cas 2: Fallback sur mots-clés si code HS absent/invalide
        if description:
            desc_upper = description.upper()

            for keyword in HSCodeAnalyzer.VEHICLE_KEYWORDS:
                if keyword in desc_upper:
                    logger.warning(
                        f"Châssis détecté par mot-clé '{keyword}' dans description "
                        f"(confiance: 70%) - Code HS manquant ou invalide"
                    )
                    return {
                        'required': True,
                        'confidence': 0.7,
                        'source': 'keywords',
                        'category': f'Véhicule (détection: {keyword})'
                    }

        # Cas 3: Aucune détection
        return {
            'required': False,
            'confidence': 0.8,
            'source': 'none',
            'category': 'Marchandise générale'
        }

    @staticmethod
    def get_chassis_document_code(hs_code: Optional[str], description: str = '') -> str:
        """
        Détermine le code de document ASYCUDA pour les véhicules avec châssis

        Règle:
        - Code 6122: Motos (HS 8711)
        - Code 6022: Tricycles et autres véhicules (tous les autres codes HS véhicules)

        Args:
            hs_code: Code HS (format: "87113019" ou "8711.30.19.00")
            description: Description de la marchandise (fallback si HS absent)

        Returns:
            '6122' pour motos, '6022' pour autres véhicules

        Examples:
            >>> get_chassis_document_code('87113019', 'MOTORCYCLE')
            '6122'
            >>> get_chassis_document_code('87042110', 'TRICYCLE')
            '6022'
            >>> get_chassis_document_code(None, 'MOTO YAMAHA')
            '6122'
            >>> get_chassis_document_code(None, 'TRICYCLE AP150ZH')
            '6022'
        """
        # Méthode 1: Détection par code HS (priorité)
        if hs_code:
            hs_clean = str(hs_code).replace('.', '').replace(' ', '').strip()
            if len(hs_clean) >= 4:
                chapter = hs_clean[:4]
                # Code HS 8711 = Motocycles → code document 6122
                if chapter == '8711':
                    logger.debug(f"Code HS {chapter} détecté → Code document 6122 (MOTOS)")
                    return '6122'
                # Tous les autres codes HS véhicules → code document 6022
                elif chapter in HSCodeAnalyzer.CHASSIS_REQUIRED_CHAPTERS:
                    logger.debug(f"Code HS {chapter} détecté → Code document 6022 (VÉHICULES)")
                    return '6022'

        # Méthode 2: Fallback sur mots-clés dans description
        if description:
            desc_upper = description.upper()
            # Vérifier mots-clés motos en premier (plus spécifique)
            for keyword in HSCodeAnalyzer.MOTORCYCLE_KEYWORDS:
                if keyword in desc_upper:
                    logger.warning(
                        f"Mot-clé moto '{keyword}' détecté → Code document 6122 "
                        f"(fallback - code HS absent ou invalide)"
                    )
                    return '6122'

        # Par défaut: code 6022 (tricycles et autres véhicules)
        logger.debug("Aucun code HS moto détecté → Code document 6022 par défaut (VÉHICULES)")
        return '6022'

    @staticmethod
    def get_chassis_info() -> Dict[str, str]:
        """
        Retourne la liste complète des codes HS nécessitant un châssis

        Returns:
            Dictionnaire {code_hs: description}
        """
        return HSCodeAnalyzer.CHASSIS_REQUIRED_CHAPTERS.copy()
