from django.core.cache import cache
from datetime import datetime, timedelta
import logging
from typing import Any, Optional, Dict, List, Union

from django.conf import settings

logger = logging.getLogger(__name__)

class APICacheService:
    """
    Servicio centralizado de cache para APIs externas.
    
    Características:
    - Backend: LocMemCache (Desarrollo) | Memcached/Redis (Producción)
    - Soporte para RUCs válidos e inválidos
    - Manejo de tipo de cambio
    - Rate limiting tracking
    - Estadísticas y monitoreo
    - TTL automático por tipo de dato
    - Compatibilidad con múltiples servicios (Migo, NubeFact, etc.)
    
    NOTA: En desarrollo usamos LocMemCache (en memoria, sin dependencias externas)
          Para producción, cambiar a Memcached o Redis en settings.py
    """
    
    # Timeouts por defecto (en segundos)
    DEFAULT_TTL = 900  # 15 minutos
    RUC_VALID_TTL = 3600  # 1 hora para RUCs válidos
    RUC_INVALID_TTL = 86400  # 24 horas para RUCs inválidos
    RATE_LIMIT_TTL = 60  # 1 minuto para tracking de rate limit
    
    # Claves de cache específicas
    CACHE_KEY_INVALID_RUCS = 'invalid_rucs'
    CACHE_KEY_RUC_DATA = 'ruc_data_{ruc}'
    CACHE_KEY_API_RATE_LIMIT = 'api_rate_limit_{service}_{endpoint}'
    CACHE_KEY_BATCH_RESULTS = 'batch_results_{batch_id}'
    
    # Prefijos para diferentes tipos de datos
    TC_PREFIX = "tc_"  # Tipo de cambio
    RUC_PREFIX = "ruc_"  # RUCs válidos
    INVALID_RUCS_KEY = "migo_invalid_rucs"  # RUCs inválidos
    
    def __init__(self):
        """
        Inicializa el servicio de cache.
        Verifica la conexión a Memcached durante la inicialización.
        """
        logger.debug("APICacheService inicializado")
        self.cache = cache
        self.backend = self._get_cache_backend()
        self._verify_cache_connection()
    
    def _get_cache_backend(self) -> str:
        """Obtiene el nombre del backend de cache configurado"""
        
        cache_settings = settings.CACHES.get('default', {})
        backend = cache_settings.get('BACKEND', 'default')
        logger.debug(f"Cache backend: {backend}")
        # Extraer nombre simple del backend
        if 'memcache' in backend.lower():
            return 'memcached'
        elif 'locmem' in backend.lower():
            return 'local_memory'
        elif 'redis' in backend.lower():
            return 'redis'
        else:
            return 'unknown'
    
    def _verify_cache_connection(self) -> bool:
        """
        Verifica la conexión al servicio de cache (LocMemCache o Memcached).
        
        Esta verificación es crítica para asegurar que el cache está disponible.
        Si falla, se registra un warning pero el servicio continúa funcionando
        (fallback a comportamiento sin cache).
        
        Returns:
            bool: True si la conexión es exitosa, False en caso contrario
        """
        try:
            test_key = '__cache_connection_test__'
            test_value = {'timestamp': datetime.now().isoformat(), 'status': 'ok'}
            
            # Intentar escribir en cache
            # Nota: set() puede retornar None en algunos backends (LocMemCache, Memcached)
            # Lo importante es que no lance excepción
            try:
                self.cache.set(test_key, test_value, 10)
            except Exception as set_error:
                logger.warning(f"⚠️  Cache.set() falló: {set_error}")
                return False
            
            # Intentar leer del cache
            try:
                get_result = self.cache.get(test_key)
            except Exception as get_error:
                logger.warning(f"⚠️  Cache.get() falló: {get_error}")
                return False
            
            # Verificar que obtuvimos lo que guardamos
            if get_result != test_value:
                logger.warning(
                    f"⚠️  Verificación de cache falló. Esperado: {test_value}, "
                    f"Obtenido: {get_result}"
                )
                return False
            
            # Limpiar clave de prueba
            try:
                self.cache.delete(test_key)
            except Exception:
                pass  # Ignorar errores en limpieza
            
            logger.info(
                f"✅ Conexión a cache exitosa (backend: {self.backend})"
            )
            return True
                
        except Exception as e:
            logger.error(
                f"❌ Error verificando conexión al cache ({self.backend}): {str(e)}\n"
                f"   El cache puede no estar disponible. Verifica que LocMemCache/Memcached está corriendo."
            )
            return False
        
    # ============================================================================
    # MÉTODOS INTERNOS (HELPERS)
    # ============================================================================
    
    def _normalize_key(self, key: str) -> str:
        """
        Normaliza una clave para asegurar compatibilidad con backends de cache.
        Algunos backends (Memcached) tienen restricciones: sin espacios, max 250 caracteres.
        
        Args:
            key: Clave original
            
        Returns:
            str: Clave normalizada
        """
        # Reemplazar espacios con guiones bajos
        normalized = key.replace(' ', '_').replace(':', '_')
        
        # Limitar a 250 caracteres (límite conservador para compatibilidad con Memcached)
        if len(normalized) > 250:
            # Crear hash de la parte que se trunca
            import hashlib
            hash_suffix = hashlib.md5(normalized.encode()).hexdigest()[:8]
            normalized = normalized[:242] + '_' + hash_suffix
        
        return normalized
    
    # ============================================================================
    # MÉTODOS BÁSICOS DE CACHE (EXISTENTES - MEJORADOS)
    # ============================================================================
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave del cache
            default: Valor por defecto si no existe o hay error
            
        Returns:
            Valor almacenado o default
            
        Example:
            >>> cache_service.get('ruc_20100038146')
            {'ruc': '20100038146', 'nombre_o_razon_social': 'CONTINENTAL S.A.C.', ...}
        """
        try:
            # Normalizar clave
            normalized_key = self._normalize_key(key)
            
            # Obtener del cache
            value = cache.get(normalized_key)
            
            if value is None:
                logger.debug(f"Cache MISS: {key}")
                return default
            
            logger.debug(f"Cache HIT: {key}")
            return value
            
        except Exception as e:
            logger.error(f"Error obteniendo clave '{key}' del cache: {str(e)}")
            return default
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Establece un valor en el cache.
        
        Args:
            key: Clave del cache
            value: Valor a almacenar
            ttl: Time To Live en segundos (opcional, usa DEFAULT_TTL por defecto)
            
        Returns:
            True si se guardó exitosamente, False en caso de error
            
        Example:
            >>> cache_service.set('ruc_20100038146', ruc_data, ttl=3600)
            True
        """
        try:
            # Normalizar clave
            normalized_key = self._normalize_key(key)
            
            # Determinar timeout
            timeout = ttl if ttl is not None else self.DEFAULT_TTL
            
            # Establecer en cache
            # Nota: cache.set() puede retornar None en algunos backends
            # Lo importante es que no lance excepción
            self.cache.set(normalized_key, value, timeout)
            
            # Logging detallado en DEBUG
            if logger.isEnabledFor(logging.DEBUG):
                value_size = len(str(value)) if value else 0
                value_type = type(value).__name__
                logger.debug(
                    f"Cache SET: {key} (key_len: {len(normalized_key)}, "
                    f"ttl: {timeout}s, size: {value_size}B, type: {value_type})"
                )
            
            return True  # Siempre retorna True si no hay excepción
            
        except Exception as e:
            logger.error(f"Error estableciendo clave '{key}' en cache: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Elimina una clave del cache.
        
        Args:
            key: Clave a eliminar
            
        Returns:
            True si se eliminó exitosamente, False en caso de error
            
        Example:
            >>> cache_service.delete('ruc_20100038146')
            True
        """
        try:
            # Normalizar clave
            normalized_key = self._normalize_key(key)
            
            # Eliminar del cache
            result = cache.delete(normalized_key)
            
            logger.debug(f"Cache DELETE: {key}")
            return result if result is not None else True
            
        except Exception as e:
            logger.error(f"Error eliminando clave '{key}' del cache: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """
        Limpia todo el cache.
        
        ⚠️  CUIDADO: Esta operación limpia TODO el cache de Memcached,
        no solo las claves de este servicio.
        
        Returns:
            True si se limpió exitosamente, False en caso de error
        """
        try:
            result = cache.clear()
            logger.warning("⚠️  Cache limpiado completamente (todas las claves)")
            return result if result is not None else True
            
        except Exception as e:
            logger.error(f"Error limpiando cache: {str(e)}")
            return False
    
    # ============================================================================
    # MÉTODOS PARA MANEJO MULTI-SERVICIO (NUEVOS - PARA FUTURO CRECIMIENTO)
    # ============================================================================
    
    def get_service_cache_key(self, service_name: str, key: str) -> str:
        """
        Genera una clave de cache namespaceada por servicio.
        
        Útil para cuando se agreguen más servicios de API (NubeFact, SUNAT, etc.)
        Evita colisiones entre servicios.
        
        Args:
            service_name: Nombre del servicio (ej: 'migo', 'nubefact', 'sunat')
            key: Clave específica del servicio
            
        Returns:
            str: Clave namespaceada (ej: 'migo:ruc_20100038146')
            
        Example:
            >>> cache_service.get_service_cache_key('migo', 'ruc_20100038146')
            'migo:ruc_20100038146'
        """
        return f"{service_name.lower()}:{key}"
    
    def clear_service_cache(self, service_name: str) -> Dict[str, int]:
        """
        Limpia todas las claves del cache de un servicio específico.
        
        Nota: Memcached no tiene soporte nativo para eliminar por patrón,
        así que este método solo limpia claves conocidas.
        
        Args:
            service_name: Nombre del servicio a limpiar
            
        Returns:
            Dict con conteo de claves eliminadas por tipo
        """
        cleaned_count = {
            "ruc_valid": 0,
            "ruc_invalid": 0,
            "tipo_cambio": 0,
            "total": 0
        }
        
        try:
            service_prefix = self.get_service_cache_key(service_name, "")
            
            # Nota: Esta es una limitación conocida de Memcached.
            # Para mejor manejo de limpiezas parciales, considerar:
            # 1. Redis con SCAN y patrón de claves
            # 2. Rastrear claves en DB separada
            # 3. Usar namespaces/buckets explícitos
            
            logger.info(
                f"Limpieza parcial de cache para servicio '{service_name}' "
                f"es limitada con Memcached. Considerar usar Redis para mejor control."
            )
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error limpiando cache del servicio {service_name}: {str(e)}")
            return cleaned_count
    
    # ============================================================================
    # MÉTODOS PARA TIPO DE CAMBIO (EXISTENTES - MANTENIDOS CON MEJORAS)
    # ============================================================================
    
    def get_tipo_cambio(self, fecha: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene tipo de cambio desde el cache.
        MÉTODO EXISTENTE - Mejorado con logging y manejo de errores.
        
        Args:
            fecha: Fecha en formato ISO (YYYY-MM-DD). Si es None, usa fecha actual.
            
        Returns:
            Datos del tipo de cambio o None si no está en cache
        """
        if not fecha:
            fecha = datetime.now().date().isoformat()
        
        cache_key = f"{self.TC_PREFIX}{fecha}"
        
        try:
            data = self.get(cache_key)
            
            if data and isinstance(data, dict):
                # Verificar si ha expirado
                expires_at = data.get('expires_at')
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() > expires_dt:
                            logger.debug(f"Tipo cambio para {fecha} ha expirado")
                            self.delete(cache_key)
                            return None
                    except (ValueError, TypeError):
                        pass
                
                logger.debug(f"Cache HIT para tipo cambio {fecha}")
                return data
            else:
                logger.debug(f"Cache MISS para tipo cambio {fecha}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo tipo cambio para {fecha}: {str(e)}")
            return None
    
    def set_tipo_cambio(self, fecha: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """
        Guarda tipo de cambio en el cache.
        MÉTODO EXISTENTE - Mejorado con metadatos y logging.
        
        Args:
            fecha: Fecha en formato ISO (YYYY-MM-DD)
            data: Datos del tipo de cambio
            ttl: TTL específico para este dato (opcional)
            
        Returns:
            True si se guardó exitosamente, False en caso de error
        """
        cache_key = f"{self.TC_PREFIX}{fecha}"
        timeout = ttl if ttl is not None else self.DEFAULT_TTL
        
        try:
            # Agregar metadatos al dato
            enhanced_data = {
                **data,
                "cached_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(seconds=timeout)).isoformat(),
                "ttl_seconds": timeout
            }
            
            result = self.set(cache_key, enhanced_data, timeout)
            
            if result:
                logger.info(f"Tipo cambio para {fecha} guardado en cache (ttl: {timeout}s)")
            else:
                logger.warning(f"No se pudo guardar tipo cambio para {fecha} en cache")
                
            return result
            
        except Exception as e:
            logger.error(f"Error guardando tipo cambio para {fecha}: {str(e)}")
            return False
    
    # ============================================================================
    # MÉTODOS PARA RUCS VÁLIDOS (NUEVOS - COMPATIBLES CON MIGO_SERVICE)
    # ============================================================================
    
    def get_ruc(self, ruc: str) -> Optional[Dict]:
        """
        Obtiene datos de un RUC válido desde el cache.
        NUEVO MÉTODO: Compatible con migo_service.py mejorado.
        
        Args:
            ruc: Número de RUC (11 dígitos)
            
        Returns:
            Datos del RUC o None si no está en cache
        """
        if not ruc or len(str(ruc)) != 11:
            logger.warning(f"Formato de RUC inválido para cache: {ruc}")
            return None
        
        cache_key = f"{self.RUC_PREFIX}{ruc}"
        
        try:
            data = self.get(cache_key)
            
            if data and isinstance(data, dict):
                # Verificar si ha expirado
                expires_at = data.get('_expires_at') or data.get('expires_at')
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() > expires_dt:
                            logger.debug(f"RUC {ruc} ha expirado en cache")
                            self.delete(cache_key)
                            return None
                    except (ValueError, TypeError):
                        pass
                
                logger.debug(f"Cache HIT para RUC {ruc}")
                return data
            else:
                logger.debug(f"Cache MISS para RUC {ruc}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo RUC {ruc} del cache: {str(e)}")
            return None
    
    def set_ruc(self, ruc: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """
        Guarda datos de un RUC válido en el cache.
        NUEVO MÉTODO: Compatible con migo_service.py mejorado.
        
        Args:
            ruc: Número de RUC (11 dígitos)
            data: Datos del RUC
            ttl: TTL específico para este RUC (opcional, usa RUC_VALID_TTL por defecto)
            
        Returns:
            True si se guardó exitosamente, False en caso de error
        """
        if not ruc or len(str(ruc)) != 11:
            logger.warning(f"Formato de RUC inválido para cache: {ruc}")
            return False
        
        cache_key = f"{self.RUC_PREFIX}{ruc}"
        timeout = ttl if ttl is not None else self.RUC_VALID_TTL
        
        try:
            # Agregar metadatos al dato
            enhanced_data = {
                **data,
                "_cached_at": datetime.now().isoformat(),
                "_expires_at": (datetime.now() + timedelta(seconds=timeout)).isoformat(),
                "_ttl": timeout
            }
            
            result = self.set(cache_key, enhanced_data, timeout)
            
            if result:
                logger.info(f"RUC {ruc} guardado en cache válidos (ttl: {timeout}s)")
            else:
                logger.warning(f"No se pudo guardar RUC {ruc} en cache válidos")
                
            return result
            
        except Exception as e:
            logger.error(f"Error guardando RUC {ruc} en cache: {str(e)}")
            return False
    
    def delete_ruc(self, ruc: str) -> bool:
        """
        Elimina un RUC del cache de válidos.
        NUEVO MÉTODO: Para mantenimiento del cache.
        
        Args:
            ruc: Número de RUC a eliminar
            
        Returns:
            True si se eliminó exitosamente, False en caso de error
        """
        if not ruc or len(str(ruc)) != 11:
            logger.warning(f"Formato de RUC inválido para eliminación: {ruc}")
            return False
        
        cache_key = f"{self.RUC_PREFIX}{ruc}"
        return self.delete(cache_key)
    
    # ============================================================================
    # MÉTODOS PARA RUCS INVÁLIDOS (NUEVOS - COORDINADOS CON MIGO_SERVICE)
    # ============================================================================
    
    def add_invalid_ruc(self, ruc: str, reason: str = "INVALIDO", 
                       ttl_hours: Optional[int] = None) -> bool:
        """
        Agrega un RUC al cache de inválidos.
        NUEVO MÉTODO: Esencial para el manejo de RUCs inválidos.
        
        Args:
            ruc: Número de RUC inválido
            reason: Razón por la cual es inválido
            ttl_hours: TTL en horas (opcional, usa RUC_INVALID_TTL por defecto)
            
        Returns:
            True si se agregó exitosamente, False en caso de error
        """
        if not ruc:
            logger.warning("Intento de agregar RUC vacío al cache de inválidos")
            return False
        
        # Calcular TTL
        if ttl_hours is not None:
            ttl_seconds = ttl_hours * 3600
        else:
            ttl_seconds = self.RUC_INVALID_TTL
        
        try:
            # Obtener cache actual de inválidos
            invalid_rucs = self.get(self.INVALID_RUCS_KEY, {})
            
            # Verificar si ya existe (para no sobrescribir timestamp original)
            if ruc not in invalid_rucs:
                added_at = datetime.now().isoformat()
            else:
                added_at = invalid_rucs[ruc].get("added_at", datetime.now().isoformat())
            
            # Actualizar/agregar RUC inválido
            invalid_rucs[ruc] = {
                "reason": reason,
                "added_at": added_at,
                "ttl_hours": ttl_hours if ttl_hours is not None else 24,
                "expires_at": (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            }
            
            # Guardar en cache
            result = self.set(self.INVALID_RUCS_KEY, invalid_rucs, ttl_seconds)
            
            if result:
                logger.info(f"RUC {ruc} agregado al cache de inválidos: {reason} (ttl: {ttl_seconds}s)")
            else:
                logger.warning(f"No se pudo agregar RUC {ruc} al cache de inválidos")
                
            return result
            
        except Exception as e:
            logger.error(f"Error agregando RUC {ruc} al cache de inválidos: {str(e)}")
            return False
    
    def is_ruc_invalid(self, ruc: str) -> bool:
        """
        Verifica si un RUC está marcado como inválido en el cache.
        NUEVO MÉTODO: Usado por migo_service para evitar consultas innecesarias.
        
        Args:
            ruc: Número de RUC a verificar
            
        Returns:
            True si el RUC está marcado como inválido, False en caso contrario
        """
        if not ruc:
            return False
        
        try:
            invalid_rucs = self.get(self.INVALID_RUCS_KEY, {})
            
            if ruc in invalid_rucs:
                # Verificar si ha expirado
                ruc_info = invalid_rucs[ruc]
                expires_at = ruc_info.get("expires_at")
                
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() > expires_dt:
                            # Eliminar RUC expirado
                            self.remove_invalid_ruc(ruc)
                            return False
                    except (ValueError, TypeError):
                        # Si no se puede parsear la fecha, asumir válido
                        pass
                
                logger.debug(f"RUC {ruc} encontrado en cache de inválidos")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error verificando RUC {ruc} en cache de inválidos: {str(e)}")
            return False
    
    def get_invalid_ruc_info(self, ruc: str) -> Optional[Dict]:
        """
        Obtiene información detallada de un RUC inválido.
        NUEVO MÉTODO: Para debugging y monitoreo.
        
        Args:
            ruc: Número de RUC
            
        Returns:
            Información del RUC inválido o None si no está en cache
        """
        if not ruc:
            return None
        
        try:
            invalid_rucs = self.get(self.INVALID_RUCS_KEY, {})
            ruc_info = invalid_rucs.get(ruc)
            
            if ruc_info:
                # Verificar si ha expirado
                expires_at = ruc_info.get("expires_at")
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() > expires_dt:
                            self.remove_invalid_ruc(ruc)
                            return None
                    except (ValueError, TypeError):
                        pass
                
                return ruc_info
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo información de RUC {ruc}: {str(e)}")
            return None
    
    def remove_invalid_ruc(self, ruc: str) -> bool:
        """
        Remueve un RUC del cache de inválidos.
        NUEVO MÉTODO: Para mantenimiento y correcciones.
        
        Args:
            ruc: Número de RUC a remover
            
        Returns:
            True si se removió exitosamente, False en caso de error
        """
        if not ruc:
            return False
        
        try:
            invalid_rucs = self.get(self.INVALID_RUCS_KEY, {})
            
            if ruc in invalid_rucs:
                del invalid_rucs[ruc]
                
                # Si quedan RUCs, actualizar cache con nuevo TTL
                if invalid_rucs:
                    # Calcular nuevo TTL basado en el RUC más antiguo
                    oldest_entry = min(
                        invalid_rucs.values(), 
                        key=lambda x: datetime.fromisoformat(x.get("added_at", datetime.now().isoformat()))
                    )
                    
                    expires_at = oldest_entry.get("expires_at")
                    if expires_at:
                        try:
                            expires_dt = datetime.fromisoformat(expires_at)
                            remaining_ttl = (expires_dt - datetime.now()).total_seconds()
                            ttl = max(300, int(remaining_ttl))  # Mínimo 5 minutos
                        except (ValueError, TypeError):
                            ttl = 3600  # 1 hora si no se puede calcular
                    else:
                        ttl = 3600  # 1 hora por defecto
                    
                    result = self.set(self.INVALID_RUCS_KEY, invalid_rucs, ttl)
                else:
                    # Si no quedan RUCs, eliminar la clave
                    result = self.delete(self.INVALID_RUCS_KEY)
                
                if result:
                    logger.info(f"RUC {ruc} removido del cache de inválidos")
                else:
                    logger.warning(f"No se pudo remover RUC {ruc} del cache de inválidos")
                    
                return result
            else:
                logger.debug(f"RUC {ruc} no encontrado en cache de inválidos")
                return True  # Si no existe, se considera éxito
                
        except Exception as e:
            logger.error(f"Error removiendo RUC {ruc} del cache de inválidos: {str(e)}")
            return False
    
    def get_all_invalid_rucs(self) -> Dict[str, Dict]:
        """
        Obtiene todos los RUCs marcados como inválidos.
        NUEVO MÉTODO: Para reportes y monitoreo.
        
        Returns:
            Dict con todos los RUCs inválidos y su información
        """
        try:
            invalid_rucs = self.get(self.INVALID_RUCS_KEY, {})
            
            # Filtrar RUCs expirados
            valid_invalid_rucs = {}
            for ruc, info in invalid_rucs.items():
                expires_at = info.get("expires_at")
                if expires_at:
                    try:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() <= expires_dt:
                            valid_invalid_rucs[ruc] = info
                        else:
                            # RUC expirado, será removido en la próxima verificación
                            pass
                    except (ValueError, TypeError):
                        valid_invalid_rucs[ruc] = info
                else:
                    valid_invalid_rucs[ruc] = info
            
            # Si se filtraron algunos, actualizar cache
            if len(valid_invalid_rucs) != len(invalid_rucs):
                self.set(self.INVALID_RUCS_KEY, valid_invalid_rucs, self.RUC_INVALID_TTL)
            
            return valid_invalid_rucs
            
        except Exception as e:
            logger.error(f"Error obteniendo todos los RUCs inválidos: {str(e)}")
            return {}
    
    def clear_invalid_rucs(self) -> bool:
        """
        Limpia todos los RUCs inválidos del cache.
        NUEVO MÉTODO: Para mantenimiento.
        
        Returns:
            True si se limpió exitosamente, False en caso de error
        """
        try:
            result = self.delete(self.INVALID_RUCS_KEY)
            
            if result:
                logger.info("Cache de RUCs inválidos limpiado completamente")
            else:
                logger.warning("No se pudo limpiar el cache de RUCs inválidos")
                
            return result
            
        except Exception as e:
            logger.error(f"Error limpiando cache de RUCs inválidos: {str(e)}")
            return False
    
    # ============================================================================
    # MÉTODOS UTILITARIOS Y DE MONITOREO (NUEVOS)
    # ============================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas completas del servicio de cache.
        
        Returns:
            Dict con información detallada del estado del cache
            
        Example:
            >>> stats = cache_service.get_cache_stats()
            >>> print(f"RUCs inválidos: {stats['invalid_rucs_count']}")
            RUCs inválidos: 5
        """
        try:
            # Obtener información del cache
            invalid_rucs = self.get_all_invalid_rucs()
            connection_ok = self._verify_cache_connection()
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "status": "healthy" if connection_ok else "warning",
                "backend": self.backend,
                
                # Estadísticas de RUCs
                "invalid_rucs": {
                    "total_count": len(invalid_rucs),
                    "sample": list(invalid_rucs.keys())[:10] if invalid_rucs else [],
                    "breakdown_by_reason": self._breakdown_invalid_rucs_by_reason(invalid_rucs)
                },
                
                # Configuración de timeouts
                "timeouts": {
                    "default": f"{self.DEFAULT_TTL}s ({self.DEFAULT_TTL//60}min)",
                    "ruc_valid": f"{self.RUC_VALID_TTL}s ({self.RUC_VALID_TTL//60}min)",
                    "ruc_invalid": f"{self.RUC_INVALID_TTL}s ({self.RUC_INVALID_TTL//3600}h)",
                    "rate_limit": f"{self.RATE_LIMIT_TTL}s"
                },
                
                # Prefijos de claves
                "key_prefixes": {
                    "tipo_cambio": self.TC_PREFIX,
                    "ruc_valid": self.RUC_PREFIX,
                    "invalid_rucs": self.INVALID_RUCS_KEY
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del cache: {str(e)}")
            return {
                "error": str(e), 
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }
    
    def _breakdown_invalid_rucs_by_reason(self, invalid_rucs: Dict) -> Dict[str, int]:
        """
        Agrupa RUCs inválidos por razón.
        
        Args:
            invalid_rucs: Dict de RUCs inválidos
            
        Returns:
            Dict con conteo de RUCs por razón
        """
        breakdown = {}
        for ruc, info in invalid_rucs.items():
            reason = info.get("reason", "DESCONOCIDA")
            breakdown[reason] = breakdown.get(reason, 0) + 1
        return breakdown
    
    def cleanup_expired(self) -> Dict[str, int]:
        """
        Limpia elementos expirados del cache.
        
        En Memcached, la expiración es automática, pero este método
        limpia referencias en metadata que puedan estar expiradas.
        
        Returns:
            Dict con conteo de elementos limpiados por tipo
        """
        cleaned = {
            "invalid_rucs": 0,
            "valid_rucs": 0,
            "tipo_cambio": 0
        }
        
        try:
            # Refrescar RUCs inválidos (elimina los expirados automáticamente)
            current_invalid = self.get_all_invalid_rucs()
            cleaned["invalid_rucs"] = 0  # El cleanup ya ocurrió en get_all_invalid_rucs
            
            logger.info(f"Cache cleanup completado: {cleaned}")
            return cleaned
            
        except Exception as e:
            logger.error(f"Error en cleanup de cache: {str(e)}")
            return cleaned
    
    def get_health(self) -> Dict[str, Any]:
        """
        Verifica la salud del servicio de cache.
        
        Realiza pruebas para determinar si el cache está funcionando correctamente.
        
        Returns:
            Dict con estado de salud
            
        Example:
            >>> health = cache_service.get_health()
            >>> if health['status'] == 'healthy':
            ...     print("Cache está OK")
        """
        health = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy",
            "checks": {}
        }
        
        try:
            # Check 1: Conexión al backend
            connection_ok = self._verify_cache_connection()
            health["checks"]["connection"] = "✅ OK" if connection_ok else "❌ FAILED"
            if not connection_ok:
                health["status"] = "unhealthy"
            
            # Check 2: Operaciones básicas
            try:
                test_key = "__health_check_" + str(datetime.now().timestamp()).replace(".", "_") + "__"
                test_value = {"health": "check", "timestamp": datetime.now().isoformat()}
                
                if self.set(test_key, test_value, 10):
                    if self.get(test_key) == test_value:
                        health["checks"]["basic_operations"] = "✅ OK"
                        self.delete(test_key)
                    else:
                        health["checks"]["basic_operations"] = "❌ Value mismatch"
                        health["status"] = "unhealthy"
                else:
                    health["checks"]["basic_operations"] = "❌ SET failed"
                    health["status"] = "unhealthy"
                    
            except Exception as e:
                health["checks"]["basic_operations"] = f"❌ {str(e)}"
                health["status"] = "unhealthy"
            
            # Check 3: Información de RUCs inválidos
            try:
                invalid_count = len(self.get_all_invalid_rucs())
                health["checks"]["invalid_rucs"] = f"✅ {invalid_count} RUCs"
            except Exception as e:
                health["checks"]["invalid_rucs"] = f"⚠️  {str(e)}"
            
            # Summary
            all_ok = all(
                "✅" in str(v) for v in health["checks"].values()
            )
            health["status"] = "healthy" if all_ok else "warning" if health["status"] != "unhealthy" else "unhealthy"
            
            return health
            
        except Exception as e:
            logger.error(f"Error verificando salud del cache: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "unhealthy",
                "error": str(e)
            }


# ============================================================================
# Documentación de configuración y uso
# ============================================================================
"""
CONFIGURACIÓN DE CACHE
=====================

🔧 DESARROLLO (LocMemCache) - ACTUAL
====================================

No requiere instalación de dependencias externas. Configurado en settings.py:

   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
           'LOCATION': 'unique-snowflake',
           'TIMEOUT': 3600,
       }
   }

Ventajas:
- Sin dependencias externas (memcached daemon)
- Rápido para desarrollo local
- Mismo código que producción
- Funciona en Windows/WSL sin problemas de red

Desventajas:
- No persiste entre reinicios
- No compartido entre procesos
- NO usar en producción

🚀 PRODUCCIÓN (Memcached o Redis) - FUTURO
===========================================

Para pasar a producción, cambiar settings.py a:

OPCIÓN 1 - Memcached (Recomendado):
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
           'LOCATION': '127.0.0.1:11211',  # O IP del servidor Memcached
           'TIMEOUT': 3600,
           'OPTIONS': {
               'no_delay': True,
               'ignore_exc': True,
               'max_pool_size': 4,
               'use_pooling': True,
           }
       }
   }

