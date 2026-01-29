# nubefact_service/config.py
import os

class NubefactConfig:
    """Carga y valida la configuración necesaria para Nubefact."""
    def __init__(self):
        self.api_base_url = os.getenv('NUBEFACT_API_URL')  # Tu RUTA única
        self.api_token = os.getenv('NUBEFACT_API_TOKEN')   # Tu TOKEN

        if not self.api_base_url or not self.api_token:
            raise ValueError(
                "Las credenciales de Nubefact no están configuradas. "
                "Por favor, define las variables de entorno: "
                "NUBEFACT_API_URL y NUBEFACT_API_TOKEN"
            )

        # Asegurar que la URL base no termine con '/'
        self.api_base_url = self.api_base_url.rstrip('/')