# nubefact_service/config.py
"""
Módulo de configuración para el servicio Nubefact.

Carga la configuración desde el modelo ApiService en la base de datos,
asegurando que todas las credenciales estén presentes y válidas.

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
import os
import logging
from typing import Optional
from api_service.models import ApiService

logger = logging.getLogger(__name__)

# Configuración por defecto
DEFAULT_TIMEOUT = (30, 60)  # (connect_timeout, read_timeout) en segundos
MAX_RETRIES = 3


class NubefactConfig:
    """
    Carga y valida la configuración necesaria para acceder a la API de Nubefact.
    
    Sigue el patrón de MigoAPIService:
    - La configuración se obtiene del modelo ApiService con service_type='NUBEFACT'
    - Los endpoints específicos se cargan desde ApiEndpoint en tiempo de ejecución
    - Los valores se pueden sobrescribir con variables de entorno como fallback
    
    Attributes:
        service (ApiService): Instancia del servicio en la BD
        base_url (str): URL base de la API (solo base, sin paths)
        auth_token (str): Token de autenticación desde la BD o env
        timeout (tuple): Timeouts de conexión (connect, read)
        max_retries (int): Número máximo de reintentos
    
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
    
    def __init__(self, timeout: Optional[tuple] = None):
        """
        Inicializa la configuración de Nubefact.
        
        Args:
            timeout (tuple, optional): Tupla de (connect_timeout, read_timeout).
                                      Si no se proporciona, usa DEFAULT_TIMEOUT.
        """
        self.service = None
        self.base_url = None
        self.auth_token = None
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.max_retries = MAX_RETRIES
        
        self._load_config()
    
    def _load_config(self) -> None:
        """
        Carga la configuración desde ApiService en la base de datos.
        
        Patrón: Igual que MigoAPIService
        - Obtiene solo la URL base (sin paths)
        - Los paths vienen de ApiEndpoint
        - Rate limiting por endpoint desde BD
        
        Raises:
            ValueError: Si la configuración no existe o no tiene los valores requeridos
        """
        try:
            # Obtener configuración del servicio de la BD
            self.service = ApiService.objects.filter(
                service_type="NUBEFACT",
                is_active=True
            ).first()
            
            if not self.service:
                raise ValueError(
                    "Servicio NUBEFACT no configurado en la base de datos. "
                    "Por favor, crear un registro ApiService con service_type='NUBEFACT'"
                )
            
            # Obtener base URL (sin paths - similar a MigoAPIService)
            self.base_url = self.service.base_url or os.getenv('NUBEFACT_API_URL')
            
            # Obtener token de autenticación
            self.auth_token = self.service.auth_token or os.getenv('NUBEFACT_API_TOKEN')
            
            # Validar que base_url exista
            if not self.base_url:
                raise ValueError(
                    "URL base de Nubefact no configurada. "
                    "Establece ApiService.base_url o variable NUBEFACT_API_URL. "
                    "Nota: base_url debe ser SOLO la URL base (ej: https://api.nubefact.com), "
                    "los paths vienen de ApiEndpoint."
                )
            
            # Validar que token exista
            if not self.auth_token:
                raise ValueError(
                    "Token de Nubefact no configurado. "
                    "Establece ApiService.auth_token o variable NUBEFACT_API_TOKEN"
                )
            
            # Normalizar URL base (remover trailing slash)
            self.base_url = self.base_url.rstrip('/')
            
            logger.info(
                f"Configuración de Nubefact cargada correctamente. "
                f"Base URL: {self.base_url} | Endpoints: se cargan desde ApiEndpoint"
            )
            
        except ApiService.DoesNotExist:
            raise ValueError(
                "Servicio NUBEFACT no existe en la base de datos. "
                "Por favor, crear primero un registro ApiService."
            )
        except Exception as e:
            logger.error(f"Error cargando configuración de Nubefact: {str(e)}")
            raise
    
    def get_timeout(self) -> tuple:
        """
        Retorna la configuración de timeouts.
        
        Returns:
            tuple: (connect_timeout, read_timeout) en segundos
        """
        return self.timeout
    
    def get_retry_count(self) -> int:
        """
        Retorna el número de reintentos configurado.
        
        Returns:
            int: Número de reintentos máximos
        """
        return self.max_retries
    
    def __repr__(self) -> str:
        """Representación en string de la configuración."""
        return (
            f"NubefactConfig(base_url={self.base_url}, "
            f"token={'*' * 10}..., timeout={self.timeout})"
        )