OPCIÓN 2 - Redis:
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.redis.RedisCache',
           'LOCATION': 'redis://127.0.0.1:6379/1',
       }
   }

USO EN SERVICIOS API
====================

# Inicializar
from api_service.services.cache_service import APICacheService
cache_service = APICacheService()

# Almacenar RUC válido
cache_service.set_ruc('20100038146', {
    'nombre_o_razon_social': 'CONTINENTAL S.A.C.',
    'estado_del_contribuyente': 'ACTIVO',
    ...
}, ttl=3600)

# Obtener RUC
ruc_data = cache_service.get_ruc('20100038146')

# Marcar RUC como inválido
cache_service.add_invalid_ruc('20999999999', reason='NO_EXISTE_SUNAT')

# Verificar si RUC es inválido
if cache_service.is_ruc_invalid('20999999999'):
    print("RUC está en cache de inválidos")

# Obtener estadísticas
stats = cache_service.get_cache_stats()
print(f"RUCs inválidos: {stats['invalid_rucs']['total_count']}")

# Verificar salud del cache
health = cache_service.get_health()
print(f"Cache status: {health['status']}")

LIMITACIONES POR BACKEND
=========================

📊 LocMemCache (Desarrollo Actual):
   - No persiste entre reinicios
   - No compartido entre procesos (Workers)
   - Limitado por RAM disponible
   - Perfecto para desarrollo local

💾 Memcached (Producción):
   - No soporta patrones de claves (SCAN/PATTERN)
   - Tamaño máximo de valor: ~1MB
   - Tamaño máximo de clave: 250 caracteres (respetamos este límite)
   - No persiste datos entre reinicios
   - TTL máximo: ~30 días

🔴 Redis (Producción Avanzada):
   - Soporte completo para patrones
   - Persistencia opcional (RDB/AOF)
   - Mejor rendimiento en operaciones complejas
   - Requiere más configuración

MONITOREO Y MANTENIMIENTO
=========================

# Ver datos del cache (en Python)
>>> from api_service.services.cache_service import APICacheService
>>> cache = APICacheService()
>>> stats = cache.get_cache_stats()
>>> print(f"RUCs inválidos: {stats['invalid_rucs']['total_count']}")

# Verificar salud
>>> health = cache.get_health()
>>> print(health['status'])

# Limpiar cache (afecta TODO el cache)
>>> cache.clear()

# Limpiar solo RUCs inválidos
>>> cache.clear_invalid_rucs()
"""