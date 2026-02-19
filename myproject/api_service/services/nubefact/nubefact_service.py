# api_service/services/nubefact_service.py
import time
import json
import logging
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError

from .base_service import BaseAPIService
from .exceptions import NubefactAPIError, NubefactValidationError
from .validators import validate_json_structure, validate_totals
from ..base.timeout_config import TimeoutConfig

logger = logging.getLogger(__name__)


class NubefactService(BaseAPIService):
    """
    Servicio para integración con Nubefact API con logging automático.

    Proporciona métodos para emitir, consultar y anular comprobantes electrónicos.
    Implementa context manager para gestión segura de recursos.

    Uso:
        with NubefactService() as service:
            response = service.generar_comprobante(datos)

    Attributes:
        ERROR_CODES (dict): Mapeo de códigos de error de Nubefact
    """

    # Configuración por defecto
    DEFAULT_TIMEOUT = (30, 60)  # (connect, read) en segundos

    ERROR_CODES = {
        10: "Token incorrecto o eliminado",
        11: "Ruta/URL incorrecta o no existe",
        12: "Content-Type incorrecto en cabecera",
        20: "Archivo no cumple con el formato establecido",
        21: "No se pudo completar la operación",
        22: "Documento enviado fuera del plazo permitido",
        23: "Documento ya existe en Nubefact",
        24: "Documento no existe o no fue enviado a Nubefact",
        40: "Error interno desconocido",
        50: "Cuenta suspendida",
        51: "Cuenta suspendida por falta de pago",
    }

    def __init__(self, timeout_config: Optional[TimeoutConfig] = None):
        """
        Inicializa el servicio Nubefact.

        Patrón igual a MigoAPIService:
        - Hereda de BaseAPIService que carga self.service desde BD
        - Obtiene base_url y auth_token desde self.service
        - Endpoints específicos se cargan usando _get_endpoint()

        Args:
            timeout (tuple, optional): Tupla de (connect_timeout, read_timeout) en segundos.
                                      Si no se proporciona, usa DEFAULT_TIMEOUT.
        """
        super().__init__("NUBEFACT")

        # `BaseAPIService` ya expone `base_url` y `auth_token` como propiedades
        # a través de `self.service`. No asignarlas aquí (evita AttributeError).
        # Alias `self.token` se establece leyendo la propiedad `auth_token`.
        self.token = self.auth_token  # Alias para compatibilidad con MigoAPIService

        # Configurar cliente HTTP
        self.session = requests.Session()
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("NUBEFACT")
        self._configure_session()

    def _validate_and_format_token(self, token: str) -> str:
        """
        Valida y formatea el token de autenticación con prefijo 'Bearer'.

        Args:
            token (str): Token de autenticación desde la BD

        Returns:
            str: Token formateado con prefijo 'Bearer '

        Raises:
            ValueError: Si el token está vacío o es None
        """
        if not token:
            raise ValueError("Token de autenticación no configurado en ApiService")

        token = str(token).strip()
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"

        return token

    def _configure_session(self):
        """Configura la sesión HTTP con headers y timeout validados."""
        try:
            formatted_token = self._validate_and_format_token(self.auth_token)

            self.session.headers.update(
                {
                    "Authorization": formatted_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )

            logger.debug(f"Sesión HTTP configurada con timeout {self.timeout_config}")

        except ValueError as e:
            logger.error(f"Error configurando sesión: {str(e)}")
            raise

    def _handle_response(
        self,
        response: requests.Response,
        endpoint_name: str,
        request_data: dict,
        start_time: float,
        batch_request=None,
    ) -> Dict[str, Any]:
        """
        Procesa la respuesta de Nubefact y registra el log.

        Args:
            response (requests.Response): Respuesta HTTP
            endpoint_name (str): Nombre del endpoint para logging
            request_data (dict): Datos que se enviaron
            start_time (float): Tiempo de inicio de la petición
            batch_request: Instancia de ApiBatchRequest si aplica

        Returns:
            Dict[str, Any]: Datos de respuesta procesados

        Raises:
            NubefactValidationError: Si hay error de validación (400)
            NubefactAPIError: Si hay otros errores
        """
        duration_ms = int((time.time() - start_time) * 1000)

        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {
                "errors": "Respuesta no es JSON válido",
                "raw_response": response.text[:500],
            }

        # Determinar estado basado en código HTTP y respuesta Nubefact
        status = "SUCCESS"
        error_message = ""

        if response.status_code == 200:
            # Éxito HTTP, pero verificar si Nubefact reportó error
            if (
                "codigo" in response_data
                and response_data["codigo"] in self.ERROR_CODES
            ):
                error_msg = self.ERROR_CODES[response_data["codigo"]]
                error_message = f"Nubefact Error {response_data['codigo']}: {error_msg}"
                status = "FAILED"
        elif response.status_code == 400:
            error_message = response_data.get("errors", "Solicitud incorrecta")
            status = "FAILED"
        elif response.status_code == 401:
            error_message = "Error de autenticación: Token inválido o expirado"
            status = "FAILED"
        elif response.status_code >= 500:
            error_message = (
                f"Error interno del servidor Nubefact: {response.status_code}"
            )
            status = "FAILED"
        else:
            error_message = f"Error HTTP {response.status_code}: {response.text[:200]}"
            status = "FAILED"

        # Registrar la llamada en la base de datos (incluyendo batch_request si aplica)
        self._log_api_call(
            endpoint_name=endpoint_name,
            request_data=request_data,
            response_data=response_data,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            batch_request=batch_request,
            caller_info=self._get_caller_info(),
        )

        # Si hubo error, lanzar excepción
        if status == "FAILED":
            if response.status_code == 400:
                raise NubefactValidationError(error_message)
            else:
                raise NubefactAPIError(error_message)

        return response_data

    def send_request(
        self, endpoint_name: str, data: dict, method: str = "POST", batch_request=None
    ) -> Dict[str, Any]:
        """
        Envía una solicitud a la API de Nubefact con logging automático.

        Patrón igual a MigoAPIService:
        - endpoint_name: identificador del endpoint configurado en ApiEndpoint
        - Busca la configuración en ApiEndpoint (path, timeout, rate limit)
        - Construye URL como: base_url + endpoint.path
        - Incluye verificación de rate limiting y soporte para batch requests

        Args:
            endpoint_name (str): Nombre del endpoint (debe estar configurado en ApiEndpoint)
            data (dict): Datos del comprobante a enviar
            method (str): Método HTTP. Por defecto 'POST'. Valores soportados: 'POST'
            batch_request: Instancia de ApiBatchRequest si esta llamada es parte de un lote

        Returns:
            Dict[str, Any]: Respuesta de Nubefact

        Raises:
            NubefactValidationError: Si los datos no pasan validación
            NubefactAPIError: Si hay error de conexión o API retorna error
            ValueError: Si el endpoint no está configurado o método es inválido

        Example:
            >>> from api_service.services.nubefact import NubefactService
            >>> service = NubefactService()
            >>> respuesta = service.send_request(
            ...     endpoint_name="emitir_factura",
            ...     data=datos_comprobante
            ... )
        """
        start_time = time.time()

        try:
            # Obtener configuración del endpoint desde BD (patrón MigoAPIService)
            endpoint = self._get_endpoint(endpoint_name)
            if not endpoint:
                raise ValueError(
                    f"Endpoint '{endpoint_name}' no configurado en ApiEndpoint. "
                    f"Por favor, crear un registro ApiEndpoint para el servicio NUBEFACT."
                )

            # FASE 2: Verificar rate limit ANTES de hacer la petición
            can_proceed, wait_time = self._check_rate_limit(endpoint_name)
            if not can_proceed:
                error_msg = f"Rate limit excedido para {endpoint_name}. Esperar {wait_time:.1f} segundos"
                duration_ms = int((time.time() - start_time) * 1000)
                self._log_api_call(
                    endpoint_name=endpoint_name,
                    request_data=data,
                    response_data={},
                    status="RATE_LIMITED",
                    error_message=error_msg,
                    duration_ms=duration_ms,
                    batch_request=batch_request,
                    caller_info=self._get_caller_info(),
                )
                raise NubefactAPIError(error_msg)

            # Validar y normalizar datos usando módulo de validadores
            validated_data = validate_json_structure(data)

            # Construir URL usando patrón MigoAPIService: base_url + endpoint.path
            url = f"{self.base_url}{endpoint.path}"

            logger.debug(f"Enviando solicitud a {endpoint_name} - URL: {url}")

            # Enviar solicitud con timeout del endpoint o timeout por defecto
            if method.upper() == "POST":
                response = self.session.post(
                    url, json=validated_data, timeout=endpoint.timeout or self.timeout_config
                )
            else:
                raise ValueError(f"Método no soportado: {method}. Solo se soporta POST")

            # FASE 2: Actualizar rate limit después de llamada exitosa
            self._update_rate_limit(endpoint_name)

            # Procesar respuesta y registrar log (incluyendo batch_request)
            return self._handle_response(
                response, endpoint_name, validated_data, start_time, batch_request
            )

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Registrar error de conexión
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Error de conexión: {str(e)}"

            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="FAILED",
                error_message=error_msg,
                duration_ms=duration_ms,
                batch_request=batch_request,
                caller_info=self._get_caller_info(),
            )

            raise NubefactAPIError(error_msg)

        except (ValidationError, NubefactValidationError, NubefactAPIError, ValueError):
            # Estas excepciones ya fueron registradas o son esperadas
            raise

        except Exception as e:
            # Registrar error inesperado
            duration_ms = int((time.time() - start_time) * 1000)

            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="FAILED",
                error_message=str(e),
                duration_ms=duration_ms,
                batch_request=batch_request,
                caller_info=self._get_caller_info(),
            )

            raise NubefactAPIError(f"Error inesperado en servicio Nubefact: {str(e)}")

    def generar_comprobante(self, datos_comprobante: dict) -> Dict[str, Any]:
        """
        Emite un comprobante electrónico en Nubefact.

        Método simplificado que envuelve send_request para la operación
        'generar_comprobante'. Valida automáticamente los datos.

        Args:
            datos_comprobante (dict): Diccionario con los datos del comprobante.
                Debe contener al menos:
                - tipo_de_comprobante (int)
                - serie (str)
                - numero (int)
                - cliente_tipo_de_documento (int)
                - cliente_numero_de_documento (str)
                - cliente_denominacion (str)
                - fecha_de_emision (str, formato YYYY-MM-DD)
                - moneda (int)
                - total_gravada (Decimal)
                - total_igv (Decimal)
                - total (Decimal)
                - items (List[dict])

        Returns:
            Dict[str, Any]: Respuesta de Nubefact con datos del comprobante generado

        Raises:
            NubefactValidationError: Si los datos no pasan validación
            NubefactAPIError: Si hay error de comunicación o API retorna error

        Example:
            >>> from api_service.services.nubefact import NubefactService
            >>> datos = {
            ...     'tipo_de_comprobante': 1,  # Factura
            ...     'serie': 'F001',
            ...     'numero': 1,
            ...     'cliente_tipo_de_documento': 6,
            ...     'cliente_numero_de_documento': '20123456789',
            ...     'cliente_denominacion': 'Empresa XYZ',
            ...     'fecha_de_emision': '2024-01-15',
            ...     'moneda': 1,
            ...     'total_gravada': 100.00,
            ...     'total_igv': 18.00,
            ...     'total': 118.00,
            ...     'items': [...]
            ... }
            >>> with NubefactService() as service:
            ...     respuesta = service.generar_comprobante(datos)
            ...     print(respuesta.get('enlace_comprobante'))
        """
        return self.send_request("generar_comprobante", datos_comprobante)

    def consultar_comprobante(
        self, tipo: int, serie: str, numero: int
    ) -> Dict[str, Any]:
        """
        Consulta el estado de un comprobante existente en Nubefact.

        Args:
            tipo (int): Tipo de comprobante (1=Factura, 2=Boleta, etc.)
            serie (str): Serie del comprobante (ej: 'F001')
            numero (int): Número del comprobante

        Returns:
            Dict[str, Any]: Estado actual del comprobante en Nubefact

        Raises:
            NubefactValidationError: Si los parámetros son inválidos
            NubefactAPIError: Si hay error de comunicación

        Example:
            >>> from api_service.services.nubefact import NubefactService
            >>> with NubefactService() as service:
            ...     estado = service.consultar_comprobante(1, 'F001', 1)
            ...     print(estado.get('estado_comprobante'))
        """
        data = {
            "operacion": "consultar_comprobante",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero,
        }
        return self.send_request("consultar_comprobante", data)

    def anular_comprobante(
        self, tipo: int, serie: str, numero: int, motivo: str
    ) -> Dict[str, Any]:
        """
        Anula un comprobante existente en Nubefact.

        Args:
            tipo (int): Tipo de comprobante (1=Factura, 2=Boleta, etc.)
            serie (str): Serie del comprobante (ej: 'F001')
            numero (int): Número del comprobante
            motivo (str): Motivo de la anulación (ej: 'Error en datos del cliente')

        Returns:
            Dict[str, Any]: Confirmación de anulación

        Raises:
            NubefactValidationError: Si los parámetros son inválidos
            NubefactAPIError: Si hay error de comunicación o el comprobante no existe

        Example:
            >>> from api_service.services.nubefact import NubefactService
            >>> with NubefactService() as service:
            ...     anulacion = service.anular_comprobante(
            ...         1, 'F001', 1, 'Error en monto'
            ...     )
            ...     print(anulacion.get('estado_comprobante'))
        """
        data = {
            "operacion": "generar_anulacion",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero,
            "motivo": motivo,
        }
        return self.send_request("anular_comprobante", data)

    def __del__(self):
        """Cierra la sesión al destruir el objeto (fallback)."""
        if hasattr(self, "session"):
            try:
                self.session.close()
            except Exception:
                pass

    def __enter__(self):
        """Context manager: permite usar 'with' para gestión de recursos."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: cierra la sesión al salir del bloque 'with'."""
        self.session.close()
        return False
