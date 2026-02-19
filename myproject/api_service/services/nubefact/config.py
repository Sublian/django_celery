# nubefact_service/config.py
"""
Módulo de configuración para el servicio Nubefact.
Versión async-friendly.

Carga la configuración desde el modelo ApiService en la base de datos,
asegurando que todas las credenciales estén presentes y válidas,
[NEW] TimeoutConfig para la gestión de timeouts.

Sigue el mismo patrón que MigoAPIService:
- base_url: URL base del servicio (sin paths)
- auth_token: Token de autenticación
- Endpoints específicos se obtienen de ApiEndpoint en la BD

Ejemplo:
    >>> config = NubefactConfig()
    >>> print(config.base_url)
    'https://api.nubefact.com'
    >>> print(config.service.base_url)
    'https://api.nubefact.com'

"""
import logging
import httpx
from typing import Optional
from asgiref.sync import sync_to_async

from api_service.models import ApiService
from api_service.services.base.timeout_config import TimeoutConfig

logger = logging.getLogger(__name__)


class NubefactConfig:
    """
    Carga y valida la configuración necesaria para acceder a la API de Nubefact.
    Soporta modo síncrono (tradicional) y asíncrono (con create()).

    Sigue el patrón de MigoAPIService:
    - La configuración se obtiene del modelo ApiService con service_type='NUBEFACT'
    - Los endpoints específicos se cargan desde ApiEndpoint en tiempo de ejecución
    - Los valores se pueden sobrescribir con variables de entorno como fallback

    Attributes:
        service (ApiService): Instancia del servicio en la BD
        base_url (str): URL base de la API (solo base, sin paths)
        auth_token (str): Token de autenticación desde la BD o env
        timeout (tuple): Timeouts de conexión (connect, read)

    Raises:
        ValueError: Si la configuración de Nubefact no existe o está incompleta

    Example:
        >>> config = NubefactConfig()
        >>> print(config.base_url)
        'https://api.nubefact.com'

        # Para obtener endpoints, NubefactService usa:
        >>> endpoint = NubefactService()._get_endpoint('emitir_comprobante')
        >>> print(endpoint.path)
        '/api/v1/send'
    """

    def __init__(self, timeout_config: Optional[TimeoutConfig] = None, _skip_load: bool = False):
        """
        Inicializa la configuración de Nubefact.

        Args:
            timeout_config: Configuración de timeout personalizada
            _skip_load: Flag interno para evitar carga automática (usado por create)
        """
        self.service = None
        self.base_url = None
        self.auth_token = None
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("NUBEFACT")

        # self._load_config()
        # Solo cargar configuración si no estamos en modo especial
        if not _skip_load:
            self._load_config_sync()
            
    def _load_config_sync(self) -> None:
        """
        Carga la configuración desde ApiService (versión síncrona).
        Para compatibilidad con código existente.
        """
        try:
            self.service = ApiService.objects.get(name="NUBEFACT Perú")

            self.base_url = getattr(self.service, 'base_url', 'https://api.nubefact.com')
            self.auth_token = getattr(self.service, 'auth_token', None)

            if not self.base_url:
                raise ValueError("URL base de Nubefact no configurada.")

            if not self.auth_token:
                raise ValueError("Token de Nubefact no configurado.")

            self.base_url = self.base_url.rstrip("/")

        except ApiService.DoesNotExist:
            raise ValueError(
                "Servicio NUBEFACT no existe en la base de datos. "
                "Por favor, crear primero un registro ApiService."
            )
        except Exception as e:
            logger.error(f"Error cargando configuración de Nubefact: {str(e)}")
            raise

    async def load_config(self) -> None:
        """
        Carga la configuración desde ApiService (versión asíncrona).
        Para usar con el factory method create().
        """
        try:
            # ✅ Usar sync_to_async para consulta a BD
            self.service = await sync_to_async(ApiService.objects.get)(name="NUBEFACT Perú")

            self.base_url = getattr(self.service, 'base_url', 'https://api.nubefact.com')
            self.auth_token = getattr(self.service, 'auth_token', None)

            if not self.base_url:
                raise ValueError("URL base de Nubefact no configurada.")

            if not self.auth_token:
                raise ValueError("Token de Nubefact no configurado.")

            self.base_url = self.base_url.rstrip("/")

        except ApiService.DoesNotExist:
            raise ValueError(
                "Servicio NUBEFACT no existe en la base de datos. "
                "Por favor, crear primero un registro ApiService."
            )
        except Exception as e:
            logger.error(f"Error cargando configuración asíncrona de Nubefact: {str(e)}")
            raise
        
    @classmethod
    async def create(cls, timeout_config: Optional[TimeoutConfig] = None):
        """
        Factory method asíncrono para crear y cargar configuración.
        
        Args:
            timeout_config: Configuración de timeout personalizada
        
        Returns:
            Instancia de NubefactConfig completamente inicializada
        """
        # Crear instancia sin cargar configuración automáticamente
        instance = cls(timeout_config, _skip_load=True)
        # Cargar configuración de forma asíncrona
        await instance.load_config()
        return instance
    
    @property
    def timeout(self) -> tuple:
        """Compatibilidad con código existente."""
        return self.timeout_config.as_tuple
    
    def get_httpx_timeout(self) -> httpx.Timeout:
        """Timeout en formato httpx."""
        return self.timeout_config.httpx_timeout

    def get_retry_count(self) -> int:
        """
        Retorna el número de reintentos configurado.

        Returns:
            int: Número de reintentos máximos
        """
        return self.timeout_config.max_retries

    def __repr__(self) -> str:
        """Representación en string de la configuración."""
        return (
            f"NubefactConfig(base_url={self.base_url}, "
            f"token={'*' * 10}..., timeout={self.timeout_config})"
        )
