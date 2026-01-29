# nubefact_service/client.py
import requests
from requests.exceptions import RequestException
from .config import NubefactConfig
from .exceptions import NubefactAPIError, NubefactAuthenticationError, NubefactValidationError

class NubefactClient:
    """Cliente para interactuar con la API de Nubefact."""

    # Mapeo de códigos de error de Nubefact a excepciones específicas
    _ERROR_MAP = {
        10: NubefactAuthenticationError,
        11: NubefactAuthenticationError,
        20: NubefactValidationError,
        21: NubefactValidationError,
        22: NubefactValidationError,
        23: NubefactValidationError,
        24: NubefactValidationError,
    }

    def __init__(self, config: NubefactConfig = None):
        self.config = config or NubefactConfig()
        self.session = requests.Session()
        # Configurar headers fijos para todas las peticiones
        self.session.headers.update({
            'Authorization': self.config.api_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _handle_response(self, response: requests.Response) -> dict:
        """Procesa la respuesta de la API, lanzando excepciones en caso de error."""
        try:
            response_data = response.json()
        except ValueError:
            response_data = {}

        # Verificar errores HTTP
        if response.status_code == 401:
            raise NubefactAuthenticationError("Token de autorización inválido o faltante.")
        elif response.status_code == 400:
            error_msg = response_data.get('errors', 'Solicitud incorrecta.')
            raise NubefactValidationError(f"Error de validación: {error_msg}")
        elif response.status_code >= 500:
            raise NubefactAPIError(f"Error interno del servidor Nubefact: {response.status_code}")

        # Verificar errores específicos de Nubefact en la respuesta JSON
        if 'codigo' in response_data and response_data['codigo'] in self._ERROR_MAP:
            error_class = self._ERROR_MAP[response_data['codigo']]
            error_desc = response_data.get('errors', 'Error desconocido')
            raise error_class(f"Código {response_data['codigo']}: {error_desc}")

        # Si la respuesta no es JSON o no tiene el formato esperado
        if not response_data:
            raise NubefactAPIError("La respuesta de Nubefact está vacía o no es JSON válido.")

        return response_data

    def post(self, endpoint: str, data: dict) -> dict:
        """Envía una petición POST a un endpoint específico de Nubefact."""
        url = f"{self.config.api_base_url}/{endpoint.lstrip('/')}"
        try:
            response = self.session.post(url, json=data, timeout=30)  # Timeout de 30 segundos
            return self._handle_response(response)
        except RequestException as e:
            raise NubefactAPIError(f"Error de conexión con Nubefact: {str(e)}")