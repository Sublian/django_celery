from django.core.cache import cache
from datetime import datetime, timedelta
import logging
from typing import Any, Optional, Dict, List, Union

logger = logging.getLogger(__name__)

class APICacheService:
    """
    Servicio de cache para API con soporte para RUCs inválidos.
    
    Mantiene todas las funciones existentes y agrega manejo específico
    para RUCs inválidos basado en las mejoras de migo_service.py.
    """
    
    # Timeouts por defecto (manteniendo valores existentes)
    DEFAULT_TTL = 900  # 15 minutos (900 segundos)
    RUC_VALID_TTL = 3600  # 1 hora para RUCs válidos
    RUC_INVALID_TTL = 86400  # 24 horas para RUCs inválidos
    
    # Claves de cache específicas
    TC_PREFIX = "tc_"  # Tipo de cambio (existente)
    RUC_PREFIX = "ruc_"  # RUCs válidos
    INVALID_RUCS_KEY = "migo_invalid_rucs"  # RUCs inválidos (coordinado con migo_service)
    
    def __init__(self):
        """Inicializa el servicio de cache."""
        logger.debug("APICacheService inicializado")
    
    # ============================================================================
    # MÉTODOS BÁSICOS DE CACHE (EXISTENTES - MANTENIDOS SIN CAMBIOS)
    # ============================================================================
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor del cache.
        
        Args:
            key: Clave del cache
            default: Valor por defecto si no existe
            
        Returns:
            Valor almacenado o default
        """
        try:
            value = cache.get(key)
            if value is None:
                return default
            return value
        except Exception as e:
            logger.error(f"Error obteniendo clave {key} del cache: {str(e)}")
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
        """
        try:
            timeout = ttl if ttl is not None else self.DEFAULT_TTL
            result = cache.set(key, value, timeout)
            
            # Debug logging
            if logger.isEnabledFor(logging.DEBUG):
                value_size = len(str(value)) if value else 0
                logger.debug(f"Cache SET: {key} (ttl: {timeout}s, size: {value_size})")
                
            return result
        except Exception as e:
            logger.error(f"Error estableciendo clave {key} en cache: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Elimina una clave del cache.
        
        Args:
            key: Clave a eliminar
            
        Returns:
            True si se eliminó exitosamente, False en caso de error
        """
        try:
            result = cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return result
        except Exception as e:
            logger.error(f"Error eliminando clave {key} del cache: {str(e)}")
            return False
    
    def clear(self) -> bool:
        """
        Limpia todo el cache.
        
        Returns:
            True si se limpió exitosamente, False en caso de error
        """
        try:
            result = cache.clear()
            logger.info("Cache limpiado completamente")
            return result
        except Exception as e:
            logger.error(f"Error limpiando cache: {str(e)}")
            return False
    
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
        Obtiene estadísticas del cache.
        NUEVO MÉTODO: Para monitoreo y debugging.
        
        Returns:
            Dict con estadísticas del cache
        """
        try:
            invalid_rucs = self.get_all_invalid_rucs()
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "invalid_rucs_count": len(invalid_rucs),
                "invalid_rucs_sample": list(invalid_rucs.keys())[:10] if invalid_rucs else [],
                "timeouts": {
                    "default": self.DEFAULT_TTL,
                    "ruc_valid": self.RUC_VALID_TTL,
                    "ruc_invalid": self.RUC_INVALID_TTL
                },
                "cache_keys": {
                    "tipo_cambio_prefix": self.TC_PREFIX,
                    "ruc_prefix": self.RUC_PREFIX,
                    "invalid_rucs_key": self.INVALID_RUCS_KEY
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del cache: {str(e)}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def cleanup_expired(self) -> Dict[str, int]:
        """
        Limpia elementos expirados del cache.
        NUEVO MÉTODO: Para mantenimiento periódico.
        
        Returns:
            Dict con conteo de elementos limpiados por tipo
        """
        cleaned = {
            "invalid_rucs": 0,
            "valid_rucs": 0,
            "tipo_cambio": 0
        }
        
        try:
            # Limpiar RUCs inválidos expirados (ya se hace en get_all_invalid_rucs)
            current_invalid = self.get_all_invalid_rucs()
            cleaned["invalid_rucs"] = 0  # El cleanup ya ocurrió en get_all_invalid_rucs
            
            # Nota: Para RUCs válidos y tipo de cambio, el cleanup ocurre
            # al intentar acceder a ellos (en los métodos get)
            
            logger.info(f"Cleanup completado: {cleaned}")
            return cleaned
            
        except Exception as e:
            logger.error(f"Error en cleanup de cache: {str(e)}")
            return cleaned