"""
Configuration FastAPI pour l'API de conversion PDF RFCV → XML ASYCUDA
"""
import warnings
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List

# Import version from package __init__.py (single source of truth)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src import __version__ as package_version


class Settings(BaseSettings):
    """Configuration de l'application API"""

    # API Configuration
    api_title: str = "API Convertisseur PDF RFCV → XML ASYCUDA"
    version: str = package_version  # Version depuis src/__init__.py (single source of truth)
    api_description: str = """
API REST pour convertir les documents PDF RFCV (Rapport Final de Contrôle et de Vérification)
en fichiers XML compatibles ASYCUDA (Automated System for Customs Data) pour les douanes ivoiriennes.

## Fonctionnalités principales

### 🚗 Génération automatique de châssis VIN (v2.1)
- **VIN ISO 3779**: Génération de numéros de châssis conformes (17 caractères avec checksum)
- **Unicité garantie**: Persistance des séquences pour éviter les doublons
- **Personnalisation**: WMI, VDS, année de fabrication, code d'usine configurables
- **Limitation**: Contrôle du nombre de VIN générés par conversion

### 📄 Conversion de documents
- **Extraction PDF**: Analyse automatique des sections RFCV (24 sections)
- **Validation**: Vérification de la conformité des données extraites
- **XML ASYCUDA**: Génération XML compatible avec le système douanier

### 🔍 Détection de châssis
- **Codes HS**: Identification automatique des véhicules (8701-8716, 8427, 8429)
- **Patterns**: Extraction des VIN et numéros de châssis existants
- **Validation**: Vérification format ISO 3779 (17 caractères, pas de I/O/Q)

### ⚖️ Calculs douaniers
- **Assurance**: Formule douanière avec taux de change variable
- **Répartition proportionnelle**: Distribution des montants globaux par article
- **Regroupement**: Consolidation des articles par code HS

### 🔄 Traitement batch
- **Parallélisation**: Traitement concurrent avec workers configurables
- **Configuration par fichier**: Taux douaniers et configs châssis individuels
- **Rapports**: Génération de rapports JSON/CSV/Markdown

## Authentification

Tous les endpoints nécessitent une clé API dans le header `X-API-Key`.
Pour obtenir une clé, contactez l'administrateur du service.
"""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Security Configuration
    keys: str = ""  # Clés API séparées par virgules (ex: "key1,key2,key3") - Pydantic charge depuis API_KEYS
    require_authentication: bool = True  # Requiert authentification par défaut

    # CORS Configuration - SÉCURISÉ PAR DÉFAUT
    cors_origins: List[str] = []  # VIDE par défaut = pas d'origines autorisées
    cors_allow_credentials: bool = False  # Désactivé par défaut pour sécurité
    cors_allow_methods: List[str] = ["GET", "POST"]  # Méthodes spécifiques seulement
    cors_allow_headers: List[str] = ["Content-Type", "X-API-Key"]  # Headers spécifiques

    # File Storage
    upload_dir: str = "uploads"
    output_dir: str = "output"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: List[str] = [".pdf"]

    # Job Management
    job_expiry_hours: int = 24
    cleanup_interval_hours: int = 6

    # Batch Processing
    default_workers: int = 4
    max_workers: int = 8

    # Rate Limiting
    rate_limit_enabled: bool = True  # Activé par défaut
    rate_limit_default: str = "60/minute"
    rate_limit_upload: str = "10/minute"
    rate_limit_batch: str = "5/hour"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_",
        case_sensitive=False,
        extra='ignore'  # Ignorer les champs extra dans .env
    )

    @field_validator('cors_origins')
    def validate_cors_origins(cls, v):
        """
        Valide la configuration CORS et émet des warnings si non sécurisée

        Args:
            v: Liste des origines CORS

        Returns:
            Liste validée
        """
        if "*" in v:
            if len(v) > 1:
                raise ValueError(
                    "Configuration CORS invalide: ne peut pas mélanger '*' avec des origines spécifiques"
                )
            warnings.warn(
                "⚠️  ATTENTION SÉCURITÉ: CORS configuré pour toutes les origines ('*'). "
                "Ceci n'est PAS recommandé en production. "
                "Définir API_CORS_ORIGINS avec des domaines spécifiques.",
                UserWarning,
                stacklevel=2
            )
        return v

    @field_validator('require_authentication')
    def validate_authentication(cls, v):
        """
        Avertir si l'authentification est désactivée

        Args:
            v: Valeur require_authentication

        Returns:
            Valeur validée
        """
        if not v:
            warnings.warn(
                "⚠️  ATTENTION SÉCURITÉ: Authentification désactivée. "
                "L'API est accessible publiquement sans restriction. "
                "Ceci est DANGEREUX en production.",
                UserWarning,
                stacklevel=2
            )
        return v

    @field_validator('keys')
    def validate_api_keys(cls, v, values):
        """
        Valide que des clés API sont configurées si auth requise

        Args:
            v: Clés API
            values: Autres valeurs de config

        Returns:
            Clés validées
        """
        # Note: avec Pydantic v2, values n'est plus disponible dans field_validator
        # On ne peut donc pas valider la cohérence avec require_authentication ici
        # Cette validation sera faite au runtime dans security.py
        if v:
            api_keys = [k.strip() for k in v.split(',') if k.strip()]
            if any(len(key) < 16 for key in api_keys):
                warnings.warn(
                    "⚠️  ATTENTION SÉCURITÉ: Certaines clés API sont trop courtes (<16 caractères). "
                    "Utiliser des clés longues et aléatoires générées avec secrets.token_urlsafe(32)",
                    UserWarning,
                    stacklevel=2
                )
        return v


# Instance globale
settings = Settings()
