from typing import Optional

from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.services.migo.migo_service import MigoAPIService
from .base.timeout_config import TimeoutConfig


class ServiceFactory:
    """Factory para crear instancias de servicios con configuración consistente."""

    _services = {
        "NUBEFACT": NubefactService,
        "MIGO": MigoAPIService,
    }

    @classmethod
    def get_service(cls, service_type: str, custom_timeout:  Optional[TimeoutConfig] = None):
        """
        Obtiene una instancia del servicio solicitado.
        
        Args:
            service_type: Tipo de servicio ("NUBEFACT", "MIGO", etc.)
            custom_timeout: Configuración de timeout personalizada (opcional)
        
        Returns:
            Instancia del servicio configurada
        """
        if service_type not in cls._services:
            raise ValueError(f"Servicio no soportado: {service_type}")

        service_class = cls._services[service_type]
        
        # Si se proporciona timeout personalizado, pasarlo al servicio
        if custom_timeout:
            return service_class(timeout_config=custom_timeout)
        
        return service_class()

    @classmethod
    def register_service(cls, service_type: str, service_class):
        """Registra un nuevo servicio en la factory."""
        cls._services[service_type] = service_class