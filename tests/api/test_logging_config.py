"""
Tests unitaires pour la configuration centralisée du logging
"""
import logging
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from api.core.logging_config import configure_logging


class FakeSettings:
    """Settings minimal pour les tests de logging"""

    def __init__(self, **kwargs):
        defaults = {
            'log_level': 'INFO',
            'log_dir': 'test_logs',
            'log_to_file': True,
            'log_format': 'standard',
            'log_max_bytes': 10 * 1024 * 1024,
            'log_backup_count': 5,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


@pytest.fixture(autouse=True)
def cleanup_test_logs():
    """Nettoyer le répertoire de logs de test après chaque test"""
    yield
    shutil.rmtree('test_logs', ignore_errors=True)


class TestConfigureLogging:
    """Tests pour configure_logging()"""

    def test_default_settings_no_error(self):
        """dictConfig s'exécute sans erreur avec les settings par défaut"""
        settings = FakeSettings()
        configure_logging(settings)

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_debug_level_propagated(self):
        """Le niveau DEBUG est bien appliqué au root logger"""
        settings = FakeSettings(log_level='DEBUG')
        configure_logging(settings)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_log_to_file_creates_directory(self):
        """log_to_file=True crée le répertoire de logs"""
        settings = FakeSettings(log_to_file=True)
        configure_logging(settings)

        assert Path('test_logs').is_dir()

    def test_log_to_file_false_no_app_log(self):
        """log_to_file=False ne crée pas app.log (security.log est toujours créé)"""
        settings = FakeSettings(log_to_file=False)
        configure_logging(settings)

        assert not (Path('test_logs') / 'app.log').exists()

    def test_log_to_file_creates_file_handler(self):
        """log_to_file=True ajoute un handler fichier au root logger"""
        settings = FakeSettings(log_to_file=True)
        configure_logging(settings)

        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert 'RotatingFileHandler' in handler_types

    def test_log_to_file_false_no_file_handler(self):
        """log_to_file=False ne crée pas de handler fichier"""
        settings = FakeSettings(log_to_file=False)
        configure_logging(settings)

        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert 'RotatingFileHandler' not in handler_types

    def test_console_handler_always_present(self):
        """Le handler console est toujours présent"""
        settings = FakeSettings(log_to_file=False)
        configure_logging(settings)

        root = logging.getLogger()
        handler_types = [type(h).__name__ for h in root.handlers]
        assert 'StreamHandler' in handler_types

    def test_detailed_format(self):
        """Le format 'detailed' est utilisable sans erreur"""
        settings = FakeSettings(log_format='detailed')
        configure_logging(settings)

        root = logging.getLogger()
        assert root.level == logging.INFO

    def test_security_logger_level_propagated(self):
        """Le log_level est propagé au security logger"""
        settings = FakeSettings(log_level='DEBUG', log_to_file=True)
        configure_logging(settings)

        security = logging.getLogger('security')
        assert security.level == logging.DEBUG

    def test_third_party_loggers_silenced(self):
        """Les loggers tiers sont configurés en WARNING"""
        settings = FakeSettings()
        configure_logging(settings)

        assert logging.getLogger('uvicorn.access').level == logging.WARNING
        assert logging.getLogger('httpx').level == logging.WARNING
        assert logging.getLogger('pdfplumber').level == logging.WARNING


class TestLogLevelValidation:
    """Tests pour la validation du log_level dans Settings"""

    def test_valid_log_levels(self):
        """Les niveaux valides sont acceptés"""
        from api.core.config import Settings
        import os

        for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            os.environ['API_LOG_LEVEL'] = level
            s = Settings()
            assert s.log_level == level
            del os.environ['API_LOG_LEVEL']

    def test_log_level_case_insensitive(self):
        """Le log_level est normalisé en majuscule"""
        from api.core.config import Settings
        import os

        os.environ['API_LOG_LEVEL'] = 'debug'
        s = Settings()
        assert s.log_level == 'DEBUG'
        del os.environ['API_LOG_LEVEL']

    def test_invalid_log_level_raises(self):
        """Un niveau invalide lève une ValueError"""
        from api.core.config import Settings
        from pydantic import ValidationError
        import os

        os.environ['API_LOG_LEVEL'] = 'VERBOSE'
        with pytest.raises(ValidationError):
            Settings()
        del os.environ['API_LOG_LEVEL']

    def test_invalid_log_format_raises(self):
        """Un format invalide lève une ValueError"""
        from api.core.config import Settings
        from pydantic import ValidationError
        import os

        os.environ['API_LOG_FORMAT'] = 'json'
        with pytest.raises(ValidationError):
            Settings()
        del os.environ['API_LOG_FORMAT']

    def test_invalid_uvicorn_level_raises(self):
        """Un niveau uvicorn invalide lève une ValueError"""
        from api.core.config import Settings
        from pydantic import ValidationError
        import os

        os.environ['API_LOG_UVICORN_LEVEL'] = 'verbose'
        with pytest.raises(ValidationError):
            Settings()
        del os.environ['API_LOG_UVICORN_LEVEL']
