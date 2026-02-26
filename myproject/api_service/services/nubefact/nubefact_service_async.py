# api_service/services/nubefact_service_async
import asyncio
import json
import time
import logging
from typing import Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from abc import ABC
import httpx
from asgiref.sync import sync_to_async

from django.conf import settings
from django.utils import timezone

from api_service.models import ApiService, ApiEndpoint, ApiBatchRequest
from api_service.services.nubefact.exceptions import (
    NubefactAPIError,
    NubefactValidationError,
)
from .logging import save_api_log_async
from .config import NubefactConfig
from ..base import (
    TimeoutConfig,
    RateLimitManager,
    validate_and_format_token
)

logger = logging.getLogger(__name__)


class NubefactServiceAsync(ABC):
    """
    Versión asincrónica de NubefactService usando httpx.

    Comparte la misma configuración (tokens, endpoints, rate limiting)
    que NubefactService (sync), pero utiliza async/await para operaciones de red.

    IMPORTANTE: No hereda de BaseAPIService para evitar llamadas a ORM en __init__.
    En su lugar, ejecuta todas las operaciones de BD a través de ThreadPoolExecutor.
    """


    def __init__(self, service_name: str = "NUBEFACT", timeout_config: Optional[TimeoutConfig] = None):
        """
        Inicializa el servicio asíncrono NubeFact.
        """
        self.service_type = service_name
        self.service = None
        self.timeout_config = timeout_config or TimeoutConfig.from_settings("NUBEFACT")
        self._client: Optional[httpx.AsyncClient] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._initialized = False
        self.config = None
        self.rate_limiter = RateLimitManager() 
        
         # Configuración de logging
        self.logging_enabled = True
        self.logging_verbose = False  # Para pruebas de estrés
        
    def set_logging_mode(self, verbose: bool = False):
        """Controla el modo de logging (útil para pruebas de estrés)."""
        self.logging_verbose = verbose

    async def _async_init(self):
        """
        Inicialización que requiere acceso a BD.
        Debe llamarse después de __init__ y antes de send_request.
        """
        if self._initialized:
            return

        self.config = await NubefactConfig.create(timeout_config=self.timeout_config)
        loop = asyncio.get_event_loop()
        self.service = await loop.run_in_executor(
            self._executor, self._load_config_sync
        )
        if not self.service:
            raise ValueError(
                f"No se encontró configuración activa para el servicio {self.service_type}"
            )
        self.rate_limiter.set_service(self.service)
        
        self._initialized = True

    def _load_config_sync(self):
        """Sincrónico - se ejecuta en thread pool."""
        try:
            service = ApiService.objects.filter(
                service_type=self.service_type, is_active=True
            ).first()
            if service:
                logger.info(
                    f"Configuración cargada para {self.service_type}: {service.base_url}"
                )
            return service
        except Exception as e:
            logger.error(f"Error cargando configuración para {self.service_type}: {e}")
            raise

    @property
    def base_url(self) -> str:
        if not self.config:
            raise ValueError("Service not initialized")
        return self.config.base_url

    @property
    def auth_token(self) -> str:
        if not self.config:
            raise ValueError("Service not initialized")
        return self.config.auth_token
    
    @property
    def timeout(self) -> tuple:
        """Propiedad de compatibilidad para código legacy."""
        return self.timeout_config.as_tuple

    def _build_headers(self) -> dict:
        """Construye headers para la petición a NubeFact."""
        if not self.config:
            raise ValueError("Service not initialized. Call _async_init() first.")
        
        token = validate_and_format_token(self.config.auth_token, "NubeFact")
        
        # Versión simplificada que funcionaba antes
        return {
            "Content-Type": "application/json",
            "Authorization": token,
            # "Authorization": f"Bearer {self.config.auth_token}",
            "Accept": "application/json",
        }


    async def _ensure_client(self) -> httpx.AsyncClient:
        """Asegura que exista un cliente HTTP configurado."""
        if not hasattr(self, '_client') or self._client is None:
            limits = httpx.Limits(max_keepalive_connections=10, max_connections=100)
            
            self._client = httpx.AsyncClient(
                timeout=self.timeout_config.httpx_timeout,
                limits=limits,
                verify=True
            )
        return self._client
    
    def _get_endpoint_sync(self, endpoint_name: str) -> Optional[ApiEndpoint]:
        """Sincrónico - se ejecuta en thread pool."""
        if not self.service:
            return None
        return ApiEndpoint.objects.filter(
            service=self.service, name=endpoint_name
        ).first()

    def _get_caller_info(self):
        """Obtiene información del caller de forma segura"""
        import inspect

        try:
            frame = inspect.currentframe()
            # Subir 2 niveles para saltar esta función y send_request
            caller_frame = frame.f_back.f_back if frame and frame.f_back else None
            if caller_frame:
                return f"{caller_frame.f_code.co_name}:{caller_frame.f_lineno}"
        except:
            pass
        return "unknown"

    # ===== RATE LIMITING (usando RateLimitManager) =====
    async def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
        """Verifica rate limit usando el manager."""
        return await self.rate_limiter.check_rate_limit_async(endpoint_name)
    
    async def _update_rate_limit(self, endpoint_name: str) -> None:
        """Actualiza rate limit usando el manager."""
        await self.rate_limiter.update_rate_limit_async(endpoint_name)
        
     # ===== LOGGING (usando logging.py) =====
    
    async def _log_api_call_async(
        self,
        endpoint_name: str,
        status_code: int,
        duration_ms: int,
        request_data: dict = None,
        response_data: dict = None,
        called_from: str = None,
        batch_request: ApiBatchRequest = None,
    ) -> None:
        """Wrapper asincrónico para logging - VERSIÓN MEJORADA"""
        
        if not self.logging_enabled:
            return

        try:
            # Ejecutar el logging en un thread separado
            await save_api_log_async(
                endpoint_name=endpoint_name,
                status_code=status_code,
                duration_ms=duration_ms,
                request_data=request_data,
                response_data=response_data,
                called_from=called_from or "unknown",
                batch_request=batch_request,
                config=self.config,
                verbose=self.logging_verbose,
            )

        except Exception as e:
            logger.error(f"Failed to log API call: {str(e)}", exc_info=True)
    
    # ===== REQUEST HANDLING =====
    async def send_request(
        self,
        endpoint_name: str,
        data: Any,
        method: str = "POST",
        batch_request=None,
        caller_context=None,
    ) -> dict:
        # Ensure async init has been called
        if not self._initialized:
            await self._async_init()

        # ✅ Obtener endpoint desde config (AHORA siempre es objeto ApiEndpoint)
        endpoint = self.config.get_endpoint(endpoint_name)
        
        # Fallback a búsqueda en BD si no está en config
        if not endpoint:
            loop = asyncio.get_event_loop()
            endpoint = await loop.run_in_executor(
                self._executor, self._get_endpoint_sync, endpoint_name
            )
            if not endpoint:
                raise ValueError(f"Endpoint {endpoint_name} not configured")

        # Check rate limit
        allowed, wait_seconds = await self._check_rate_limit(endpoint_name)
        if not allowed:
            raise NubefactAPIError(f"Rate limit exceeded; wait {wait_seconds}s")

        # Use data as-is (validation done in operations)
        validated_data = data

        client = await self._ensure_client()
        headers = self._build_headers()
        
        # ✅ endpoint.path funciona porque endpoint es un objeto ApiEndpoint real
        url = f"{self.base_url.rstrip('/')}/{endpoint.path.lstrip('/')}"

        start = time.time()

        # Determinar called_from una sola vez
        if batch_request:
            called_from = getattr(batch_request, "called_from", "batch")
        elif caller_context:
            called_from = caller_context
        else:
            called_from = self._get_caller_info()

        validated_data_copy = validated_data.copy() if validated_data else {}

        try:
            # Realizar la petición HTTP
            if method.upper() == "POST":
                resp = await client.post(url, json=validated_data, headers=headers)
            else:
                resp = await client.request(method.upper(), url, json=validated_data, headers=headers)

            duration_ms = int((time.time() - start) * 1000)

            # Capturar respuesta para debug
            try:
                response_data = resp.json()
            except:
                response_data = {"error": "Respuesta no JSON"}

            # print(f"🔍 DEBUG - Status code: {resp.status_code}")
            # print(f"🔍 DEBUG - Response data: {json.dumps(response_data, indent=2)}")

            # Procesar respuesta (puede lanzar excepción si hay error)
            result = self._handle_response_simple(resp)

            # ✅ LOG EXITOSO
            asyncio.create_task(self._update_rate_limit(endpoint_name))
            asyncio.create_task(
                self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    status_code=resp.status_code,
                    duration_ms=duration_ms,
                    request_data=validated_data_copy,
                    response_data=result,
                    called_from=called_from,
                    batch_request=batch_request,  # ✅ Pasar batch_request
                )
            )

            return result

        except httpx.RequestError as exc:
            # Error de red/timeout
            duration_ms = int((time.time() - start) * 1000)
            error_response = {"error": str(exc), "type": "RequestError"}

            asyncio.create_task(
                self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    status_code=0,
                    duration_ms=duration_ms,
                    request_data=validated_data_copy,
                    response_data=error_response,
                    called_from=called_from,
                    batch_request=batch_request,  # ✅ Pasar batch_request
                )
            )
            raise NubefactAPIError(str(exc))

        except (NubefactValidationError, NubefactAPIError) as exc:
            # Error de validación o API
            duration_ms = int((time.time() - start) * 1000)
            status_code = getattr(exc, "status_code", 400)
            
            # ✅ Obtener response_data completo desde la excepción
            response_data = getattr(exc, "response_data", {"error": str(exc)})

            # print(f"🔍 DEBUG - Excepción capturada: {exc}")
            # print(f"🔍 DEBUG - Response_data en excepción: {json.dumps(response_data, indent=2)}")
            # print(f"🔍 DEBUG - Enviando log para {endpoint_name}...")

            asyncio.create_task(
                self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_data=validated_data_copy,
                    response_data=response_data,
                    called_from=called_from,
                    batch_request=batch_request,  # ✅ Pasar batch_request
                )
            )
            raise

        except Exception as exc:
            # Error inesperado
            duration_ms = int((time.time() - start) * 1000)

            asyncio.create_task(
                self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    status_code=500,
                    duration_ms=duration_ms,
                    request_data=validated_data_copy,
                    response_data={"error": str(exc), "type": "UnexpectedError"},
                    called_from=called_from,
                    batch_request=batch_request,  # ✅ Pasar batch_request
                )
            )
            raise        

    def _handle_response_simple(self, response: httpx.Response) -> dict:
        """Procesa respuesta (async-safe)."""
        try:
            response_data = response.json()
        except Exception:
            response_data = {"errors": "Respuesta no es JSON válido"}

        # Guardar metadata
        response_data["_status_code"] = response.status_code
        
        code = response.status_code
        
        # Si es 200, asumir éxito
        if code == 200:
            return response_data
        
        # ✅ DEBUG AQUÍ - antes de lanzar excepción
        # if code != 200:
        #     print(f"🔍 DEBUG - Error detectado en respuesta:")
        #     print(f"🔍 DEBUG - Status code: {code}")
            # print(f"🔍 DEBUG - Response data: {json.dumps(response_data, indent=2)}")

        # Para otros códigos, preparar excepción con datos completos
        error_msg = f"HTTP {code}"
        if code == 400:
            error_msg = (
                response_data.get("errors", "Solicitud incorrecta")
                if isinstance(response_data, dict)
                else str(response_data)
            )
            exc = NubefactValidationError(error_msg)
        elif code == 401:
            exc = NubefactAPIError("Token inválido o expirado")
        else:
            exc = NubefactAPIError(error_msg)
        
        # Adjuntar datos completos a la excepción
        exc.response_data = response_data
        exc.status_code = code
        raise exc

    #############
    # OPERATIONS
    #############
    async def generar_comprobante(
        self, payload: dict, batch_request=None, caller_context: str = None
    ) -> dict:
        """
        Genera comprobante con tracking de contexto

        Args:
            payload: Datos del comprobante
            caller_context: Quién está llamando (para logging)
        """
        from .schemas.comprobante import ComprobanteSchema
        
        # Validar con Pydantic
        validated = ComprobanteSchema(**payload)
        validated_data = validated.model_dump()
        
        # Extraer metadata si existe
        metadata = payload.pop("_metadata", {}) if "_metadata" in payload else {}
        final_caller = caller_context or metadata.get("called_from", "unknown")

        return await self.send_request(
            "generar_comprobante",
            validated_data,
            method="POST",
            batch_request=batch_request,
            caller_context=final_caller,
        )

    async def anular_comprobante(
        self, numero: str, motivo: str, batch_request=None
    ) -> dict:
        return await self.send_request(
            "anular_comprobante",
            {"numero": numero, "motivo": motivo},
            method="POST",
            batch_request=batch_request,
        )

    async def __aenter__(self):
        await self._async_init()
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._client is not None:
            await self._client.aclose()
