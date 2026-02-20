"""
Módulo de configuración para el servicio Nubefact.
Carga configuración desde BD y proporciona acceso a token, URL y timeouts.
"""

import logging
from typing import Optional
from asgiref.sync import sync_to_async
import httpx

from api_service.models import ApiService
from api_service.services.base.timeout_config import TimeoutConfig

logger = logging.getLogger(__name__)


class NubefactConfig:
    """
    Configuración para Nubefact, con soporte síncrono y asíncrono.
    """

    def __init__(self, timeout_config: Optional[TimeoutConfig] = None, _skip_load: bool = False):
        self.service = None
        self.base_url = None
        self.auth_token = None
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("NUBEFACT")

        if not _skip_load:
            self._load_sync()

    def _load_sync(self) -> None:
        """Carga síncrona desde BD."""
        try:
            self.service = ApiService.objects.get(name="NUBEFACT Perú")
            self.base_url = getattr(self.service, 'base_url', 'https://api.nubefact.com').rstrip('/')
            raw_token = getattr(self.service, 'auth_token', '')
            # Sanitizar token: eliminar espacios, saltos de línea y caracteres invisibles
            self.auth_token = raw_token.strip().replace('\n', '').replace('\r', '')
            if not self.base_url:
                raise ValueError("URL base no configurada para NUBEFACT Perú")
            if not self.auth_token:
                raise ValueError("Token no configurado para NUBEFACT Perú")
        except ApiService.DoesNotExist:
            raise ValueError("Servicio NUBEFACT Perú no existe en la base de datos")
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
            raise

    async def load_async(self) -> None:
        """Carga asíncrona desde BD."""
        try:
            self.service = await sync_to_async(ApiService.objects.get)(name="NUBEFACT Perú")
            self.base_url = getattr(self.service, 'base_url', 'https://api.nubefact.com').rstrip('/')
            raw_token = getattr(self.service, 'auth_token', '')
            self.auth_token = raw_token.strip().replace('\n', '').replace('\r', '')
            if not self.base_url:
                raise ValueError("URL base no configurada para NUBEFACT Perú")
            if not self.auth_token:
                raise ValueError("Token no configurado para NUBEFACT Perú")
        except ApiService.DoesNotExist:
            raise ValueError("Servicio NUBEFACT Perú no existe en la base de datos")
        except Exception as e:
            logger.error(f"Error cargando configuración asíncrona: {e}")
            raise

    @classmethod
    async def create(cls, timeout_config: Optional[TimeoutConfig] = None):
        """Factory asíncrono."""
        instance = cls(timeout_config, _skip_load=True)
        await instance.load_async()
        return instance

    def get_headers(self) -> dict:
        """Headers estándar para peticiones a Nubefact."""
        if not self.auth_token:
            raise ValueError("Configuración no cargada o token ausente")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

    def get_full_url(self, path: str) -> str:
        """Construye URL completa."""
        return f"{self.base_url}/{path.lstrip('/')}"

    @property
    def httpx_timeout(self) -> httpx.Timeout:
        return self.timeout_config.httpx_timeout

    @property
    def timeout_tuple(self) -> tuple:
        return self.timeout_config.as_tuple

    def get_retry_count(self) -> int:
        return self.timeout_config.max_retries

    def __repr__(self) -> str:
        return f"NubefactConfig(base_url={self.base_url}, timeout={self.timeout_config})"