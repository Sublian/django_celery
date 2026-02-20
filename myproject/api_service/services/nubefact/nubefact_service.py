# api_service/services/nubefact/nubefact_service.py

import time
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from django.core.exceptions import ValidationError

from api_service.models import ApiBatchRequest
from ..base_service import BaseAPIService
from .exceptions import NubefactAPIError, NubefactValidationError
from .validators import validate_json_structure
from .logging import save_api_log_sync
from ..base import (
    TimeoutConfig,
    RateLimitManager,
    validate_and_format_token
)

logger = logging.getLogger(__name__)


class NubefactService(BaseAPIService):
    """
    Servicio para integración con Nubefact API.

    Proporciona métodos para emitir, consultar y anular comprobantes electrónicos.
    Implementa context manager para gestión segura de recursos.

    Uso:
        with NubefactService() as service:
            response = service.generar_comprobante(datos)
    """

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
        """
        super().__init__("NUBEFACT")

        # Rate limiting
        self.rate_limiter = RateLimitManager(self.service)
        
        # Cliente HTTP
        self.session = requests.Session()
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("NUBEFACT")
        self._configure_session()

    def _configure_session(self):
        """Configura la sesión HTTP con headers y timeout validados."""
        try:
            token = validate_and_format_token(self.auth_token, "NubeFact")
            self.session.headers.update({
                "Authorization": token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            })
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
        batch_request: Optional[ApiBatchRequest] = None,
    ) -> Dict[str, Any]:
        """
        Procesa la respuesta de Nubefact y registra el log.
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
        status, error_message = self._determine_response_status(response, response_data)

        # Registrar la llamada en BD
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

    def _determine_response_status(
        self, 
        response: requests.Response, 
        response_data: dict
    ) -> Tuple[str, str]:
        """
        Determina el estado y mensaje de error basado en la respuesta.
        """
        if response.status_code == 200:
            if "codigo" in response_data and response_data["codigo"] in self.ERROR_CODES:
                error_msg = self.ERROR_CODES[response_data["codigo"]]
                return "FAILED", f"Nubefact Error {response_data['codigo']}: {error_msg}"
            return "SUCCESS", ""
        
        if response.status_code == 400:
            return "FAILED", response_data.get("errors", "Solicitud incorrecta")
        
        if response.status_code == 401:
            return "FAILED", "Error de autenticación: Token inválido o expirado"
        
        if response.status_code >= 500:
            return "FAILED", f"Error interno del servidor Nubefact: {response.status_code}"
        
        return "FAILED", f"Error HTTP {response.status_code}: {response.text[:200]}"

    # ===== RATE LIMITING (usando RateLimitManager) =====
    
    def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
        """Verifica rate limit usando el manager."""
        return self.rate_limiter.check_rate_limit_sync(endpoint_name)
    
    def _update_rate_limit(self, endpoint_name: str) -> None:
        """Actualiza rate limit usando el manager."""
        self.rate_limiter.update_rate_limit_sync(endpoint_name)

    # ===== REQUEST HANDLING =====
    
    def send_request(
        self, 
        endpoint_name: str, 
        data: dict, 
        method: str = "POST", 
        batch_request: Optional[ApiBatchRequest] = None
    ) -> Dict[str, Any]:
        """
        Envía una solicitud a la API de Nubefact con logging automático.
        """
        start_time = time.time()

        try:
            # Obtener configuración del endpoint
            endpoint = self._get_endpoint(endpoint_name)
            if not endpoint:
                raise ValueError(
                    f"Endpoint '{endpoint_name}' no configurado en ApiEndpoint. "
                    f"Por favor, crear un registro ApiEndpoint para el servicio NUBEFACT."
                )

            # Verificar rate limit
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

            # Validar y normalizar datos
            validated_data = validate_json_structure(data)

            # Construir URL
            url = f"{self.base_url}{endpoint.path}"

            logger.debug(f"Enviando solicitud a {endpoint_name} - URL: {url}")

            # Enviar solicitud
            if method.upper() != "POST":
                raise ValueError(f"Método no soportado: {method}. Solo se soporta POST")

            response = self.session.post(
                url, 
                json=validated_data, 
                timeout=endpoint.timeout or self.timeout_config.as_tuple
            )

            # Actualizar rate limit después de llamada exitosa
            self._update_rate_limit(endpoint_name)

            # Procesar respuesta
            return self._handle_response(
                response, endpoint_name, validated_data, start_time, batch_request
            )

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
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
            raise

        except Exception as e:
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

    # ===== OPERACIONES ESPECÍFICAS =====
    
    def generar_comprobante(self, datos_comprobante: dict) -> Dict[str, Any]:
        """Emite un comprobante electrónico en Nubefact."""
        return self.send_request("generar_comprobante", datos_comprobante)

    def consultar_comprobante(
        self, tipo: int, serie: str, numero: int
    ) -> Dict[str, Any]:
        """Consulta el estado de un comprobante existente."""
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
        """Anula un comprobante existente."""
        data = {
            "operacion": "generar_anulacion",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero,
            "motivo": motivo,
        }
        return self.send_request("anular_comprobante", data)

    # ===== CONTEXT MANAGER =====
    
    def __del__(self):
        """Cierra la sesión al destruir el objeto (fallback)."""
        if hasattr(self, "session"):
            try:
                self.session.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
        return False