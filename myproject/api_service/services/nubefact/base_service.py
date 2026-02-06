# api_service/services/base_service.py
import inspect
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from django.conf import settings
from api_service.models import (
    ApiEndpoint,
    ApiService,
    ApiCallLog,
    ApiRateLimit,
    ApiBatchRequest,
)

logger = logging.getLogger(__name__)


class BaseAPIService(ABC):
    """Clase base abstracta para todos los servicios de API con logging integrado."""

    def __init__(self, service_type: str):
        self.service_type = service_type
        self.service = None
        self._load_config()

    def _load_config(self):
        """Carga la configuración del servicio desde la base de datos."""
        try:

            self.service = ApiService.objects.filter(
                service_type=self.service_type, is_active=True
            ).first()

            if not self.service:
                raise ValueError(
                    f"No se encontró configuración activa para el servicio {self.service_type}"
                )

            logger.info(
                f"Configuración cargada para {self.service_type}: {self.service.base_url}"
            )

        except Exception as e:
            logger.error(f"Error cargando configuración para {self.service_type}: {e}")
            raise

    @abstractmethod
    def send_request(self, endpoint: str, data: dict, method: str = "POST"):
        """Método abstracto para enviar solicitudes."""
        pass

    def _get_caller_info(self) -> str:
        """Obtiene información del llamador para logging."""

        try:
            # Obtener el frame del llamador (2 niveles arriba)
            frame = inspect.currentframe().f_back.f_back
            if frame:
                module = inspect.getmodule(frame)
                if module:
                    return f"{module.__name__}:{frame.f_code.co_name}"
        except:
            pass
        return "unknown"

    def _get_endpoint(self, endpoint_name: str):
        """Obtiene o crea un endpoint en la base de datos."""

        if not self.service:
            return None

        return ApiEndpoint.objects.filter(
            service=self.service, name=endpoint_name
        ).first()

    def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
        """
        Verifica si se puede hacer una petición según el rate limit.

        Basado en el patrón de MigoAPIService.

        Args:
            endpoint_name (str): Nombre del endpoint

        Returns:
            Tuple[bool, float]: (puede_proceder, tiempo_espera_segundos)

        Example:
            >>> can_proceed, wait_time = service._check_rate_limit('emitir_comprobante')
            >>> if not can_proceed:
            ...     print(f"Esperar {wait_time} segundos")
        """
        try:
            if not getattr(self, "service", None):
                return True, 0

            endpoint = self._get_endpoint(endpoint_name)
            if endpoint:
                # Obtener o crear el registro de rate limit para este endpoint
                rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                    self.service, endpoint
                )

                # Usar el método can_make_request() del modelo
                if rate_limit.can_make_request():
                    return True, 0
                else:
                    # Si no se puede hacer la petición, obtener tiempo de espera
                    wait_seconds = rate_limit.get_wait_time()
                    logger.warning(
                        f"Rate limit excedido para endpoint {endpoint_name}. "
                        f"Esperar {wait_seconds:.1f} segundos"
                    )
                    return False, wait_seconds
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")

        # Por defecto, permitir la petición si hay error
        return True, 0

    def _update_rate_limit(self, endpoint_name: str) -> None:
        """
        Actualiza el rate limit después de una llamada exitosa.

        Incrementa el contador de peticiones realizadas.

        Args:
            endpoint_name (str): Nombre del endpoint
        """
        try:
            if not getattr(self, "service", None):
                return

            endpoint = self._get_endpoint(endpoint_name)
            if endpoint:
                # Obtener o crear el registro de rate limit para este endpoint
                rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                    self.service, endpoint
                )

                # Usar el método increment_count() del modelo
                rate_limit.increment_count()
                logger.debug(
                    f"Rate limit actualizado para endpoint {endpoint_name}. "
                    f"Conteo actual: {rate_limit.current_count}/{rate_limit.get_limit()}"
                )
        except Exception as e:
            logger.error(f"Error updating rate limit: {str(e)}")

    def _log_api_call(
        self,
        endpoint_name: str,
        request_data: dict,
        response_data: dict,
        status: str,
        error_message: str = "",
        duration_ms: int = 0,
        batch_request: ApiBatchRequest = None,
        caller_info: str = None,
    ) -> None:
        """
        Registra llamada API en base de datos.

        Alineado con el patrón de MigoAPIService para consistencia.

        Args:
            endpoint_name (str): Nombre del endpoint
            request_data (dict): Datos de la solicitud
            response_data (dict): Datos de la respuesta
            status (str): Estado de la llamada (SUCCESS, FAILED, etc.)
            error_message (str): Mensaje de error (opcional)
            duration_ms (int): Duración en milisegundos
            batch_request (ApiBatchRequest): Solicitud por lote (opcional)
            caller_info (str): Información del llamador (opcional)

        Note:
            Si no hay servicio configurado (p.ej. en tests), solo loguea sin grabar en BD.
        """
        if caller_info is None:
            caller_info = self._get_caller_info()

        # Si no hay servicio (p.ej. tests que evitan inicializar DB), solo loguear
        if not getattr(self, "service", None):
            logger.debug(
                f"[API_CALL] {endpoint_name} status={status} duration={duration_ms}ms error={error_message}"
            )
            return

        try:
            endpoint = self._get_endpoint(endpoint_name)
            logger.debug(f"Registrando llamada API: {endpoint_name}")

            # Si es un RUC inválido (404), registrar información adicional
            if status == "FAILED" and "404" in error_message:
                response_data["invalid_ruc"] = True
                response_data["invalid_reason"] = "RUC_NO_EXISTE_SUNAT"

            # Crear registro de log - endpoint puede ser None
            ApiCallLog.objects.create(
                service=self.service,
                endpoint=endpoint,
                batch_request=batch_request,
                status=status,
                request_data=request_data,
                response_data=response_data,
                response_code=(
                    response_data.get("status_code", 200)
                    if isinstance(response_data, dict)
                    else 200
                ),
                error_message=error_message[:500],
                duration_ms=duration_ms,
                called_from=caller_info,
            )

            logger.info(
                f"[API_CALL_LOGGED] {endpoint_name} - {status} - {duration_ms}ms"
            )

        except Exception as e:
            logger.error(f"Error logging API call: {str(e)}")

    @property
    def base_url(self):
        return self.service.base_url if self.service else None

    @property
    def auth_token(self):
        return self.service.auth_token if self.service else None

    @property
    def auth_type(self):
        return self.service.auth_type if self.service else None
