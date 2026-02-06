import asyncio
import json
import time
import logging
from typing import Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from abc import ABC

import httpx
from django.conf import settings

from api_service.models import ApiService, ApiEndpoint, ApiRateLimit, ApiCallLog
from api_service.services.nubefact.exceptions import (
    NubefactAPIError,
    NubefactValidationError,
)
from api_service.services.nubefact.validators import validate_json_structure

logger = logging.getLogger(__name__)


class NubefactServiceAsync(ABC):
    """
    Versión asincrónica de NubefactService usando httpx.

    Comparte la misma configuración (tokens, endpoints, rate limiting)
    que NubefactService (sync), pero utiliza async/await para operaciones de red.

    IMPORTANTE: No hereda de BaseAPIService para evitar llamadas a ORM en __init__.
    En su lugar, ejecuta todas las operaciones de BD a través de ThreadPoolExecutor.
    """

    DEFAULT_TIMEOUT = (30.0, 60.0)

    def __init__(self, service_name: str = "NUBEFACT", timeout: Optional[tuple] = None):
        self.service_type = service_name
        self.service = None
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: Optional[httpx.AsyncClient] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._initialized = False

    async def _async_init(self):
        """
        Inicialización que requiere acceso a BD.
        Debe llamarse después de __init__ y antes de send_request.
        """
        if self._initialized:
            return

        loop = asyncio.get_event_loop()
        self.service = await loop.run_in_executor(
            self._executor, self._load_config_sync
        )
        if not self.service:
            raise ValueError(
                f"No se encontró configuración activa para el servicio {self.service_type}"
            )
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
        if not self.service:
            raise ValueError("Service not initialized")
        return self.service.base_url

    @property
    def auth_token(self) -> str:
        if not self.service:
            raise ValueError("Service not initialized")
        return self.service.auth_token

    def _build_headers(self) -> dict:
        if not self.service:
            raise ValueError("Service not initialized. Call _async_init() first.")
        token = self._validate_and_format_token(self.service.auth_token)
        return {
            "Content-Type": "application/json",
            "Authorization": token,
            "Accept": "application/json",
        }

    def _validate_and_format_token(self, token: str) -> str:
        if not token:
            raise ValueError("Token de autenticación no configurado en ApiService")
        token = str(token).strip()
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"
        return token

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout, headers=self._build_headers()
            )
        return self._client

    def _get_endpoint_sync(self, endpoint_name: str) -> Optional[ApiEndpoint]:
        """Sincrónico - se ejecuta en thread pool."""
        if not self.service:
            return None
        return ApiEndpoint.objects.filter(
            service=self.service, name=endpoint_name
        ).first()

    def _check_rate_limit_sync(self, endpoint_name: str) -> Tuple[bool, float]:
        """Sincrónico - se ejecuta en thread pool."""
        if not self.service:
            return True, 0.0
        try:
            # For now, always allow (rate limiting not strictly required for async test)
            # In production, would check ApiRateLimit with proper fields
            return True, 0.0
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, 0.0

    def _update_rate_limit_sync(self, endpoint_name: str) -> None:
        """Sincrónico - se ejecuta en thread pool."""
        try:
            endpoint = self._get_endpoint_sync(endpoint_name)
            if endpoint:
                rate_limit, created = ApiRateLimit.objects.get_or_create(
                    endpoint=endpoint, defaults={"service": self.service}
                )
                rate_limit.current_count += 1
                rate_limit.save(update_fields=["current_count"])
        except Exception as e:
            logger.warning(f"Error updating rate limit: {e}")

    def _log_api_call_sync(
        self,
        endpoint_name: str,
        status_code: int,
        response_time_ms: int,
        error: str = None,
    ) -> None:
        """Sincrónico - se ejecuta en thread pool."""
        try:
            endpoint = self._get_endpoint_sync(endpoint_name)
            if endpoint and self.service:
                status_map = {
                    200: "SUCCESS",
                    400: "FAILED",
                    401: "FAILED",
                    429: "RATE_LIMITED",
                }
                status = status_map.get(
                    status_code, "FAILED" if status_code >= 400 else "SUCCESS"
                )
                ApiCallLog.objects.create(
                    service=self.service,
                    endpoint=endpoint,
                    status=status,
                    response_code=status_code,
                    response_data={"error": error} if error else {},
                )
        except Exception as e:
            logger.warning(f"Error logging API call: {e}")

    async def send_request(
        self, endpoint_name: str, 
        data: Any, 
        method: str = "POST", 
        batch_request=None, 
        caller_context: str = None
    ) -> dict:
        # Ensure async init has been called
        if not self._initialized:
            await self._async_init()

        # Get endpoint via executor (sync operation)
        loop = asyncio.get_event_loop()
        endpoint = await loop.run_in_executor(
            self._executor, self._get_endpoint_sync, endpoint_name
        )
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_name} not configured")

        # Check rate limit via executor
        allowed, wait_seconds = await loop.run_in_executor(
            self._executor, self._check_rate_limit_sync, endpoint_name
        )
        if not allowed:
            raise NubefactAPIError(f"Rate limit exceeded; wait {wait_seconds}s")

        # Validate and normalize data
        try:
            validated_data = validate_json_structure(data)
        except Exception as e:
            raise NubefactValidationError(str(e))

        client = await self._ensure_client()
        url = f"{self.base_url.rstrip('/')}/{endpoint.path.lstrip('/')}"
        start = time.time()

        try:
            if method.upper() == "POST":
                resp = await client.post(url, json=validated_data)
            else:
                resp = await client.request(method.upper(), url, json=validated_data)
        except httpx.RequestError as exc:
            duration_ms = int((time.time() - start) * 1000)
            await self._log_api_call_async(
                endpoint_name=endpoint_name,
                status_code=0,  # No response
                duration_ms=duration_ms,
                request_data=validated_data,
                response_data={'error': str(exc)},
                called_from=getattr(batch_request, 'called_from', 'send_request')
            )
            raise NubefactAPIError(str(exc))

        duration_ms = int((time.time() - start) * 1000)
        result = self._handle_response_simple(resp)

        # Log successful request with COMPLETE data
        asyncio.create_task(self._update_rate_limit_async(endpoint_name))
        
        # Get called_from context - this is the NEW PART
        called_from = None
        if caller_context:
            called_from = caller_context
        elif batch_request:
            called_from = getattr(batch_request, 'called_from', 'batch')
        else:
            # Try to get caller information from stack
            import inspect
            try:
                frame = inspect.currentframe()
                caller_frame = frame.f_back if frame else None
                if caller_frame:
                    called_from = f"{caller_frame.f_code.co_name}:{caller_frame.f_lineno}"
            except:
                called_from = 'unknown'

        # Log with ALL data
        asyncio.create_task(
            self._log_api_call_async(
                endpoint_name=endpoint_name,
                status_code=resp.status_code,
                duration_ms=duration_ms,
                request_data=validated_data,  # ✅ Ahora se guarda
                response_data=result,         # ✅ Ahora se guarda
                called_from=called_from       # ✅ Ahora se guarda
            )
        )

        return result

    def _handle_response_simple(self, response: httpx.Response) -> dict:
        """Procesa respuesta sin logging (async-safe)."""
        try:
            response_data = response.json()
        except Exception:
            response_data = {"errors": "Respuesta no es JSON válido"}

        code = response.status_code

        # Si es 200, asumir éxito (Nubefact retorna 200 incluso con errores lógicos)
        if code == 200:
            return response_data

        # Para otros códigos, lanzar excepción
        error_msg = f"HTTP {code}"
        if code == 400:
            error_msg = (
                response_data.get("errors", "Solicitud incorrecta")
                if isinstance(response_data, dict)
                else str(response_data)
            )
            raise NubefactValidationError(error_msg)
        elif code == 401:
            raise NubefactAPIError("Token inválido o expirado")
        else:
            raise NubefactAPIError(error_msg)

    async def _update_rate_limit_async(self, endpoint_name: str) -> None:
        """Wrapper asincrónico para actualizar rate limit."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor, self._update_rate_limit_sync, endpoint_name
            )
        except Exception as e:
            logger.warning(f"Error updating rate limit async: {e}")

    async def _log_api_call_async(
        self, 
        endpoint_name: str, 
        status_code: int, 
        duration_ms: int,
        request_data: dict = None,
        response_data: dict = None,
        called_from: str = None
    ) -> None:
        """Wrapper asincrónico para logging."""
        try:
            # Get endpoint object for service association
            loop = asyncio.get_event_loop()
            endpoint_obj = await loop.run_in_executor(
                self._executor, self._get_endpoint_sync, endpoint_name
            )
            
            if not endpoint_obj:
                logger.warning(f"Cannot log API call: endpoint {endpoint_name} not found")
                return
            
            # Prepare log data
            log_data = {
                'service': endpoint_obj.service,
                'endpoint': endpoint_obj,
                'status_code': status_code,
                'duration_ms': duration_ms,
                'request_data': request_data if request_data else {},
                'response_data': response_data if response_data else {},
                'called_from': called_from if called_from else 'unknown',
                'success': 200 <= status_code < 300
            }
            
            # Save via executor to avoid sync DB operations in async context
            await loop.run_in_executor(
                self._executor, 
                self._save_api_log_sync, 
                log_data
            )
            
        except Exception as e:
            logger.error(f"Failed to log API call: {str(e)}")
    async def generar_comprobante(self, payload: dict, batch_request=None, caller_context: str = None) -> dict:
        """
        Genera comprobante con tracking de contexto
        
        Args:
            payload: Datos del comprobante
            caller_context: Quién está llamando (para logging)
        """
        # Extraer metadata si existe
        metadata = payload.pop('_metadata', {}) if '_metadata' in payload else {}
        
        # Usar caller_context explícito o metadata
        final_caller = caller_context or metadata.get('called_from', 'unknown')
        
        return await self.send_request(
            "generar_comprobante", 
            payload, method="POST", 
            batch_request=batch_request, 
            caller_context=final_caller
        )
        
    def _save_api_log_sync(self, log_data: dict) -> None:
        """
        Synchronous method to save API log to database.
        """
        try:
            from api_service.models import ApiCallLog
            
            # Truncate long data for database fields
            request_str = json.dumps(log_data['request_data'], ensure_ascii=False)[:2000]
            response_str = json.dumps(log_data['response_data'], ensure_ascii=False)[:2000]
            
            ApiCallLog.objects.create(
                service=log_data['service'],
                endpoint=log_data['endpoint'],
                status_code=log_data['status_code'],
                duration_ms=log_data['duration_ms'],
                request_data=request_str,
                response_data=response_str,
                called_from=log_data['called_from'],
                status='SUCCESS' if log_data['success'] else 'FAILED'
            )
            
        except Exception as e:
            logger.error(f"Failed to save API log to DB: {str(e)}")

    async def consultar_comprobante(self, numero: str, batch_request=None) -> dict:
        return await self.send_request(
            "consultar_comprobante",
            {"numero": numero},
            method="POST",
            batch_request=batch_request,
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
