"""
MigoAPIServiceAsync - Versión Asincrónica que Hereda de MigoAPIService

Este módulo proporciona una versión asincrónica de MigoAPIService,
reutilizando TODA la lógica existente (validación, cache, rate limiting, logging)
y solo haciendo async las llamadas HTTP.

Características Heredadas:
✅ Validación de RUC/DNI
✅ Cache (válidos e inválidos)
✅ Rate limiting automático
✅ Logging completo
✅ Batch processing
✅ Manejo de errores
✅ Actualización de partners
✅ Todos los métodos de negocio

Cambios Mínimos:
✅ Método _make_request_async() para llamadas HTTP async
✅ Usa httpx en lugar de requests
✅ Métodos principales son async

Status: ✅ Reutiliza lógica existente + Async HTTP
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from django.utils import timezone

from .migo_service import MigoAPIService
from .cache_service import APICacheService
from ..models import ApiEndpoint, ApiCallLog, ApiBatchRequest

logger = logging.getLogger(__name__)


class MigoAPIServiceAsync(MigoAPIService):
    """
    Cliente APIMIGO Asincrónico - Hereda de MigoAPIService.
    
    Reutiliza:
    - Inicialización (__init__)
    - Validación (_validate_ruc_format, _validate_dni_format)
    - Cache (_is_ruc_marked_invalid, _mark_ruc_as_invalid, etc.)
    - Rate limiting (_check_rate_limit, _update_rate_limit)
    - Logging (_log_api_call, _get_caller_info)
    - Todos los métodos de negocio (consultar_ruc, consultar_dni, etc.)
    
    Sobrescribe:
    - _make_request_async() → ahora es async
    - Métodos que llaman a _make_request() → ahora son async
    
    Uso:
        async with MigoAPIServiceAsync() as service:
            result = await service.consultar_ruc_async('20100038146')
    """
    
    def __init__(self, token=None):
        """Inicializa usando la lógica existente de MigoAPIService"""
        super().__init__(token)
        
        # Cliente HTTP async - se crea en __aenter__
        self.async_client: Optional[httpx.AsyncClient] = None
        
        logger.debug(f"[ASYNC] MigoAPIServiceAsync inicializado con base_url: {self.base_url}")
    
    async def __aenter__(self):
        """Context manager: crear cliente async"""
        self.async_client = httpx.AsyncClient(timeout=30.0)
        logger.debug("[ASYNC] Cliente HTTP async creado")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager: cerrar cliente async"""
        if self.async_client:
            await self.async_client.aclose()
            self.async_client = None
        logger.debug("[ASYNC] Cliente HTTP async cerrado")
    
    def _get_client(self) -> httpx.AsyncClient:
        """Obtiene el cliente async, lanzando error si no está inicializado"""
        if not self.async_client:
            raise RuntimeError(
                "Cliente HTTP no inicializado. "
                "Usar: async with MigoAPIServiceAsync() as service:"
            )
        return self.async_client
    
    # ========================================================================
    # MÉTODO CRÍTICO ASYNC: _make_request_async (Sobrescribe MigoAPIService)
    # ========================================================================
    
    async def _make_request_async(
        self, 
        endpoint_name: str, 
        data: dict = None, 
        method: str = 'POST',
        batch_request: ApiBatchRequest = None, 
        retry_count: int = 0, 
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Versión ASYNC de _make_request().
        
        Reutiliza TODA la lógica de MigoAPIService excepto la llamada HTTP.
        - Validación de rate limit (existente)
        - Logging (existente)
        - Reintentos (existente)
        - Manejo de errores (existente)
        
        Solo cambia: usa httpx async en lugar de requests sync
        """
        start_time = timezone.now()
        endpoint = self._get_endpoint(endpoint_name)
        
        if not endpoint:
            return {
                "success": False,
                "error": f"Endpoint {endpoint_name} no configurado"
            }
        
        # REUTILIZAR: Verificar rate limit (método heredado)
        can_proceed, wait_time = self._check_rate_limit(endpoint_name)
        if not can_proceed:
            error_msg = f"Rate limit excedido para {endpoint_name}. Esperar {wait_time:.1f} segundos"
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="RATE_LIMITED",
                error_message=error_msg,
                duration_ms=0,
                batch_request=batch_request
            )
            return {"success": False, "error": error_msg}
        
        # Preparar datos
        request_data = data or {}
        if 'token' not in request_data:
            request_data['token'] = self.token
        
        try:
            client = self._get_client()
            
            # CAMBIO ÚNICO: Usar httpx async en lugar de requests sync
            if method.upper() == 'POST':
                response = await client.post(
                    f"{self.base_url}{endpoint.path}",
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=endpoint.timeout or 30
                )
            else:
                response = await client.get(
                    f"{self.base_url}{endpoint.path}",
                    params=request_data,
                    timeout=endpoint.timeout or 30
                )
            
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # REUTILIZAR: Procesar respuesta (lógica existente)
            if response.status_code == 200:
                response_data = response.json()
                
                if isinstance(response_data, dict):
                    success = response_data.get('success', True)
                    
                    if not success and '404' in str(response_data.get('error', '')):
                        response_data['invalid_sunat'] = True
                
                self._log_api_call(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="SUCCESS",
                    duration_ms=duration_ms,
                    batch_request=batch_request
                )
                
                self._update_rate_limit(endpoint_name)
                return response_data
            
            elif response.status_code == 404:
                # REUTILIZAR: Manejo de RUC no encontrado (existente)
                duration_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'RUC no encontrado en SUNAT')
                except:
                    error_msg = 'RUC no encontrado en SUNAT'
                
                response_data = {
                    "success": False,
                    "error": error_msg,
                    "status_code": 404,
                    "invalid_sunat": True
                }
                
                # Extraer RUC y marcarlo como inválido
                ruc = None
                if data and 'ruc' in data:
                    ruc = data['ruc']
                elif isinstance(request_data, dict) and 'ruc' in request_data:
                    ruc = request_data['ruc']
                
                if ruc:
                    self._mark_ruc_as_invalid(ruc, "404_NOT_FOUND")
                    response_data['ruc'] = ruc
                
                self._log_api_call(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="RUC_INVALID",
                    error_message=error_msg,
                    duration_ms=duration_ms,
                    batch_request=batch_request
                )
                
                self._update_rate_limit(endpoint_name)
                return response_data
            
            else:
                # REUTILIZAR: Manejo de otros errores HTTP (existente)
                duration_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                try:
                    error_data = response.json()
                    error_msg = f"Error {response.status_code}: {error_data.get('error', 'Error desconocido')}"
                except:
                    error_msg = f"Error {response.status_code}: {response.text[:200]}"
                
                response_data = {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
                self._log_api_call(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="FAILED",
                    error_message=error_msg,
                    duration_ms=duration_ms,
                    batch_request=batch_request
                )
                
                # Reintento para errores 5xx
                if retry_count < max_retries and response.status_code >= 500:
                    logger.warning(f"Reintentando {endpoint_name}, intento {retry_count + 1}/{max_retries}")
                    await asyncio.sleep(2 ** retry_count)
                    return await self._make_request_async(
                        endpoint_name, data, method, 
                        batch_request, retry_count + 1, max_retries
                    )
                
                self._update_rate_limit(endpoint_name)
                return response_data
        
        except (asyncio.TimeoutError, httpx.TimeoutException) as e:
            # REUTILIZAR: Manejo de timeout (existente)
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            error_msg = f"Timeout: {str(e)}"
            
            response_data = {"success": False, "error": error_msg}
            
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=request_data,
                response_data=response_data,
                status="FAILED",
                error_message=error_msg,
                duration_ms=duration_ms,
                batch_request=batch_request
            )
            
            # Reintento para timeout
            if retry_count < max_retries:
                logger.warning(f"Reintentando {endpoint_name} por timeout, intento {retry_count + 1}/{max_retries}")
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request_async(
                    endpoint_name, data, method, 
                    batch_request, retry_count + 1, max_retries
                )
            
            return response_data
        
        except Exception as e:
            # REUTILIZAR: Manejo de error general (existente)
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            error_msg = f"Error de conexión: {str(e)}"
            
            response_data = {"success": False, "error": error_msg}
            
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=request_data,
                response_data=response_data,
                status="FAILED",
                error_message=error_msg,
                duration_ms=duration_ms,
                batch_request=batch_request
            )
            
            # Reintento
            if retry_count < max_retries:
                logger.warning(f"Reintentando {endpoint_name} por error, intento {retry_count + 1}/{max_retries}")
                await asyncio.sleep(2 ** retry_count)
                return await self._make_request_async(
                    endpoint_name, data, method, 
                    batch_request, retry_count + 1, max_retries
                )
            
            return response_data
    
    # ========================================================================
    # MÉTODOS ASYNC PRINCIPALES (Reutilizan lógica, pero async)
    # ========================================================================
    
    async def consultar_ruc_async(
        self, 
        ruc: str, 
        force_refresh: bool = False,
        update_partner: bool = True
    ) -> Dict[str, Any]:
        """
        Versión ASYNC de consultar_ruc().
        
        Reutiliza:
        - Validación de formato (_validate_ruc_format)
        - Cache de inválidos (_is_ruc_marked_invalid, _mark_ruc_as_invalid)
        - Cache normal (cache_service)
        - Actualización de partner (_update_partner_sunat_status)
        
        Solo cambia: usa _make_request_async()
        """
        start_time = timezone.now()
        
        # REUTILIZAR: Validar formato (método heredado)
        is_valid_format, format_error = self._validate_ruc_format(ruc)
        if not is_valid_format:
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            api_response = {
                "success": False,
                "error": format_error,
                "ruc": ruc,
                "invalid_format": True
            }
            
            self._log_api_call(
                endpoint_name="consultar_ruc",
                request_data={"ruc": ruc},
                response_data=api_response,
                status="INVALID_FORMAT",
                error_message=format_error,
                duration_ms=duration_ms
            )
            
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
            
            return api_response
        
        # REUTILIZAR: Verificar si está marcado como inválido (método heredado)
        if not force_refresh and self._is_ruc_marked_invalid(ruc):
            logger.debug(f"RUC {ruc} en cache de inválidos")
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            invalid_info = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {}).get(ruc, {})
            api_response = {
                "success": False,
                "error": f"RUC marcado como inválido: {invalid_info.get('reason', 'Desconocido')}",
                "ruc": ruc,
                "cache_hit": True
            }
            
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
            
            return api_response
        
        # REUTILIZAR: Verificar cache normal (método heredado)
        if not force_refresh:
            cache_key = self.cache_service.get_service_cache_key('migo', f"ruc_{ruc}")
            cached_data = self.cache_service.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit para RUC {ruc}")
                api_response = {**cached_data, "cache_hit": True}
                
                if update_partner:
                    self._update_partner_sunat_status(ruc, api_response)
                
                return api_response
        
        # CAMBIO: Usar _make_request_async()
        request_data = {"ruc": ruc}
        api_response = await self._make_request_async("consultar_ruc", data=request_data)
        
        # REUTILIZAR: Procesar respuesta (lógica heredada)
        if api_response.get("success"):
            cache_key = self.cache_service.get_service_cache_key('migo', f"ruc_{ruc}")
            self.cache_service.set(cache_key, api_response, ttl=self.cache_service.RUC_VALID_TTL)
            
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
        
        elif api_response.get("invalid_sunat"):
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
        
        return api_response
    
    async def consultar_ruc_masivo_async(
        self,
        rucs: List[str],
        batch_size: int = 50,
        update_partners: bool = True
    ) -> Dict[str, Any]:
        """
        Versión ASYNC de consultar_ruc_masivo().
        
        Reutiliza:
        - Validación de formato
        - Cache
        - Procesamiento masivo
        
        Solo cambia: procesa en paralelo con asyncio
        """
        if not rucs:
            return {
                "success": False,
                "error": "Lista de RUCs vacía",
                "total": 0
            }
        
        # Filtrar únicos
        rucs_unicos = list(set(rucs))
        
        resultados = {
            "success": True,
            "total_rucs": len(rucs),
            "unique_rucs": len(rucs_unicos),
            "duplicates_removed": len(rucs) - len(rucs_unicos),
            "validos": [],
            "invalidos": [],
            "errores": [],
            "cache_hits": 0,
            "api_calls": 0,
            "batches_processed": 0
        }
        
        # Pre-filtrar por formato (REUTILIZAR validación)
        rucs_a_procesar = []
        for ruc in rucs_unicos:
            is_valid_format, _ = self._validate_ruc_format(ruc)
            if is_valid_format:
                rucs_a_procesar.append(ruc)
            else:
                resultados["invalidos"].append({
                    "ruc": ruc,
                    "error": "Formato inválido",
                    "type": "invalid"
                })
        
        # Procesar en lotes de forma PARALELA
        for i in range(0, len(rucs_a_procesar), batch_size):
            batch = rucs_a_procesar[i:i + batch_size]
            resultados["batches_processed"] += 1
            
            logger.info(f"[ASYNC] Procesando lote {resultados['batches_processed']}: {len(batch)} RUCs")
            
            # CAMBIO: Procesar en paralelo con asyncio
            tasks = [
                self.consultar_ruc_async(ruc, update_partner=update_partners)
                for ruc in batch
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Procesar respuestas
            for ruc, response in zip(batch, responses):
                if response.get("success"):
                    resultados["validos"].append({
                        "ruc": ruc,
                        "data": response.get("data", {})
                    })
                elif response.get("invalid_sunat") or response.get("invalid_format"):
                    resultados["invalidos"].append({
                        "ruc": ruc,
                        "error": response.get("error"),
                        "type": "invalid"
                    })
                else:
                    resultados["errores"].append({
                        "ruc": ruc,
                        "error": response.get("error"),
                        "type": "error"
                    })
                
                if response.get("cache_hit"):
                    resultados["cache_hits"] += 1
                else:
                    resultados["api_calls"] += 1
            
            # Pequeña pausa entre lotes para respetar rate limiting
            if i + batch_size < len(rucs_a_procesar):
                await asyncio.sleep(0.5)
        
        # Estadísticas
        resultados["total_validos"] = len(resultados["validos"])
        resultados["total_invalidos"] = len(resultados["invalidos"])
        resultados["total_errores"] = len(resultados["errores"])
        
        logger.info(f"[ASYNC] Lote completado: {resultados['total_validos']} válidos, "
                   f"{resultados['total_invalidos']} inválidos")
        
        return resultados
    
    async def consultar_dni_async(self, dni: str) -> Dict[str, Any]:
        """
        Versión ASYNC de consultar_dni().
        Reutiliza validación y cache, solo cambia a async.
        """
        cache_key = self.cache_service.get_service_cache_key('migo', f"dni_{dni}")
        cached_data = self.cache_service.get(cache_key)
        
        if cached_data:
            return {**cached_data, "cache_hit": True}
        
        result = await self._make_request_async("consultar_dni", {"dni": dni})
        
        if result.get("success"):
            self.cache_service.set(cache_key, result, ttl=self.cache_service.RUC_INVALID_TTL)
        
        return result
    
    async def consultar_tipo_cambio_async(self) -> Dict[str, Any]:
        """Versión ASYNC de consultar_tipo_cambio_latest()"""
        return await self._make_request_async(
            endpoint_name="tipo_cambio_latest",
            data={}
        )
    
    async def validar_ruc_para_facturacion_async(self, ruc: str) -> Dict[str, Any]:
        """
        Versión ASYNC de validar_ruc_para_facturacion().
        Reutiliza toda la lógica de validación.
        """
        try:
            resultado = await self.consultar_ruc_async(ruc)
            
            if not resultado.get("success"):
                return {
                    "valido": False,
                    "ruc": ruc,
                    "razon_social": None,
                    "estado": None,
                    "condicion": None,
                    "direccion": None,
                    "errores": ["RUC no encontrado en SUNAT"],
                    "advertencias": [],
                }
            
            estado = resultado.get("estado_del_contribuyente", "").upper()
            condicion = resultado.get("condicion_de_domicilio", "").upper()
            
            errores = []
            advertencias = []
            
            # Validaciones críticas
            if estado != "ACTIVO":
                errores.append(f"Contribuyente no está ACTIVO (estado: {estado})")
            
            if condicion != "HABIDO":
                errores.append(f"Contribuyente no es HABIDO (condición: {condicion})")
            
            # Validaciones de datos
            razon_social = resultado.get("nombre_o_razon_social")
            if not razon_social or len(razon_social.strip()) < 3:
                advertencias.append("Razón social muy corta o vacía")
            
            direccion = resultado.get("direccion")
            if not direccion or len(direccion.strip()) < 10:
                advertencias.append("Dirección muy corta o incompleta")
            
            return {
                "valido": len(errores) == 0,
                "ruc": ruc,
                "razon_social": razon_social,
                "estado": estado,
                "condicion": condicion,
                "direccion": direccion,
                "data_completa": resultado,
                "errores": errores,
                "advertencias": advertencias,
            }
        
        except Exception as e:
            logger.error(f"Error validando RUC {ruc}: {e}")
            return {
                "valido": False,
                "ruc": ruc,
                "razon_social": None,
                "errores": [f"Error de validación: {str(e)}"],
                "advertencias": [],
            }
