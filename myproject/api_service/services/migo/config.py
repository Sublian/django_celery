"""
Módulo de configuración para el servicio Migo.
"""

import logging
from typing import Optional
from api_service.models import ApiService
from api_service.services.base.timeout_config import TimeoutConfig

logger = logging.getLogger(__name__)


class MigoConfig:
    """
    Configuración para el servicio Migo.
    """

    def __init__(self, timeout_config: Optional[TimeoutConfig] = None):
        self.service = None
        self.base_url = None
        self.auth_token = None
        # Migo usa su propio prefijo en settings
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("MIGO")
        
        self._load_config()

    def _load_config(self) -> None:
        """Carga configuración específica de Migo."""
        # Similar a NubefactConfig pero con su propio service_type
        pass