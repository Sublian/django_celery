"""
Configuración genérica de timeouts para servicios API.

Esta clase puede ser utilizada por cualquier servicio (NubeFact, Migo, etc.)
para manejar timeouts y reintentos de manera consistente.

Los valores se cargan desde settings de Django usando un prefijo específico
para cada servicio.
"""

from typing import Optional, Tuple, TypeVar, Generic
from dataclasses import dataclass
from django.conf import settings
import httpx

T = TypeVar("T")  # Para tipo genérico del servicio


@dataclass
class TimeoutConfig:
    """
    Configuración de timeouts y reintentos para servicios API.

    Attributes:
        connect_timeout: Tiempo máximo para establecer conexión (segundos)
        read_timeout: Tiempo máximo para leer respuesta (segundos)
        write_timeout: Tiempo máximo para enviar datos (segundos)
        pool_timeout: Tiempo máximo para esperar conexión del pool (segundos)
        max_retries: Número máximo de reintentos en caso de timeout/error
        retry_on_timeout: Si se deben reintentar errores de timeout

    Example:
        >>> # Para NubeFact
        >>> nubefact_timeout = TimeoutConfig.from_settings("NUBEFACT")
        >>>
        >>> # Para Migo
        >>> migo_timeout = TimeoutConfig.from_settings("MIGO")
    """

    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    write_timeout: float = 10.0
    pool_timeout: float = 5.0
    max_retries: int = 3
    retry_on_timeout: bool = True

    @classmethod
    def from_settings(cls, service_prefix: str) -> "TimeoutConfig":
        """
        Carga configuración desde settings de Django.

        Args:
            service_prefix: Prefijo para las variables en settings
                          (ej: "NUBEFACT", "MIGO", "OTRO_SERVICIO")

        Returns:
            Instancia de TimeoutConfig con valores específicos del servicio

        Example:
            >>> # En settings.py:
            >>> NUBEFACT_READ_TIMEOUT = 30.0
            >>> MIGO_READ_TIMEOUT = 60.0  # Migo es más lento
            >>>
            >>> config = TimeoutConfig.from_settings("NUBEFACT")
        """
        return cls(
            connect_timeout=getattr(
                settings, f"{service_prefix}_CONNECT_TIMEOUT", 10.0
            ),
            read_timeout=getattr(settings, f"{service_prefix}_READ_TIMEOUT", 30.0),
            write_timeout=getattr(settings, f"{service_prefix}_WRITE_TIMEOUT", 10.0),
            pool_timeout=getattr(settings, f"{service_prefix}_POOL_TIMEOUT", 5.0),
            max_retries=getattr(settings, f"{service_prefix}_MAX_RETRIES", 3),
            retry_on_timeout=getattr(
                settings, f"{service_prefix}_RETRY_ON_TIMEOUT", True
            ),
        )

    @property
    def httpx_timeout(self) -> httpx.Timeout:
        """Timeout en formato httpx."""
        return httpx.Timeout(
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=self.write_timeout,
            pool=self.pool_timeout,
        )

    @property
    def as_tuple(self) -> Tuple[float, float]:
        """Timeouts como tupla (connect, read) para compatibilidad."""
        return (self.connect_timeout, self.read_timeout)

    def __repr__(self) -> str:
        return (
            f"TimeoutConfig("
            f"connect={self.connect_timeout}s, "
            f"read={self.read_timeout}s, "
            f"retries={self.max_retries})"
        )
