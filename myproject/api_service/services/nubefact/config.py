# nubefact_service/config.py
import os
from api_service.models import ApiService, ApiEndpoint

class NubefactConfig:
    """Carga y valida la configuración necesaria para Nubefact."""
    def __init__(self):
        self.service = ApiService.objects.filter(service_type="NUBEFACT").first()
        if not self.service:
            raise ValueError("Servicio NUBEFACT no configurado")
        
        self.api_base_url = self.service.base_url or os.getenv('NUBEFACT_API_URL') 
        self.api_token = self.service.auth_token or os.getenv('NUBEFACT_API_TOKEN') 
        
        # self.api_base_url = os.getenv('NUBEFACT_API_URL')  # Tu RUTA única
        # self.api_token = os.getenv('NUBEFACT_API_TOKEN')   # Tu TOKEN
        

        if not self.api_base_url or not self.api_token:
            raise ValueError(
                "Las credenciales de Nubefact no están configuradas. "
                "Por favor, define las variables de entorno: "
                "NUBEFACT_API_URL y NUBEFACT_API_TOKEN"
            )

        # Asegurar que la URL base no termine con '/'
        self.api_base_url = self.api_base_url.rstrip('/')