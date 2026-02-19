# api_service/tests/test_timeout_config.py
import pytest
from unittest.mock import patch
from django.conf import settings
import httpx

from api_service.services.base.timeout_config import TimeoutConfig

# ✅ IMPORTANTE: NO importar fixtures de BD
# NO usar: from .conftest_db import setup_nubefact_service

class TestTimeoutConfig:
    """Tests para TimeoutConfig - NO necesita BD"""
    
    # ✅ No usar ningún fixture de BD

    def test_default_values(self):
        """Verificar valores por defecto"""
        config = TimeoutConfig()
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 30.0
        assert config.max_retries == 3

    def test_custom_values(self):
        """Verificar valores personalizados"""
        config = TimeoutConfig(
            connect_timeout=5.0,
            read_timeout=45.0,
            max_retries=5
        )
        assert config.connect_timeout == 5.0
        assert config.read_timeout == 45.0
        assert config.max_retries == 5

    @patch.object(settings, 'NUBEFACT_CONNECT_TIMEOUT', 8.0)
    @patch.object(settings, 'NUBEFACT_READ_TIMEOUT', 25.0)
    def test_from_settings_with_prefix(self):
        """Verificar carga desde settings con prefijo específico"""
        config = TimeoutConfig.from_settings("NUBEFACT")
        assert config.connect_timeout == 8.0
        assert config.read_timeout == 25.0

    @patch.object(settings, 'MIGO_CONNECT_TIMEOUT', 15.0)
    @patch.object(settings, 'MIGO_READ_TIMEOUT', 60.0)
    def test_from_settings_with_different_prefix(self):
        """Verificar carga con diferentes prefijos"""
        config = TimeoutConfig.from_settings("MIGO")
        assert config.connect_timeout == 15.0
        assert config.read_timeout == 60.0

    def test_from_settings_fallback(self):
        """Verificar valores por defecto cuando no hay settings"""
        config = TimeoutConfig.from_settings("SERVICIO_INEXISTENTE")
        assert config.connect_timeout == 10.0
        assert config.read_timeout == 30.0

    def test_httpx_timeout(self):
        """Verificar conversión a httpx.Timeout"""
        config = TimeoutConfig(connect_timeout=5.0, read_timeout=20.0)
        timeout = config.httpx_timeout
        assert timeout.connect == 5.0
        assert timeout.read == 20.0
        assert isinstance(timeout, httpx.Timeout)

    def test_as_tuple(self):
        """Verificar conversión a tupla"""
        config = TimeoutConfig(connect_timeout=5.0, read_timeout=20.0)
        connect, read = config.as_tuple
        assert connect == 5.0
        assert read == 20.0