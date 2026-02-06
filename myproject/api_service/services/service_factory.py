# api_service/services/service_factory.py
from nubefact.nubefact_service import NubefactService
from migo.migo_service import MigoAPIService


class ServiceFactory:
    """Factory para crear instancias de servicios."""

    _services = {
        "NUBEFACT": NubefactService,
        "MIGO": MigoAPIService,
        # Agrega más servicios aquí
    }

    @classmethod
    def get_service(cls, service_type: str):
        """Obtiene una instancia del servicio solicitado."""
        if service_type not in cls._services:
            raise ValueError(f"Servicio no soportado: {service_type}")

        return cls._services[service_type]()

    @classmethod
    def register_service(cls, service_type: str, service_class):
        """Registra un nuevo servicio en la factory."""
        cls._services[service_type] = service_class
