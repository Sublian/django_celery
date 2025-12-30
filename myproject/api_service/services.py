from urllib import response
import requests
import time
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from .models import ApiService, ApiEndpoint, ApiCallLog, ApiRateLimit, ApiBatchRequest
import requests
from .exceptions import (
    APIError, RateLimitExceededError, AuthenticationError,
    APINotFoundError, APIBadResponseError, APITimeoutError
)

class MigoAPIClient:
    """Cliente específico para APIMIGO con todas sus funcionalidades"""
    
    def __init__(self, token=None):
        self.service = ApiService.objects.filter(service_type='MIGO').first()
        if not self.service:
            raise ValueError("Servicio APIMIGO no configurado")
        
        self.token = token or self.service.auth_token
        self.base_url = self.service.base_url
        
        # Mapeo de endpoints MIGO
        self.endpoints = {
            'account': self._get_endpoint('account', '/api/v1/account'),
            'ruc': self._get_endpoint('ruc', '/api/v1/ruc'),
            'ruc_collection': self._get_endpoint('ruc_collection', '/api/v1/ruc/collection'),
            'dni': self._get_endpoint('dni', '/api/v1/dni'),
            'tipo_cambio': self._get_endpoint('tipo_cambio', '/api/v1/tipo_cambio'),
            'representantes': self._get_endpoint('representantes', '/api/v1/representantes'),
        }
    
    def _get_endpoint(self, name, path):
        """Obtiene o crea un endpoint en la base de datos"""
        endpoint, created = ApiEndpoint.objects.get_or_create(
            service=self.service,
            path=path,
            defaults={'name': name, 'method': 'POST'}
        )
        return endpoint
    
    def _check_rate_limit(self):
        """Verifica y respeta el rate limiting del servicio"""
        rate_limit_obj = ApiRateLimit.objects.get(service=self.service)
    
        if not rate_limit_obj.can_make_request():
            wait_time = rate_limit_obj.get_wait_time()
            raise RateLimitExceededError(wait_time, self.service.requests_per_minute)
        
        return True
    
    def _make_request(self, endpoint_name, payload):
        """Método base para hacer peticiones con auditoría completa"""
        if not self._check_rate_limit():
            # Podrías encolar esto en Celery para reintentar más tarde
            raise Exception(f"Rate limit excedido para {self.service.name}")
        
        endpoint = self.endpoints[endpoint_name]
        url = f"{self.base_url.rstrip('/')}{endpoint.path}"
        
        # Preparar payload con token
        payload_with_token = {'token': self.token, **payload}
        
        # Crear log de auditoría
        api_log = ApiCallLog.objects.create(
            service=self.service,
            endpoint=endpoint,
            request_data=payload_with_token,
            called_from=self._get_caller_info()
        )
        
        try:
            start_time = time.time()
            
            response = requests.post(
                url,
                json=payload_with_token,
                headers={'Content-Type': 'application/json'},
                timeout=30  # 30 segundos timeout
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Actualizar log con respuesta
            api_log.duration_ms = duration_ms
            api_log.response_code = response.status_code
            
            if response.status_code == 200:
                try:
                    
                    response_data = response.json()
                    api_log.response_data = response_data
                    
                    if response_data.get('success'):
                        api_log.status = 'SUCCESS'
                        api_log.save()
                        
                        # Actualizar rate limit
                        rate_limit = ApiRateLimit.objects.get(service=self.service)
                        rate_limit.increment_count()
                        
                        return response_data
                    else:
                        # RUC no existe u otro error de negocio
                        api_log.status = 'FAILED'
                        error_msg = response_data.get('message', 'Error desconocido en API')
                        api_log.error_message = error_msg
                        api_log.save()
                        
                        if 'no existe' in error_msg.lower() or 'not found' in error_msg.lower():
                            raise APINotFoundError(f"Recurso no encontrado: {error_msg}")
                        else:
                            raise APIError(f"Error de API: {error_msg}")
                
                except ValueError:  # JSON decode error
                    # APIMIGO devuelve HTML cuando token es inválido
                    api_log.status = 'FAILED'
                    if 'token_invalido' in response.text.lower() or 'unauthorized' in response.text.lower():
                        api_log.error_message = "Token inválido o no autorizado"
                        api_log.save()
                        raise AuthenticationError("Token APIMIGO inválido o no autorizado")
                    else:
                        api_log.error_message = f"Respuesta no JSON: {response.text[:200]}"
                        api_log.save()
                        raise APIBadResponseError("Respuesta inesperada de APIMIGO")
            
            elif response.status_code == 404:
                api_log.status = 'FAILED'
                if endpoint_name in ['ruc', 'dni']:
                    api_log.error_message = f"{'RUC' if endpoint_name == 'ruc' else 'DNI'} no encontrado"
                    api_log.save()
                    raise APINotFoundError(api_log.error_message)
                else:
                    api_log.error_message = "Endpoint no encontrado"
                    api_log.save()
                    raise APINotFoundError("Endpoint no encontrado")
            
            elif response.status_code == 401 or response.status_code == 403:
                api_log.status = 'FAILED'
                api_log.error_message = "Authentication failed"
                api_log.save()
                raise AuthenticationError(f"Authentication failed: {response.status_code}")
            
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                api_log.status = 'FAILED'
                api_log.error_message = error_msg
                api_log.save()
                raise APIError(error_msg)
                
        except requests.exceptions.Timeout:
            api_log.status = 'FAILED'
            api_log.error_message = "Timeout de conexión"
            api_log.save()
            raise Exception("Timeout al conectar con APIMIGO")
        
        except requests.exceptions.ConnectionError:
            api_log.status = 'FAILED'
            api_log.error_message = "Error de conexión"
            api_log.save()
            raise Exception("No se pudo conectar con APIMIGO")
        
        except Exception as e:
            api_log.status = 'FAILED'
            api_log.error_message = str(e)
            api_log.save()
            raise
    
    def _get_caller_info(self):
        """Obtiene información sobre quién llamó a la API"""
        import inspect
        stack = inspect.stack()
        # Busca el primer caller fuera de esta clase
        for frame_info in stack[2:]:
            if 'self' in frame_info.frame.f_locals:
                caller = frame_info.frame.f_locals['self']
                return f"{caller.__class__.__name__}.{frame_info.function}"
        return "unknown"
    
    # Métodos específicos de APIMIGO
    def consultar_cuenta(self):
        """Consulta información de la cuenta MIGO"""
        return self._make_request('account', {})
    
    def consultar_ruc(self, ruc):
        """Consulta datos de un RUC en SUNAT"""
        cache_key = f"migo_ruc_{ruc}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        result = self._make_request('ruc', {'ruc': ruc})
        
        # Cachear por 24 horas
        if result.get('success'):
            cache.set(cache_key, result, 86400)
        
        return result
    
    def consultar_dni(self, dni):
        """Consulta datos de un DNI"""
        cache_key = f"migo_dni_{dni}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        result = self._make_request('dni', {'dni': dni})
        
        # Cachear por 24 horas
        if result.get('success'):
            cache.set(cache_key, result, 86400)
        
        return result
    
    def consultar_tipo_cambio(self, fecha=None):
        """Consulta tipo de cambio SUNAT/SBS"""
        payload = {}
        if fecha:
            payload['fecha'] = fecha
        return self._make_request('tipo_cambio', payload)
    
    def consultar_representantes_legales(self, ruc):
        """Consulta representantes legales de una empresa"""
        return self._make_request('representantes', {'ruc': ruc})
    
    def validar_ruc_para_facturacion (self, ruc):
        """Verificación específica para facturación: RUC activo y habido"""
        
        try:
            resultado = self.consultar_ruc(ruc)
            
            if not resultado.get('success'):
                return {
                    'valido': False,
                    'ruc': ruc,
                    'razon_social': None,
                    'estado': None,
                    'condicion': None,
                    'direccion': None,
                    'errores': ['RUC no encontrado en SUNAT'],
                    'advertencias': []
                }
            
            estado = resultado.get('estado_del_contribuyente', '').upper()
            condicion = resultado.get('condicion_de_domicilio', '').upper()
            
            errores = []
            advertencias = []
            
            # Validaciones críticas
            if estado != 'ACTIVO':
                errores.append(f"Contribuyente no está ACTIVO (estado: {estado})")
            
            if condicion != 'HABIDO':
                errores.append(f"Contribuyente no es HABIDO (condición: {condicion})")
            
            # Validaciones de datos
            razon_social = resultado.get('nombre_o_razon_social')
            if not razon_social or len(razon_social.strip()) < 3:
                advertencias.append("Razón social muy corta o vacía")
            
            direccion = resultado.get('direccion')
            if not direccion or len(direccion.strip()) < 10:
                advertencias.append("Dirección muy corta o incompleta")
            
            return {
                'valido': len(errores) == 0,
                'ruc': ruc,
                'razon_social': razon_social,
                'estado': estado,
                'condicion': condicion,
                'direccion': direccion,
                'data_completa': resultado,
                'errores': errores,
                'advertencias': advertencias
            }
            
        except Exception as e:
            print(f"Error validando RUC {ruc}: {e}")
            return {
                'valido': False,
                'ruc': ruc,
                'razon_social': None,
                'errores': [f"Error de validación: {str(e)}"],
                'advertencias': []
            }

    def consultar_ruc_masivo(self, ruc_list, batch_id=None):
        """
        Consulta masiva de RUCs (máximo 100 por llamada)
        
        Args:
            ruc_list: Lista de RUCs a consultar
            batch_id: ID de ApiBatchRequest para tracking
        
        Returns:
            dict con resultados y estadísticas
        """
        if len(ruc_list) > 100:
            raise ValueError("Máximo 100 RUCs por consulta masiva")
        
        # Registrar batch request si se proporciona batch_id
        batch_request = None
        if batch_id:
            try:
                batch_request = ApiBatchRequest.objects.get(id=batch_id)
                batch_request.status = 'PROCESSING'
                batch_request.total_items = len(ruc_list)
                batch_request.save()
            except ApiBatchRequest.DoesNotExist:
                pass
        
        try:
            # Usar endpoint de colección
            endpoint = self._get_endpoint('ruc_collection', '/api/v1/ruc/collection')
            
            # Verificar rate limit
            if not self._check_rate_limit():
                raise Exception("Rate limit excedido para consultas masivas")
            
            # Preparar payload
            payload = {
                'token': self.token,
                'ruc': ruc_list
            }
            
            # Hacer la petición
            result = self._make_request_with_tracking(
                endpoint_name='ruc_collection',
                payload=payload,
                batch_request=batch_request
            )
            
            # Procesar resultados
            if isinstance(result, list):
                successful = [r for r in result if r.get('success')]
                failed = [r for r in result if not r.get('success')]
                
                # Actualizar batch request si existe
                if batch_request:
                    batch_request.results = result
                    batch_request.processed_items = len(result)
                    batch_request.successful_items = len(successful)
                    batch_request.failed_items = len(failed)
                    batch_request.status = 'COMPLETED' if len(failed) == 0 else 'PARTIAL'
                    batch_request.completed_at = timezone.now()
                    batch_request.save()
                
                return {
                    'success': True,
                    'total': len(result),
                    'successful': len(successful),
                    'failed': len(failed),
                    'results': result,
                    'summary': {
                        'activos': len([r for r in successful if r.get('estado_del_contribuyente') == 'ACTIVO']),
                        'habidos': len([r for r in successful if r.get('condicion_de_domicilio') == 'HABIDO']),
                    }
                }
            
            return {
                'success': False,
                'error': 'Formato de respuesta inesperado',
                'results': result
            }
            
        except Exception as e:
            if batch_request:
                batch_request.status = 'FAILED'
                batch_request.error_summary = {'error': str(e)}
                batch_request.completed_at = timezone.now()
                batch_request.save()
            raise
    
    def _make_request_with_tracking(self, endpoint_name, payload, batch_request=None):
        """
        Versión extendida de _make_request con tracking de batch
        """
        # Mismo código base de _make_request pero con actualizaciones de batch
        # ... (similar al _make_request original) ...
        
        # Dentro del try, después de obtener respuesta:
        if batch_request:
            batch_request.processed_items += 1
            if response.status_code == 200 and response_data.get('success'):
                batch_request.successful_items += 1
            else:
                batch_request.failed_items += 1
            batch_request.save()
        
        # Resto de la lógica de _make_request...
    
    def preparar_datos_facturacion_mensual(self, ruc_list):
        """
        Prepara datos de clientes para facturación mensual
        
        Args:
            ruc_list: Lista de RUCs a validar
        
        Returns:
            dict con clientes válidos y problemas encontrados
        """
        resultados = {
            'validos': [],
            'invalidos': [],
            'advertencias': []
        }
        
        # Dividir en lotes de 100 (máximo permitido)
        lotes = [ruc_list[i:i+100] for i in range(0, len(ruc_list), 100)]
        
        for lote in lotes:
            try:
                batch_result = self.consultar_ruc_masivo(lote)
                
                for item in batch_result.get('results', []):
                    ruc = item.get('ruc')
                    
                    if item.get('success'):
                        estado = item.get('estado_del_contribuyente', '').upper()
                        condicion = item.get('condicion_de_domicilio', '').upper()
                        
                        cliente_data = {
                            'ruc': ruc,
                            'razon_social': item.get('nombre_o_razon_social'),
                            'direccion': item.get('direccion'),
                            'estado': estado,
                            'condicion': condicion,
                            'habido': condicion == 'HABIDO',
                            'activo': estado == 'ACTIVO',
                            'data_completa': item,
                            'valido_para_facturar': estado == 'ACTIVO' and condicion == 'HABIDO'
                        }
                        
                        if cliente_data['valido_para_facturar']:
                            resultados['validos'].append(cliente_data)
                        else:
                            resultados['invalidos'].append({
                                'ruc': ruc,
                                'razon_social': cliente_data['razon_social'],
                                'estado': estado,
                                'condicion': condicion,
                                'error': 'No activo o no habido'
                            })
                    else:
                        resultados['advertencias'].append({
                            'ruc': ruc,
                            'error': 'No se pudo consultar en SUNAT'
                        })
                
                # Respetar rate limiting (60/minuto = 1 cada segundo)
                time.sleep(1)
                
            except Exception as e:
                resultados['advertencias'].extend([
                    {'ruc': ruc, 'error': f'Error en lote: {str(e)}'}
                    for ruc in lote
                ])
        
        return resultados    

    