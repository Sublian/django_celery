"""
Servicio APIMIGO Asincrónico
============================

Versión no bloqueante de MigoAPIService usando httpx y async/await.

Características:
- Llamadas HTTP no bloqueantes usando httpx
- Soporte completo para async/await
- Compatible con caché centralizado (APICacheService)
- Rate limiting y retry automático
- Procesamiento de lotes paralelo
- Manejo completo de errores
- Logging detallado

Uso:
    import asyncio
    
    async def main():
        service = MigoAPIServiceAsync()
        result = await service.consultar_ruc_async('20100038146')
        print(result)
    
    asyncio.run(main())

Para uso en Django:
    from asgiref.sync import async_to_sync
    
    # Convertir async a sync si es necesario
    result = async_to_sync(service.consultar_ruc_async)('20100038146')
"""

import httpx
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
# from concurrent.futures import asyncio as async_futures

from django.db import transaction
from django.utils import timezone
from django.conf import settings

from .cache_service import APICacheService
from .migo_service import MigoAPIService  # Para heredar configuración
from billing.models import Partner
from ..models import ApiService, ApiEndpoint, ApiCallLog, ApiRateLimit, ApiBatchRequest
from ..exceptions import APIError, RateLimitExceededError

logger = logging.getLogger(__name__)


