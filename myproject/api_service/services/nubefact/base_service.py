# api_service/services/base_service.py
import logging
from abc import ABC, abstractmethod
from django.conf import settings
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

class BaseAPIService(ABC):
    """Clase base abstracta para todos los servicios de API."""
    
    def __init__(self, service_type: str):
        self.service_type = service_type
        self.service_config = None
        self._load_config()
    
    def _load_config(self):
        """Carga la configuración del servicio desde la base de datos."""
        try:
            from api_service.models import ApiService
            
            self.service_config = ApiService.objects.filter(
                service_type=self.service_type,
                is_active=True
            ).first()
            
            if not self.service_config:
                raise ValueError(
                    f"No se encontró configuración activa para el servicio {self.service_type}"
                )
                
            logger.info(f"Configuración cargada para {self.service_type}: {self.service_config.base_url}")
            
        except Exception as e:
            logger.error(f"Error cargando configuración para {self.service_type}: {e}")
            raise
    
    @property
    def base_url(self):
        return self.service_config.base_url
    
    @property
    def auth_token(self):
        return self.service_config.auth_token
    
    @property
    def auth_type(self):
        return self.service_config.auth_type
    
    @abstractmethod
    def send_request(self, endpoint: str, data: dict, method: str = "POST"):
        """Método abstracto para enviar solicitudes."""
        pass