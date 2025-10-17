"""
Configuration centralisée du logging de sécurité
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler


def setup_security_logging(log_dir: str = "logs", log_level: int = logging.INFO):
    """
    Configure le logging de sécurité pour l'application

    Args:
        log_dir: Répertoire pour les fichiers de log
        log_level: Niveau de logging (DEBUG, INFO, WARNING, ERROR)
    """
    # Créer le répertoire de logs s'il n'existe pas
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Configuration du logger de sécurité
    security_logger = logging.getLogger('security')
    security_logger.setLevel(log_level)

    # Éviter la duplication si déjà configuré
    if security_logger.handlers:
        return security_logger

    # Format détaillé pour les logs de sécurité
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler pour fichier security.log avec rotation
    security_file = log_path / 'security.log'
    file_handler = RotatingFileHandler(
        security_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    security_logger.addHandler(file_handler)

    # Handler console (optionnel, utile pour développement)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Seulement warnings et erreurs en console
    console_handler.setFormatter(formatter)
    security_logger.addHandler(console_handler)

    return security_logger


def log_security_event(
    event_type: str,
    details: dict,
    severity: str = "INFO",
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    logger: Optional[logging.Logger] = None
):
    """
    Log un événement de sécurité

    Args:
        event_type: Type d'événement (auth_failure, path_traversal, etc.)
        details: Détails de l'événement
        severity: Niveau de sévérité (INFO, WARNING, ERROR, CRITICAL)
        user_id: Identifiant utilisateur (si applicable)
        ip_address: Adresse IP client
        logger: Logger à utiliser (par défaut: logger 'security')
    """
    if logger is None:
        logger = logging.getLogger('security')

    # Construire le message de log
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'user_id': user_id or 'anonymous',
        'ip_address': ip_address or 'unknown',
        'details': details
    }

    # Logger selon la sévérité
    log_method = getattr(logger, severity.lower(), logger.info)
    log_method(f"SECURITY_EVENT: {log_entry}")


# Types d'événements de sécurité prédéfinis
class SecurityEventTypes:
    """Constantes pour les types d'événements de sécurité"""

    # Authentification
    AUTH_SUCCESS = "authentication_success"
    AUTH_FAILURE = "authentication_failure"
    AUTH_MISSING = "authentication_missing"

    # Path Traversal
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    PATH_TRAVERSAL_BLOCKED = "path_traversal_blocked"

    # Uploads
    FILE_UPLOAD_SUCCESS = "file_upload_success"
    FILE_UPLOAD_REJECTED = "file_upload_rejected"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_TYPE_REJECTED = "file_type_rejected"

    # Téléchargements
    FILE_DOWNLOAD = "file_download"
    FILE_ACCESS_DENIED = "file_access_denied"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Erreurs système
    UNHANDLED_EXCEPTION = "unhandled_exception"
    CONFIGURATION_ERROR = "configuration_error"


# Logger global de sécurité (initialisé au démarrage de l'app)
security_logger = None


def get_security_logger() -> logging.Logger:
    """
    Retourne le logger de sécurité global

    Returns:
        Logger de sécurité configuré
    """
    global security_logger
    if security_logger is None:
        security_logger = setup_security_logging()
    return security_logger