class MigoAPIServiceAsync:
    """
    Cliente APIMIGO con soporte para operaciones asincrónicas no bloqueantes.
    
    Características:
    - Llamadas HTTP async usando httpx
    - Procesamiento paralelo de lotes
    - Compatible con cache centralizado
    - Rate limiting respetado
    - Reintentos automáticos con backoff exponencial
    """
    
    # Reutilizar constantes del servicio sincrónico
    INVALID_RUCS_CACHE_KEY = MigoAPIService.INVALID_RUCS_CACHE_KEY
    INVALID_RUC_TTL_HOURS = MigoAPIService.INVALID_RUC_TTL_HOURS
    
    # Configuración de async
    TIMEOUT = 30  # Timeout en segundos
    MAX_RETRIES = 2
    RETRY_DELAY = 0.5  # Segundos entre reintentos
    
    def __init__(self, token: Optional[str] = None):
        """
        Inicializa el servicio async.
        
        Args:
            token: Token de autenticación (opcional, usa BD si no se proporciona)
        """
        self.service = ApiService.objects.filter(service_type="MIGO").first()
        if not self.service:
            raise ValueError("Servicio APIMIGO no configurado en BD")
        
        self.token = token or self.service.auth_token
        self.base_url = self.service.base_url
        self.cache_service = APICacheService()
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(f"MigoAPIServiceAsync inicializado con base_url: {self.base_url}")
    
    async def __aenter__(self):
        """Context manager para cliente HTTP async."""
        self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cierra el cliente HTTP async."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Obtiene o crea cliente HTTP async."""
        if not self._client:
            self._client = httpx.AsyncClient(timeout=self.TIMEOUT)
        return self._client
    
    async def close(self):
        """Cierra el cliente HTTP si está abierto."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_endpoint(self, endpoint_name: str) -> Optional[ApiEndpoint]:
        """
        Obtiene configuración del endpoint desde BD.
        Nota: Django ORM es sincrónico, se usa directamente.
        """
        try:
            return ApiEndpoint.objects.filter(
                service=self.service,
                name=endpoint_name
            ).first()
        except Exception as e:
            logger.error(f"Error obteniendo endpoint {endpoint_name}: {e}")
            return None
    
    async def _make_request_async(
        self,
        endpoint_name: str,
        data: Optional[Dict[str, Any]] = None,
        method: str = 'POST',
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Realiza una petición HTTP async a APIMIGO.
        
        Args:
            endpoint_name: Nombre del endpoint
            data: Datos para la petición
            method: Método HTTP (GET/POST)
            retry_count: Número de reintentos actual
            
        Returns:
            Dict con respuesta de la API
        """
        start_time = timezone.now()
        endpoint = self._get_endpoint(endpoint_name)
        
        if not endpoint:
            return {
                "success": False,
                "error": f"Endpoint {endpoint_name} no configurado"
            }
        
        # Preparar datos
        request_data = data or {}
        if 'token' not in request_data:
            request_data['token'] = self.token
        
        try:
            client = self._get_client()
            url = f"{self.base_url}{endpoint.path}"
            
            # Log de la petición
            logger.debug(f"🚀 [ASYNC] {method} {url} (intento {retry_count + 1})")
            
            # Realizar petición
            if method.upper() == 'POST':
                response = await client.post(
                    url,
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=endpoint.timeout or self.TIMEOUT
                )
            else:
                response = await client.get(
                    url,
                    params=request_data,
                    timeout=endpoint.timeout or self.TIMEOUT
                )
            
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Procesar respuesta
            if response.status_code == 200:
                response_data = response.json()
                
                logger.debug(f"✅ [ASYNC] Respuesta exitosa ({duration_ms:.1f}ms)")
                
                # Registrar en BD (asincronamente)
                await self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="SUCCESS",
                    duration_ms=int(duration_ms)
                )
                
                return response_data
            
            elif response.status_code == 404 and endpoint_name == "consultar_ruc":
                # RUC no encontrado
                error_msg = "RUC no encontrado en SUNAT"
                response_data = {
                    "success": False,
                    "error": error_msg,
                    "status_code": 404,
                    "invalid_sunat": True
                }
                
                logger.warning(f"⚠️  [ASYNC] RUC no encontrado (404)")
                
                # Marcar RUC como inválido (sincronamente, a través de cache_service)
                if data and 'ruc' in data:
                    ruc = data['ruc']
                    try:
                        self.cache_service.add_invalid_ruc(ruc, "404_NOT_FOUND")
                        response_data['ruc'] = ruc
                    except Exception as e:
                        logger.warning(f"No se pudo marcar RUC {ruc} como inválido: {e}")
                
                await self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="RUC_INVALID",
                    error_message=error_msg,
                    duration_ms=int(duration_ms)
                )
                
                return response_data
            
            elif response.status_code >= 500 and retry_count < self.MAX_RETRIES:
                # Error del servidor, reintentar
                wait_seconds = self.RETRY_DELAY * (2 ** retry_count)  # Backoff exponencial
                logger.warning(
                    f"⚠️  [ASYNC] Error {response.status_code}. "
                    f"Reintentando en {wait_seconds}s (intento {retry_count + 1})"
                )
                await asyncio.sleep(wait_seconds)
                return await self._make_request_async(
                    endpoint_name, data, method, retry_count + 1
                )
            
            else:
                # Error HTTP
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', f'Error {response.status_code}')
                except:
                    error_msg = f"Error {response.status_code}: {response.text[:200]}"
                
                response_data = {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
                logger.error(f"❌ [ASYNC] Error: {error_msg}")
                
                await self._log_api_call_async(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="FAILED",
                    error_message=error_msg,
                    duration_ms=int(duration_ms)
                )
                
                return response_data
        
        except asyncio.TimeoutError:
            error_msg = f"Timeout después de {self.TIMEOUT}s"
            logger.error(f"❌ [ASYNC] {error_msg}")
            return {"success": False, "error": error_msg}
        
        except httpx.RequestError as e:
            error_msg = f"Error de conexión: {str(e)}"
            logger.error(f"❌ [ASYNC] {error_msg}")
            
            # Reintentar en error de conexión
            if retry_count < self.MAX_RETRIES:
                wait_seconds = self.RETRY_DELAY * (2 ** retry_count)
                logger.warning(f"⚠️  [ASYNC] Reintentando en {wait_seconds}s")
                await asyncio.sleep(wait_seconds)
                return await self._make_request_async(
                    endpoint_name, data, method, retry_count + 1
                )
            
            return {"success": False, "error": error_msg}
        
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            logger.error(f"❌ [ASYNC] {error_msg}")
            return {"success": False, "error": error_msg}
    
    async def _log_api_call_async(
        self,
        endpoint_name: str,
        request_data: dict,
        response_data: dict,
        status: str,
        error_message: str = "",
        duration_ms: int = 0
    ) -> None:
        """
        Registra llamada API en BD (ejecutada en thread pool para no bloquear).
        
        Args:
            endpoint_name: Nombre del endpoint
            request_data: Datos enviados
            response_data: Respuesta recibida
            status: Estado de la llamada
            error_message: Mensaje de error si aplica
            duration_ms: Duración en ms
        """
        try:
            endpoint = self._get_endpoint(endpoint_name)
            
            # Ejecutar creación en thread pool (Django ORM es sincrónico)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: ApiCallLog.objects.create(
                    service=self.service,
                    endpoint=endpoint,
                    status=status,
                    request_data=request_data,
                    response_data=response_data,
                    response_code=response_data.get('status_code', 200) if isinstance(response_data, dict) else 200,
                    error_message=error_message[:500],
                    duration_ms=duration_ms,
                    called_from="async_client"
                )
            )
        except Exception as e:
            logger.error(f"Error registrando llamada API: {e}")
    
    async def consultar_ruc_async(
        self,
        ruc: str,
        force_refresh: bool = False,
        update_partner: bool = True
    ) -> Dict[str, Any]:
        """
        Consulta individual de RUC de forma asincrónica.
        
        Args:
            ruc: Número de RUC a consultar
            force_refresh: Ignorar cache y forzar consulta a API
            update_partner: Actualizar estado del partner en BD
            
        Returns:
            Dict con respuesta de la API
        """
        # Validar formato
        if not ruc or len(str(ruc)) != 11 or not str(ruc).isdigit():
            return {
                "success": False,
                "error": f"Formato de RUC inválido: {ruc}",
                "invalid_format": True
            }
        
        # Verificar cache de inválidos
        if not force_refresh and self.cache_service.is_ruc_invalid(ruc):
            logger.debug(f"[ASYNC] RUC {ruc} en cache de inválidos, omitiendo consulta")
            return {
                "success": False,
                "error": "RUC marcado como inválido",
                "ruc": ruc,
                "cache_hit": True
            }
        
        # Verificar cache normal
        if not force_refresh:
            cache_key = self.cache_service.get_service_cache_key('migo', f"ruc_{ruc}")
            cached = self.cache_service.get(cache_key)
            if cached:
                logger.debug(f"[ASYNC] Cache hit para RUC {ruc}")
                return {**cached, "cache_hit": True, "cache_type": "valid"}
        
        # Consultar API
        result = await self._make_request_async(
            "consultar_ruc",
            data={"ruc": ruc}
        )
        
        # Cachear resultado si fue exitoso
        if result.get("success"):
            cache_key = self.cache_service.get_service_cache_key('migo', f"ruc_{ruc}")
            try:
                self.cache_service.set(
                    cache_key,
                    result,
                    ttl=self.cache_service.RUC_VALID_TTL
                )
            except Exception as e:
                logger.warning(f"Error cacheando RUC {ruc}: {e}")
        
        return result
    
    async def consultar_ruc_masivo_async(
        self,
        rucs: List[str],
        batch_size: int = 10,
        update_partners: bool = True
    ) -> Dict[str, Any]:
        """
        Consulta masiva de RUCs en paralelo de forma asincrónica.
        
        Nota: Procesa en paralelo respetando rate limiting.
        
        Args:
            rucs: Lista de RUCs a consultar
            batch_size: Número de consultas paralelas simultaneas
            update_partners: Actualizar partners en BD
            
        Returns:
            Dict con resultados consolidados
        """
        if not rucs:
            return {"success": False, "error": "Lista de RUCs vacía", "results": []}
        
        # Filtrar duplicados
        rucs_unicos = list(set(rucs))
        logger.info(f"[ASYNC] Consultando {len(rucs_unicos)} RUCs únicos (de {len(rucs)} originales)")
        
        resultados = {
            "success": True,
            "total_rucs": len(rucs_unicos),
            "validos": [],
            "invalidos": [],
            "errores": [],
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "duration_ms": 0
        }
        
        start_time = datetime.now()
        
        try:
            # Procesar en lotes paralelos
            for i in range(0, len(rucs_unicos), batch_size):
                batch = rucs_unicos[i:i + batch_size]
                
                # Crear tasks para todas las consultas del lote
                tasks = [
                    self.consultar_ruc_async(ruc, update_partner=update_partners)
                    for ruc in batch
                ]
                
                # Ejecutar en paralelo
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Procesar resultados del lote
                for ruc, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        resultados["errores"].append({
                            "ruc": ruc,
                            "error": str(result),
                            "type": "exception"
                        })
                    elif result.get("success"):
                        resultados["validos"].append({
                            "ruc": ruc,
                            "data": result
                        })
                    else:
                        resultados["invalidos"].append({
                            "ruc": ruc,
                            "error": result.get("error", "Error desconocido"),
                            "type": "api_error"
                        })
                
                # Pequeña pausa entre lotes para respetar rate limiting
                if i + batch_size < len(rucs_unicos):
                    await asyncio.sleep(0.5)
            
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            resultados["completed_at"] = datetime.now().isoformat()
            resultados["duration_ms"] = int(duration_ms)
            
            logger.info(
                f"[ASYNC] Consulta masiva completada: "
                f"{len(resultados['validos'])} válidos, "
                f"{len(resultados['invalidos'])} inválidos, "
                f"{len(resultados['errores'])} errores "
                f"en {duration_ms:.1f}ms"
            )
            
            return resultados
        
        except Exception as e:
            logger.error(f"[ASYNC] Error en consulta masiva: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "completed_at": datetime.now().isoformat(),
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000)
            }
    
    async def consultar_dni_async(self, dni: str) -> Dict[str, Any]:
        """Consulta un DNI de forma asincrónica."""
        cache_key = self.cache_service.get_service_cache_key('migo', f"dni_{dni}")
        cached = self.cache_service.get(cache_key)
        
        if cached:
            return cached
        
        result = await self._make_request_async("consulta_dni", data={"dni": dni})
        
        if result.get("success"):
            try:
                self.cache_service.set(
                    cache_key,
                    result,
                    ttl=self.cache_service.RUC_INVALID_TTL
                )
            except Exception as e:
                logger.warning(f"Error cacheando DNI {dni}: {e}")
        
        return result
    
    async def consultar_tipo_cambio_async(self) -> Dict[str, Any]:
        """Consulta tipo de cambio más reciente de forma asincrónica."""
        return await self._make_request_async("tipo_cambio_latest", data={})


# ============================================================================
# FUNCIONES HELPER PARA USAR ASYNC EN CONTEXTO SINCRÓNICO
# ============================================================================

def run_async(coro):
    """
    Ejecuta una corutina en el event loop actual o crea uno nuevo.
    
    Útil para llamar async desde código sincrónico.
    
    Ejemplo:
        result = run_async(service.consultar_ruc_async('20100038146'))
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is None:
        # No hay loop en ejecución, crear uno nuevo
        return asyncio.run(coro)
    else:
        # Ya hay un loop, crear task
        return asyncio.create_task(coro)


async def batch_query(
    service: MigoAPIServiceAsync,
    rucs: List[str],
    batch_size: int = 10
) -> Dict[str, Any]:
    """
    Consulta un lote de RUCs en paralelo.
    
    Ejemplo:
        async def main():
            async with MigoAPIServiceAsync() as service:
                results = await batch_query(service, ['20100038146', '20123456789'])
                print(results)
        
        asyncio.run(main())
    """
    return await service.consultar_ruc_masivo_async(rucs, batch_size=batch_size)
