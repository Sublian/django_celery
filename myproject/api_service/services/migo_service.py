import requests
import time
import hashlib
import json
import requests
from requests.exceptions import RequestException
import logging
from urllib import response
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .cache_service import APICacheService
from billing.models import Partner
from ..models import ApiService, ApiEndpoint, ApiCallLog, ApiRateLimit, ApiBatchRequest
from ..exceptions import (
    APIError,
    RateLimitExceededError,
    AuthenticationError,
    APINotFoundError,
    APIBadResponseError,
    APITimeoutError,
)

logger = logging.getLogger(__name__)


class MigoAPIService:
    """
    Cliente específico para APIMIGO con todas sus funcionalidades.
    
    Características:
    - Consultas de RUC, DNI, tipo de cambio
    - Cache integrado (LocMemCache en desarrollo, Memcached en producción)
    - Rate limiting automático
    - Manejo completo de errores
    - Batch processing
    
    El cache se gestiona automáticamente a través de APICacheService.
    Los RUCs válidos se cachean por 1 hora, inválidos por 24 horas.
    """
    
    # Constantes para cache de RUCs inválidos
    INVALID_RUCS_CACHE_KEY = "migo_invalid_rucs"
    INVALID_RUC_TTL_HOURS = 24  # RUCs inválidos se cachean por 24 horas

    def __init__(self, token=None):
        self.service = ApiService.objects.filter(service_type="MIGO").first()
        if not self.service:
            raise ValueError("Servicio APIMIGO no configurado")

        self.token = token or self.service.auth_token
        self.base_url = self.service.base_url        
        self.cache_service = APICacheService()
        self.invalid_rucs_cache_key = "invalid_rucs_cache"

        # Mapeo de endpoints MIGO
        # self.endpoints = {
        #     "consulta_cuenta": self._get_endpoint("consulta_cuenta", "/api/v1/account"),
        #     "consulta_ruc": self._get_endpoint("consulta_ruc", "/api/v1/ruc"),
        #     "consulta_dni": self._get_endpoint("consulta_dni", "/api/v1/dni"),
        #     "consulta_ruc_masivo": self._get_endpoint(
        #         "consulta_ruc_masivo", "/api/v1/ruc/collection"
        #     ),
        #     "tipo_cambio_latest": self._get_endpoint(
        #         "tipo_cambio_latest", "/api/v1/exchange/latest"
        #     ),
        #     "tipo_cambio_fecha": self._get_endpoint(
        #         "tipo_cambio_fecha", "/api/v1/exchange/date"
        #     ),
        #     "tipo_cambio_rango": self._get_endpoint(
        #         "tipo_cambio_rango", "/api/v1/exchange"
        #     ),
        #     "representantes_legales": self._get_endpoint(
        #         "representantes_legales", "/api/v1/ruc/representantes-legales"
        #     ),
        # }
        # Mantener compatibilidad con métodos existentes
        # self.endpoint_aliases = {
        #     "account": "consulta_cuenta",
        #     "ruc": "consulta_ruc",
        #     "dni": "consulta_dni",
        # }

    def _get_endpoint(self, endpoint_name: str) -> Optional[ApiEndpoint]:
        """
        Obtiene la configuración de un endpoint desde la base de datos.
        
        Args:
            endpoint_name: Nombre del endpoint
            
        Returns:
            ApiEndpoint o None si no se encuentra
        """
        try:
            return ApiEndpoint.objects.filter(
                service=self.service,
                name=endpoint_name
            ).first()
        except Exception as e:
            logger.error(f"Error obteniendo endpoint {endpoint_name}: {str(e)}")
            return None

    def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
        """
        Verifica rate limit y lanza excepción si se excede.
        Args:
            endpoint_name: Nombre del endpoint
        Returns:
            Tuple[bool, float]: (puede_proceder, tiempo_espera_segundos)
        """
        try:
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
        Actualiza rate limit después de una llamada.
        Incrementa el contador de peticiones realizadas.
        
        Args:
            endpoint_name: Nombre del endpoint
        """
        try:
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
    
    def _log_api_call(self, endpoint_name: str, request_data: dict, 
                     response_data: dict, status: str, error_message: str = "", 
                     duration_ms: int = 0, batch_request: ApiBatchRequest = None,
                     caller_info: str = None) -> None:
        """
        Registra llamada API en base de datos.
        FUNCIÓN EXISTENTE: Mejorada para manejar RUCs inválidos.
        
        Args:
            endpoint_name: Nombre del endpoint
            request_data: Datos de la solicitud
            response_data: Datos de la respuesta
            status: Estado de la llamada
            error_message: Mensaje de error (opcional)
            duration_ms: Duración en milisegundos
            batch_request: Solicitud por lote (opcional)
            caller_info: Información del llamador (opcional)
        """
        if caller_info is None:
            caller_info = self._get_caller_info()
        
        try:
            endpoint = self._get_endpoint(endpoint_name)
            
            # Si es un RUC inválido (404), registrar información adicional
            if status == "FAILED" and "404" in error_message:
                response_data['invalid_ruc'] = True
                response_data['invalid_reason'] = "RUC_NO_EXISTE_SUNAT"
            
            ApiCallLog.objects.create(
                service=self.service,
                endpoint=endpoint,
                batch_request=batch_request,
                status=status,
                request_data=request_data,
                response_data=response_data,
                response_code=response_data.get('status_code', 200) if isinstance(response_data, dict) else 200,
                error_message=error_message[:500],
                duration_ms=duration_ms,
                called_from=caller_info
            )
        except Exception as e:
            logger.error(f"Error logging API call: {str(e)}")
    
    def _make_request(self, endpoint_name: str, data: dict = None, method: str = 'POST',
                     batch_request: ApiBatchRequest = None, retry_count: int = 0, 
                     max_retries: int = 2) -> Dict[str, Any]:
        """
        Realiza una petición HTTP a la API Migo.
        FUNCIÓN EXISTENTE: Mantenida con lógica mejorada para RUCs inválidos.
        Args:
            endpoint_name: Nombre del endpoint
            data: Datos para la petición
            method: Método HTTP
            batch_request: Solicitud por lote
            retry_count: Contador de reintentos actual
            max_retries: Máximo número de reintentos
        Returns:
            Dict con la respuesta de la API
        """
        start_time = timezone.now()
        endpoint = self._get_endpoint(endpoint_name)
        
        if not endpoint:
            return {
                "success": False,
                "error": f"Endpoint {endpoint_name} no configurado"
            }
        
        # Verificar rate limit
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
        
        # Preparar datos de la petición
        request_data = data or {}
        if 'token' not in request_data:
            request_data['token'] = self.token
        
        try:
            # Realizar la petición
            if method.upper() == 'POST':
                response = requests.post(
                    f"{self.base_url}{endpoint.path}",
                    json=request_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=endpoint.timeout or 30
                )
            else:
                response = requests.get(
                    f"{self.base_url}{endpoint.path}",
                    params=request_data,
                    timeout=endpoint.timeout or 30
                )
            
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            # Procesar respuesta
            if response.status_code == 200:
                response_data = response.json()
                
                # Verificar si la respuesta indica RUC inválido
                if isinstance(response_data, dict):
                    success = response_data.get('success', True)
                    
                    if not success and '404' in str(response_data.get('error', '')):
                        # RUC no encontrado en SUNAT
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
                # RUC no encontrado - Manejo específico mejorado
                duration_ms = (timezone.now() - start_time).total_seconds() * 1000
                
                # Intentar obtener mensaje de error del response
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'RUC no encontrado en SUNAT')
                except:
                    error_msg = 'RUC no encontrado en SUNAT'
                
                response_data = {
                    "success": False,
                    "error": error_msg,
                    "status_code": 404,
                    "invalid_sunat": True  # Flag específico para RUCs inválidos
                }
                
                # Extraer RUC de la solicitud para marcarlo como inválido
                ruc = None
                if data and 'ruc' in data:
                    ruc = data['ruc']
                elif isinstance(request_data, dict) and 'ruc' in request_data:
                    ruc = request_data['ruc']
                
                if ruc:
                    # Marcar RUC como inválido en cache
                    self._mark_ruc_as_invalid(ruc, "404_NOT_FOUND")
                    response_data['ruc'] = ruc
                
                self._log_api_call(
                    endpoint_name=endpoint_name,
                    request_data=request_data,
                    response_data=response_data,
                    status="RUC_INVALID",  # Nuevo estado específico
                    error_message=error_msg,
                    duration_ms=duration_ms,
                    batch_request=batch_request
                )
                
                self._update_rate_limit(endpoint_name)
                return response_data
                
            else:
                # Otro error HTTP
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
                
                # Reintento para errores 5xx o timeout
                if retry_count < max_retries and response.status_code >= 500:
                    logger.warning(f"Reintentando {endpoint_name}, intento {retry_count + 1}/{max_retries}")
                    time.sleep(2 ** retry_count)  # Backoff exponencial
                    return self._make_request(
                        endpoint_name, data, method, 
                        batch_request, retry_count + 1, max_retries
                    )
                
                self._update_rate_limit(endpoint_name)
                return response_data
                
        except RequestException as e:
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            error_msg = f"Error de conexión: {str(e)}"
            
            response_data = {
                "success": False,
                "error": error_msg
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
            
            # Reintento para errores de conexión
            if retry_count < max_retries:
                logger.warning(f"Reintentando {endpoint_name} por error de conexión, intento {retry_count + 1}/{max_retries}")
                time.sleep(2 ** retry_count)
                return self._make_request(
                    endpoint_name, data, method, 
                    batch_request, retry_count + 1, max_retries
                )
            
            return response_data
        
    def _get_caller_info(self, depth: int = 3) -> str:
        """
        Obtiene información del llamador para logging.        
        Args:
            depth: Profundidad del stack trace a analizar            
        Returns:
            str: Información del llamador
        """
        import inspect
        try:
            frame = inspect.currentframe()
            for _ in range(depth):
                if frame:
                    frame = frame.f_back
            if frame:
                return f"{frame.f_code.co_filename}:{frame.f_lineno} - {frame.f_code.co_name}"
        except:
            pass
        return "unknown_caller"

    def _validate_ruc_format(self, ruc: str) -> Tuple[bool, str]:
        """
        NUEVA FUNCIÓN: Agregada para validación previa.
        Valida el formato básico de un RUC peruano.        
        Args:
            ruc: Número de RUC a validar            
        Returns:
            Tuple[bool, str]: (es_válido, mensaje_error)
        """
        if not ruc:
            return False, "RUC vacío"
        
        # Convertir a string si es necesario
        if not isinstance(ruc, str):
            ruc = str(ruc)
        
        # Verificar que sean solo dígitos
        if not ruc.isdigit():
            return False, "RUC debe contener solo dígitos"
        
        # Verificar longitud (11 dígitos para RUC peruano)
        if len(ruc) != 11:
            return False, f"RUC debe tener 11 dígitos, tiene {len(ruc)}"
                
        # Verificar RUCs de prueba conocidos (del dataset problemático)
        rucs_prueba_conocidos = {
            '20678901234': 'RUC de prueba - secuencia numérica',
            '20123456789': 'RUC de prueba - secuencia numérica', 
            '20456789012': 'RUC de prueba - secuencia numérica',
            '20789012345': 'RUC de prueba - secuencia numérica',
            '20890123456': 'RUC de prueba - secuencia numérica'
        }
        
        if ruc in rucs_prueba_conocidos:
            return False, rucs_prueba_conocidos[ruc]
        
        # Verificar patrones sospechosos (todos iguales, secuencias, etc.)
        if len(set(ruc)) == 1:  # Todos los dígitos iguales
            return False, "RUC con patrón inválido (todos dígitos iguales)"
        
        return True, ""
    
    def _is_ruc_marked_invalid(self, ruc: str) -> bool:
        """
        NUEVA FUNCIÓN: Agregada para validación previa.
        Verifica si un RUC está marcado como inválido en el cache.        
        Args:
            ruc: Número de RUC a verificar            
        Returns:
            bool: True si el RUC está marcado como inválido
        """
        invalid_rucs = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {})
        return ruc in invalid_rucs
    
    def _mark_ruc_as_invalid(self, ruc: str, reason: str = "NO_EXISTE_SUNAT"):
        """
        NUEVA FUNCIÓN: Agregada para validación previa.
        Marca un RUC como inválido en el cache.        
        Args:
            ruc: Número de RUC a marcar como inválido
            reason: Razón por la cual es inválido
        """
        invalid_rucs = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {})
        invalid_rucs[ruc] = {
            'reason': reason,
            'timestamp': timezone.now().isoformat(),
            'ttl_hours': self.INVALID_RUC_TTL_HOURS
        }
        self.cache_service.set(
            self.INVALID_RUCS_CACHE_KEY, 
            invalid_rucs, 
            ttl=self.INVALID_RUC_TTL_HOURS * 3600
        )
        logger.info(f"RUC {ruc} marcado como inválido: {reason}")
        
    def _update_partner_sunat_status(self, ruc: str, api_response: Dict[str, Any]) -> None:
        """
        NUEVA FUNCIÓN: Para mantener actualizado el estado de partners.
        Actualiza el estado SUNAT de un partner basado en la respuesta de la API.        
        Args:
            ruc: Número de RUC del partner
            api_response: Respuesta de la API Migo
        """
        try:
            # Buscar partner por RUC o num_document
            partner = Partner.objects.filter(num_document=ruc).first()
            
            if not partner:
                logger.debug(f"Partner con RUC {ruc} no encontrado en la base de datos")
                return
            
            with transaction.atomic():
                is_valid = api_response.get('success', False)
                
                if not is_valid:
                    # RUC inválido o no encontrado
                    partner.sunat_valid = False
                    partner.sunat_state = 'NO_VERIFICADO'
                    partner.sunat_condition = 'NO_VERIFICADO'
                    
                    error_msg = api_response.get('error', 'RUC inválido')
                    
                    # Agregar nueva observación manteniendo las anteriores
                    new_comment = f"[{timezone.now().date()}] SUNAT: {error_msg}\n"
                    partner.sunat_comment = new_comment[:1000]  # Limitar longitud
                    
                    logger.info(f"Partner {ruc} marcado como inválido en SUNAT: {error_msg}")
                    
                else:
                    # RUC válido con datos
                    data = api_response.get('data', {})
                    partner.sunat_valid = True
                    partner.sunat_state = data.get('estado_del_contribuyente', 'NO_VERIFICADO')
                    partner.sunat_condition = data.get('condicion_de_domicilio', 'NO_VERIFICADO')
                    partner.sunat_last_check = timezone.now()
                    
                    # Guardar datos de dirección si están disponibles
                    if 'direccion_simple' in data:
                        partner.sunat_address = data['direccion_simple'][:500]
                    if 'ubigeo' in data:
                        partner.sunat_ubigeo = data['ubigeo'][:6]
                    
                    # Agregar observación de verificación exitosa
                    new_comment = f"[{timezone.now().date()}] SUNAT: Validación exitosa\n"
                    partner.sunat_comment = new_comment[:1000]
                    
                    logger.info(f"Partner {ruc} actualizado con datos SUNAT válidos")
                
                partner.save()
                
        except Exception as e:
            logger.error(f"Error actualizando estado SUNAT para partner {ruc}: {str(e)}")
         
    # Métodos específicos de APIMIGO
    def consultar_cuenta(self):
        """Consulta información de la cuenta MIGO"""
        return self._make_request(
            endpoint_name="consulta_cuenta",
            payload={},
            endpoint_name_display="Consulta cuenta APIMIGO",
        )

    # v1
    def consultar_ruc(self, ruc) -> dict:
        """Consulta individual de un RUC en SUNAT"""
        cache_key = f"ruc_{ruc}"

        # 1. Verificar cache primero
        cached_data = self.cache_service.get(cache_key)
        if cached_data:
            return {**cached_data, "cache_hit": True}

        # 2. Hacer consulta si no está en cache
        try:
            result = self._make_request("consulta_ruc", {"ruc": ruc})

            # Cachear por 24 horas si se encuentra
            if result.get("success"):
                cache.set(cache_key, result, 86400)
                return result.json()
            elif response.status_code == 404:
                # Manejar RUC no encontrado
                return {
                    "success": False,
                    "error": "RUC no encontrado",
                    "status_code": 404,
                }
            else:
                return {
                    "success": False,
                    "error": f"Error {response.status_code}",
                    "status_code": response.status_code,
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def consultar_ruc(self, ruc: str, force_refresh: bool = False, 
                     update_partner: bool = True) -> Dict[str, Any]:
        """
        Consulta individual de RUC con manejo mejorado de RUCs inválidos.
        FUNCIÓN EXISTENTE: Mejorada con validación y cache de inválidos.
        
        Args:
            ruc: Número de RUC a consultar
            force_refresh: Ignorar cache y forzar consulta a API
            update_partner: Actualizar estado del partner en base de datos
            
        Returns:
            Dict con la respuesta de la API
        """
        start_time = timezone.now()
        
        # 1. Validar formato del RUC antes de cualquier consulta
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
        
        # 2. Verificar si el RUC está marcado como inválido en cache
        if not force_refresh and self._is_ruc_marked_invalid(ruc):
            logger.debug(f"RUC {ruc} encontrado en cache de inválidos, omitiendo consulta")
            duration_ms = (timezone.now() - start_time).total_seconds() * 1000
            
            invalid_info = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {}).get(ruc, {})
            api_response = {
                "success": False,
                "error": f"RUC marcado como inválido: {invalid_info.get('reason', 'Desconocido')}",
                "ruc": ruc,
                "cache_hit": True,
                "cache_type": "invalid"
            }
            
            self._log_api_call(
                endpoint_name="consultar_ruc",
                request_data={"ruc": ruc},
                response_data=api_response,
                status="CACHE_INVALID",
                error_message=api_response["error"],
                duration_ms=duration_ms
            )
            
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
            
            return api_response
        
        # 3. Verificar cache normal (para RUCs válidos)
        if not force_refresh:
            cache_key = f"ruc_{ruc}"
            cached_data = self.cache_service.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit para RUC {ruc} (válido)")
                duration_ms = (timezone.now() - start_time).total_seconds() * 1000
                api_response = {**cached_data, "cache_hit": True, "cache_type": "valid"}
                
                if update_partner:
                    self._update_partner_sunat_status(ruc, api_response)
                
                return api_response
        
        # 4. Consultar API usando _make_request existente
        request_data = {"ruc": ruc}
        api_response = self._make_request("consultar_ruc", data=request_data)
        
        # 5. Procesar respuesta
        if api_response.get("success"):
            # RUC válido - guardar en cache normal
            cache_key = f"ruc_{ruc}"
            self.cache_service.set(cache_key, api_response, ttl=3600)
            
            # Actualizar partner
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
                
        elif api_response.get("invalid_sunat"):
            # RUC inválido en SUNAT - ya fue marcado en _make_request
            if update_partner:
                self._update_partner_sunat_status(ruc, api_response)
        
        return api_response
    
    def consultar_dni(self, dni):
        """Consulta datos de un DNI"""
        cache_key = f"migo_dni_{dni}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        result = self._make_request("consulta_dni", {"dni": dni})

        # Cachear por 24 horas
        if result.get("success"):
            cache.set(cache_key, result, 86400)

        return result

    def consultar_tipo_cambio_latest(self):
        """
        Consulta el tipo de cambio más reciente.
        Endpoint: POST /api/v1/exchange/latest
        Returns:
            Dict: Tipo de cambio del día más reciente
        """
        return self._make_request(
            endpoint_name="tipo_cambio_latest",
            payload={"token": self.token},
            endpoint_name_display="Consulta tipo cambio más reciente",
        )

    def consultar_tipo_cambio_fecha(self, fecha):
        """
        Consulta tipo de cambio para una fecha específica.
        Endpoint: POST /api/v1/exchange/date
        Args:
            fecha: Fecha en formato YYYY-MM-DD
        Returns:
            Dict: Tipo de cambio para la fecha especificada
        """
        return self._make_request(
            endpoint_name="tipo_cambio_fecha",
            payload={"token": self.token, "fecha": fecha},
            endpoint_name_display=f"Consulta tipo cambio fecha {fecha}",
        )

    def consultar_tipo_cambio_rango(self, fecha_inicio, fecha_fin):
        """
        Consulta tipo de cambio por rango de fechas.
        Endpoint: POST /api/v1/exchange
        Args:
            fecha_inicio: Fecha inicio (YYYY-MM-DD)
            fecha_fin: Fecha fin (YYYY-MM-DD)
        Returns:
            Dict: Tipos de cambio en el rango
        """
        return self._make_request(
            endpoint_name="tipo_cambio_rango",
            payload={
                "token": self.token,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
            },
            endpoint_name_display=f"Consulta tipo cambio rango {fecha_inicio} a {fecha_fin}",
        )

    def consultar_representantes_legales(self, ruc):
        """
        Consulta representantes legales de un RUC.
        Endpoint: POST /api/v1/ruc/representantes-legales
        Args:
            ruc: Número de RUC
        Returns:
            Dict: Lista de representantes legales
        """
        return self._make_request(
            endpoint_name="representantes_legales",
            payload={"token": self.token, "ruc": ruc},
            endpoint_name_display="Consulta representantes legales",
        )

    def validar_ruc_para_facturacion(self, ruc):
        """Verificación específica para facturación: RUC activo y habido"""

        try:
            resultado = self.consultar_ruc(ruc)

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
            print(f"Error validando RUC {ruc}: {e}")
            return {
                "valido": False,
                "ruc": ruc,
                "razon_social": None,
                "errores": [f"Error de validación: {str(e)}"],
                "advertencias": [],
            }

    def _particionar_rucs_en_lotes(self, ruc_list, tamano_lote=None):
        """
        Particiona una lista de RUCs en lotes del tamaño especificado.
        Args:
            ruc_list: Lista de RUCs a particionar
            tamano_lote: Tamaño máximo de cada lote (por defecto 100, límite de APIMIGO)
        Returns:
            Lista de lotes (cada lote es una lista de RUCs)
        Ejemplo:
            >>> _particionar_rucs_en_lotes([1,2,3,4,5], 2)
            [[1,2], [3,4], [5]]
        """
        if not isinstance(ruc_list, list):
            raise ValueError("ruc_list debe ser una lista")
        # Determinar tamaño de lote
        if tamano_lote is None:
            if (
                self.service
                and hasattr(self.service, "max_batch_size")
                and self.service.max_batch_size
            ):
                tamano_lote = self.service.max_batch_size
            else:
                tamano_lote = 100  # Valor por defecto seguro
        if tamano_lote <= 0:
            raise ValueError("tamano_lote debe ser mayor a 0")

        # Normalizar RUCs antes de particionar
        lotes = []
        lote_actual = []

        for ruc in ruc_list:
            # Normalizar cada RUC
            if isinstance(ruc, (int, float)):
                ruc_normalizado = str(int(ruc))
            elif isinstance(ruc, str):
                ruc_normalizado = ruc.strip()
            else:
                raise ValueError(f"Tipo de dato no válido para RUC: {type(ruc)}")

            # Validar formato básico
            if len(ruc_normalizado) != 11 or not ruc_normalizado.isdigit():
                raise ValueError(
                    f"RUC inválido: {ruc_normalizado}. Debe tener 11 dígitos"
                )

            lote_actual.append(ruc_normalizado)

            # Si el lote alcanzó el tamaño máximo, agregarlo y comenzar uno nuevo
            if len(lote_actual) >= tamano_lote:
                lotes.append(lote_actual)
                lote_actual = []

        # Agregar el último lote si no está vacío
        if lote_actual:
            lotes.append(lote_actual)

        return lotes

    def _analizar_facturacion(self, resultados):
        """
        Analiza qué RUCs están habilitados para facturación según SUNAT.

        Criterios para facturación válida:
        1. Estado: ACTIVO (no BAJA, SUSPENSION_TEMPORAL, etc.)
        2. Condición: HABIDO (no NO_HABIDO)
        3. Tipo de contribuyente: No debe ser EXTRANJERO_NO_DOMICILIADO sin ciertas condiciones
        4. Ubicación: Debe tener dirección válida en Perú

        Args:
            resultados: Lista de diccionarios con datos de RUC

        Returns:
            dict con análisis de facturación
        """
        habilitados = []
        no_habilitados = []
        advertencias = []

        for item in resultados:
            if not isinstance(item, dict) or not item.get("success"):
                # Si no es exitoso, no se puede analizar
                no_habilitados.append(
                    {
                        "ruc": item.get("ruc", "DESCONOCIDO"),
                        "razon": item.get("nombre_o_razon_social", ""),
                        "motivo": "Consulta fallida",
                        "detalle": item.get("error", "Error desconocido"),
                    }
                )
                continue

            ruc = item.get("ruc")
            razon = item.get("nombre_o_razon_social", "")
            estado = item.get("estado_del_contribuyente", "")
            condicion = item.get("condicion_de_domicilio", "")
            tipo_contribuyente = item.get("tipo_contribuyente", "")

            motivos_rechazo = []
            advertencias_ruc = []

            # 1. Verificar estado
            if estado != "ACTIVO":
                motivos_rechazo.append(f"Estado: {estado}")

            # 2. Verificar condición
            if condicion != "HABIDO":
                motivos_rechazo.append(f"Condición: {condicion}")

            # 3. Verificar tipo de contribuyente
            if tipo_contribuyente in ["EXTRANJERO_NO_DOMICILIADO", "NO_DOMICILIADO"]:
                advertencias_ruc.append(
                    f"Tipo contribuyente: {tipo_contribuyente} - Verificar retenciones"
                )

            # 4. Verificar dirección
            direccion = item.get("direccion", "")
            if not direccion or len(direccion.strip()) < 10:
                advertencias_ruc.append("Dirección incompleta o muy corta")

            # 5. Verificar actualización (si tiene más de 1 año, podría estar desactualizado)
            actualizado_en = item.get("actualizado_en", "")
            if actualizado_en:
                try:
                    from datetime import datetime

                    fecha_actualizacion = datetime.strptime(
                        actualizado_en, "%Y-%m-%d %H:%M:%S"
                    )
                    dias_desde_actualizacion = (
                        datetime.now() - fecha_actualizacion
                    ).days
                    if dias_desde_actualizacion > 365:
                        advertencias_ruc.append(
                            f"Datos desactualizados ({dias_desde_actualizacion} días)"
                        )
                except:
                    pass

            # Clasificar resultado
            if not motivos_rechazo:
                habilitados.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "estado": estado,
                        "condicion": condicion,
                        "advertencias": advertencias_ruc,
                        "direccion": (
                            direccion[:100] + "..."
                            if len(direccion) > 100
                            else direccion
                        ),
                        "actualizado_en": actualizado_en,
                    }
                )
            else:
                # if motivos_rechazo:
                no_habilitados.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "motivos": motivos_rechazo,
                        "estado": estado,
                        "condicion": condicion,
                    }
                )

            if advertencias_ruc:
                advertencias.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "advertencias": advertencias_ruc,
                    }
                )

        return {
            "total_analizados": len(resultados),
            "habilitados_facturacion": {
                "cantidad": len(habilitados),
                "porcentaje": (
                    (len(habilitados) / len(resultados) * 100) if resultados else 0
                ),
                "items": habilitados,
            },
            "no_habilitados_facturacion": {
                "cantidad": len(no_habilitados),
                "porcentaje": (
                    (len(no_habilitados) / len(resultados) * 100) if resultados else 0
                ),
                "items": no_habilitados,
            },
            "advertencias": {
                "cantidad": len(advertencias),
                "porcentaje": (
                    (len(advertencias) / len(resultados) * 100) if resultados else 0
                ),
                "items": advertencias,
            },
        }

    def validar_rucs_para_facturacion(self, ruc_list):
        """
        Valida específicamente si RUCs están habilitados para facturación.
        Args:
            ruc_list: Lista de RUCs a validar
        Returns:
            dict con validación detallada por RUC
        """
        # Consultar los RUCs
        resultado = self.consultar_ruc_masivo(ruc_list)

        if not resultado.get("success"):
            return {
                "success": False,
                "error": resultado.get("error", "Error en consulta"),
                "validaciones": [],
            }

        validaciones = []

        for ruc_data in resultado.get("results", []):
            ruc = ruc_data.get("ruc", "")
            razon = ruc_data.get("nombre_o_razon_social", "")

            if not ruc_data.get("success"):
                validaciones.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "valido_facturacion": False,
                        "motivo": "Consulta fallida",
                        "detalles": ruc_data.get("error", "Error desconocido"),
                    }
                )
                continue

            # Aplicar criterios de facturación
            criterios = {
                "estado_activo": ruc_data.get("estado_del_contribuyente") == "ACTIVO",
                "habido": ruc_data.get("condicion_de_domicilio") == "HABIDO",
                "direccion_valida": len(ruc_data.get("direccion", "").strip()) > 10,
                "datos_actualizados": "actualizado_en" in ruc_data,
            }

            valido = all(criterios.values())

            validaciones.append(
                {
                    "ruc": ruc,
                    "razon_social": razon,
                    "valido_facturacion": valido,
                    "criterios": criterios,
                    "estado": ruc_data.get("estado_del_contribuyente"),
                    "condicion": ruc_data.get("condicion_de_domicilio"),
                    "direccion": (
                        ruc_data.get("direccion", "")[:50] + "..."
                        if len(ruc_data.get("direccion", "")) > 50
                        else ruc_data.get("direccion", "")
                    ),
                    "motivo": (
                        "Válido"
                        if valido
                        else ", ".join([k for k, v in criterios.items() if not v])
                    ),
                }
            )

        # Resumen
        validos = [v for v in validaciones if v["valido_facturacion"]]

        return {
            "success": True,
            "total_rucs": len(ruc_list),
            "validos_facturacion": len(validos),
            "invalidos_facturacion": len(validaciones) - len(validos),
            "porcentaje_valido": (
                (len(validos) / len(validaciones) * 100) if validaciones else 0
            ),
            "validaciones": validaciones,
            "resumen_criterios": {
                "estado_activo": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("estado_activo", False)
                ),
                "habido": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("habido", False)
                ),
                "direccion_valida": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("direccion_valida", False)
                ),
                "datos_actualizados": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("datos_actualizados", False)
                ),
            },
        }

    def consultar_ruc_masivo_completo(self, ruc_list, batch_id=None, tamano_lote=None):
        """
        Consulta masiva de RUCs sin límite de cantidad (usa particionado automático).

        Args:
            ruc_list: Lista de RUCs a consultar (cualquier cantidad)
            batch_id: ID de ApiBatchRequest para tracking
            tamano_lote: Tamaño de cada lote (máximo 100 por APIMIGO, por defecto 100)

        Returns:
            dict con resultados consolidados de todos los lotes
        """
        if tamano_lote is None:
            if (
                self.service
                and hasattr(self.service, "max_batch_size")
                and self.service.max_batch_size
            ):
                tamano_lote = self.service.max_batch_size
            else:
                tamano_lote = 100
        logger.info(
            f"Iniciando consulta masiva completa de {len(ruc_list)} RUCs con lotes de {tamano_lote}"
        )

        # Validar entrada
        if not isinstance(ruc_list, list):
            raise ValueError("ruc_list debe ser una lista")

        if len(ruc_list) == 0:
            return {
                "success": True,
                "total_requested": 0,
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
                "summary": {"activos": 0, "habidos": 0},
                "lotes_procesados": 0,
            }

        # Registrar batch request si se proporciona batch_id
        batch_request = None
        if batch_id:
            try:
                batch_request = ApiBatchRequest.objects.get(id=batch_id)
                batch_request.status = "PROCESSING"
                batch_request.total_items = len(ruc_list)
                batch_request.processed_items = 0
                batch_request.successful_items = 0
                batch_request.failed_items = 0
                batch_request.save()
            except ApiBatchRequest.DoesNotExist:
                pass

        try:
            # Particionar RUCs en lotes
            lotes = self._particionar_rucs_en_lotes(ruc_list, tamano_lote)

            # Resultados consolidados
            todos_resultados = []
            total_exitosos = 0
            total_fallidos = 0
            total_procesados = 0

            # Procesar cada lote
            for i, lote in enumerate(lotes):
                logger.info(
                    f"Procesando lote {i + 1}/{len(lotes)} con {len(lote)} RUCs"
                )

                try:
                    # Consultar el lote actual
                    resultado_lote = self.consultar_ruc_masivo(lote)

                    # Si el lote fue exitoso, procesar resultados
                    if resultado_lote.get("success"):
                        resultados_lote = resultado_lote.get("results", [])
                        todos_resultados.extend(resultados_lote)

                        # Contar exitosos y fallidos
                        for item in resultados_lote:
                            if isinstance(item, dict) and item.get("success", False):
                                total_exitosos += 1
                            else:
                                total_fallidos += 1

                        total_procesados += len(resultados_lote)

                        # Actualizar batch request si existe
                        if batch_request:
                            batch_request.processed_items = total_procesados
                            batch_request.successful_items = total_exitosos
                            batch_request.failed_items = total_fallidos
                            batch_request.save()

                    else:
                        # Si falló todo el lote
                        total_fallidos += len(lote)
                        total_procesados += len(lote)

                        # Crear registros fallidos para cada RUC del lote
                        for ruc in lote:
                            todos_resultados.append(
                                {
                                    "success": False,
                                    "ruc": ruc,
                                    "error": resultado_lote.get(
                                        "error", "Error en consulta masiva"
                                    ),
                                }
                            )

                        if batch_request:
                            batch_request.failed_items += len(lote)
                            batch_request.processed_items += len(lote)
                            batch_request.save()

                    # Respetar rate limiting entre lotes (mínimo 2 segundos)
                    if i < len(lotes) - 1:  # No esperar después del último lote
                        time.sleep(2)

                except Exception as e:
                    logger.error(f"Error procesando lote {i + 1}: {str(e)}")
                    total_fallidos += len(lote)
                    total_procesados += len(lote)

                    # Crear registros fallidos para cada RUC del lote
                    for ruc in lote:
                        todos_resultados.append(
                            {
                                "success": False,
                                "ruc": ruc,
                                "error": f"Error en lote: {str(e)}",
                            }
                        )

                    if batch_request:
                        batch_request.failed_items += len(lote)
                        batch_request.processed_items += len(lote)
                        batch_request.save()

                    # Continuar con el siguiente lote
                    continue

            # Calcular estadísticas finales
            activos = len(
                [
                    r
                    for r in todos_resultados
                    if isinstance(r, dict)
                    and r.get("success")
                    and r.get("estado_del_contribuyente") == "ACTIVO"
                ]
            )

            habidos = len(
                [
                    r
                    for r in todos_resultados
                    if isinstance(r, dict)
                    and r.get("success")
                    and r.get("condicion_de_domicilio") == "HABIDO"
                ]
            )

            # Actualizar batch request final si existe
            if batch_request:
                batch_request.results = {
                    "successful": [r for r in todos_resultados if r.get("success")],
                    "failed": [r for r in todos_resultados if not r.get("success")],
                    "total": len(todos_resultados),
                }
                batch_request.processed_items = total_procesados
                batch_request.successful_items = total_exitosos
                batch_request.failed_items = total_fallidos
                batch_request.status = "COMPLETED" if total_fallidos == 0 else "PARTIAL"
                batch_request.completed_at = timezone.now()
                batch_request.save()

            # Retornar resultados consolidados
            return {
                "success": True,
                "total_requested": len(ruc_list),
                "total_processed": total_procesados,
                "successful": total_exitosos,
                "failed": total_fallidos,
                "results": todos_resultados,
                "summary": {
                    "activos": activos,
                    "habidos": habidos,
                },
                "lotes_procesados": len(lotes),
                "batch_id": batch_request.id if batch_request else None,
            }

        except Exception as e:
            # Manejar errores globales
            if batch_request:
                batch_request.status = "FAILED"
                batch_request.error_summary = {"error": str(e)}
                batch_request.completed_at = timezone.now()
                batch_request.save()

            error_msg = f"Error en consulta masiva completa: {str(e)}"
            error_msg += f"\nRUCs totales: {len(ruc_list)}"
            error_msg += (
                f"\nPrimeros RUCs: {ruc_list[:5] if len(ruc_list) > 5 else ruc_list}"
            )
            raise Exception(error_msg)

    def consultar_ruc_masivo(self, rucs: List[str], batch_size: int = 50,
                           update_partners: bool = True) -> Dict[str, Any]:
        """
        Consulta masiva de RUCs con manejo optimizado de inválidos.
        FUNCIÓN EXISTENTE: Mejorada con filtrado de inválidos y procesamiento por lotes.
        
        Args:
            rucs: Lista de RUCs a consultar
            batch_size: Tamaño de lote para procesamiento
            update_partners: Actualizar estado de partners en base de datos
            
        Returns:
            Dict con resultados consolidados
        """
        if not rucs:
            return {
                "success": False,
                "error": "Lista de RUCs vacía",
                "total": 0
            }
        
        # Filtrar RUCs únicos
        rucs_unicos = list(set(rucs))
        duplicates_removed = len(rucs) - len(rucs_unicos)
        
        resultados = {
            "success": True,
            "total_rucs": len(rucs),
            "unique_rucs": len(rucs_unicos),
            "duplicates_removed": duplicates_removed,
            "validos": [],
            "invalidos": [],
            "errores": [],
            "cache_hits": 0,
            "api_calls": 0,
            "batches_processed": 0
        }
        
        # Pre-filtrar RUCs con formato inválido
        rucs_a_procesar = []
        rucs_invalidos_formato = []
        
        for ruc in rucs_unicos:
            is_valid_format, format_error = self._validate_ruc_format(ruc)
            if is_valid_format:
                rucs_a_procesar.append(ruc)
            else:
                rucs_invalidos_formato.append({
                    "ruc": ruc,
                    "error": format_error,
                    "type": "invalid_format"
                })
                resultados["invalidos"].append({
                    "ruc": ruc,
                    "error": format_error,
                    "type": "invalid",
                    "subtype": "format"
                })
        
        # Procesar RUCs válidos en formato
        for i in range(0, len(rucs_a_procesar), batch_size):
            batch = rucs_a_procesar[i:i + batch_size]
            resultados["batches_processed"] += 1
            
            logger.info(f"Procesando lote {resultados['batches_processed']}: {len(batch)} RUCs")
            
            # Consultar lote usando endpoint masivo (si existe) o individualmente
            try:
                # Intentar consulta masiva
                request_data = {
                    "ruc": batch,
                    "token": self.token
                }
                
                batch_response = self._make_request("consultar_ruc_masivo", data=request_data)
                
                # Procesar respuesta masiva
                # La API puede devolver:
                # 1. Una lista directa de diccionarios (nuevo formato)
                # 2. Un diccionario con "data" que contiene la lista (formato legado)
                response_data = None
                
                if isinstance(batch_response, list):
                    # Caso 1: Respuesta es directamente una lista
                    response_data = batch_response
                elif isinstance(batch_response, dict) and batch_response.get("success"):
                    # Caso 2: Respuesta es un diccionario con éxito
                    if isinstance(batch_response.get("data"), list):
                        response_data = batch_response["data"]
                
                if response_data is not None and isinstance(response_data, list):
                    # Procesar la lista de resultados
                    for item in response_data:
                        if isinstance(item, dict):
                            ruc = item.get("ruc")
                            is_success = item.get("success", False)
                            
                            if is_success:
                                # RUC válido en SUNAT
                                resultados["validos"].append({
                                    "ruc": ruc,
                                    "data": item
                                })
                                
                                # Actualizar partner si se solicita
                                if update_partners:
                                    self._update_partner_sunat_status(ruc, {"success": True, "data": item})
                                
                                # Marcar como válido removiendo del cache de inválidos si existe
                                if self._is_ruc_marked_invalid(ruc):
                                    self.clear_invalid_rucs_cache(ruc)
                            else:
                                # RUC no encontrado o error en SUNAT
                                resultados["invalidos"].append({
                                    "ruc": ruc,
                                    "error": item.get("error", "RUC no encontrado en SUNAT"),
                                    "type": "invalid",
                                    "subtype": "sunat"
                                })
                                
                                # Marcar como inválido
                                self._mark_ruc_as_invalid(ruc, "NO_EXISTE_SUNAT")
                                
                                # Actualizar partner si se solicita
                                if update_partners:
                                    self._update_partner_sunat_status(ruc, {"success": False, "error": item.get("error", "No encontrado")})
                        else:
                            # Item no es un diccionario
                            resultados["errores"].append({
                                "ruc": "unknown",
                                "error": "Formato inválido en respuesta",
                                "type": "error"
                            })
                    
                    resultados["api_calls"] += 1
                    
                elif batch_response.get("success") is False:
                    # API devolvió error general
                    logger.warning(f"Error en consulta masiva: {batch_response.get('error', 'Error desconocido')}")
                    # Procesar individualmente como fallback
                    self._process_batch_individually(
                        batch, resultados, update_partners
                    )
                else:
                    # Respuesta inesperada
                    logger.warning(f"Respuesta inesperada de la API: {type(batch_response)}")
                    # Procesar individualmente como fallback
                    self._process_batch_individually(
                        batch, resultados, update_partners
                    )
                    
            except Exception as e:
                logger.error(f"Error procesando lote: {str(e)}")
                # Procesar individualmente como fallback
                self._process_batch_individually(
                    batch, resultados, update_partners
                )
        
        # Estadísticas finales
        resultados["total_validos"] = len(resultados["validos"])
        resultados["total_invalidos"] = len(resultados["invalidos"])
        resultados["total_errores"] = len(resultados["errores"])
        
        logger.info(f"Procesamiento masivo completado: "
                   f"{resultados['total_validos']} válidos, "
                   f"{resultados['total_invalidos']} inválidos, "
                   f"{resultados['total_errores']} errores")
        
        return resultados

    def _process_batch_individually(self, batch: List[str], resultados: Dict[str, Any],
                                  update_partners: bool) -> None:
        """
        Procesa un lote de RUCs individualmente.
        NUEVA FUNCIÓN: Helper para procesamiento individual.
        
        Args:
            batch: Lista de RUCs a procesar
            resultados: Dict donde almacenar resultados
            update_partners: Si actualizar partners
        """
        for ruc in batch:
            # Verificar cache de inválidos primero
            if self._is_ruc_marked_invalid(ruc):
                resultados["cache_hits"] += 1
                invalid_info = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {}).get(ruc, {})
                resultados["invalidos"].append({
                    "ruc": ruc,
                    "error": f"RUC en cache inválidos: {invalid_info.get('reason', 'Desconocido')}",
                    "type": "invalid",
                    "subtype": "cached"
                })
                continue
            
            # Verificar cache normal
            cache_key = f"ruc_{ruc}"
            cached_data = self.cache_service.get(cache_key)
            if cached_data:
                resultados["cache_hits"] += 1
                resultados["validos"].append({
                    "ruc": ruc,
                    "data": cached_data,
                    "cache_hit": True
                })
                if update_partners:
                    self._update_partner_sunat_status(ruc, cached_data)
                continue
            
            # Consultar API individualmente
            api_response = self.consultar_ruc(ruc, update_partner=update_partners)
            resultados["api_calls"] += 1
            
            if api_response.get("success"):
                resultados["validos"].append({
                    "ruc": ruc,
                    "data": api_response.get("data", {})
                })
            elif api_response.get("invalid_sunat") or api_response.get("invalid_format"):
                resultados["invalidos"].append({
                    "ruc": ruc,
                    "error": api_response.get("error"),
                    "type": "invalid",
                    "subtype": "sunat" if api_response.get("invalid_sunat") else "format"
                })
            else:
                resultados["errores"].append({
                    "ruc": ruc,
                    "error": api_response.get("error"),
                    "type": "error"
                })
    
    def get_invalid_rucs_report(self) -> Dict[str, Any]:
        """
        Obtiene un reporte de los RUCs marcados como inválidos.
        NUEVA FUNCIÓN: Para monitoreo y debugging.
        
        Returns:
            Dict con información de RUCs inválidos
        """
        invalid_rucs = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {})
        
        return {
            "total_invalidos": len(invalid_rucs),
            "invalid_rucs": [
                {
                    "ruc": ruc,
                    "reason": data.get("reason"),
                    "timestamp": data.get("timestamp"),
                    "ttl_hours": data.get("ttl_hours")
                }
                for ruc, data in invalid_rucs.items()
            ]
        }
    
    def clear_invalid_rucs_cache(self, ruc: str = None) -> Dict[str, Any]:
        """
        Limpia el cache de RUCs inválidos.
        NUEVA FUNCIÓN: Para mantenimiento.
        
        Args:
            ruc: Si se especifica, limpia solo ese RUC específico
            
        Returns:
            Dict con resultado de la operación
        """
        if ruc:
            invalid_rucs = self.cache_service.get(self.INVALID_RUCS_CACHE_KEY, {})
            if ruc in invalid_rucs:
                del invalid_rucs[ruc]
                self.cache_service.set(
                    self.INVALID_RUCS_CACHE_KEY, 
                    invalid_rucs, 
                    ttl=self.INVALID_RUC_TTL_HOURS * 3600
                )
                logger.info(f"RUC {ruc} removido del cache de inválidos")
                return {"success": True, "message": f"RUC {ruc} removido del cache"}
            else:
                return {"success": False, "message": f"RUC {ruc} no encontrado en cache"}
        else:
            self.cache_service.delete(self.INVALID_RUCS_CACHE_KEY)
            logger.info("Cache de RUCs inválidos limpiado completamente")
            return {"success": True, "message": "Cache de RUCs inválidos limpiado"}    
