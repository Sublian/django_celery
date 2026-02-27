# api_service/services/base/rate_limit.py

import logging
import time
from typing import Tuple, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from asgiref.sync import sync_to_async

from api_service.models import ApiService, ApiEndpoint, ApiRateLimit

logger = logging.getLogger(__name__)


class RateLimitManager:
    """
    Manejador de rate limiting que usa las tablas correctas.
    Respeta:
    - ApiService.requests_per_minute (límite global)
    - ApiEndpoint.custom_rate_limit (límite específico)
    - ApiRateLimit (registro de uso)
    """
    
    def __init__(self, service: Optional[ApiService] = None):
        self.service = service
        self.service_limit = getattr(service, 'requests_per_minute', 200) if service else 200
        self.cached_endpoint_limits = {}
    
    def set_service(self, service: ApiService):
        """Establece el servicio y su límite global."""
        self.service = service
        self.service_limit = getattr(service, 'requests_per_minute', 200)
    
    def _get_endpoint_limit(self, endpoint: ApiEndpoint) -> int:
        """
        Obtiene el límite para un endpoint.
        Prioridad: custom_rate_limit > service_limit
        """
        if endpoint.id in self.cached_endpoint_limits:
            return self.cached_endpoint_limits[endpoint.id]
        
        # Usar custom_rate_limit si existe, sino el límite del servicio
        limit = endpoint.custom_rate_limit if endpoint.custom_rate_limit else self.service_limit
        self.cached_endpoint_limits[endpoint.id] = limit
        return limit
    
    def _get_rate_limit_record(self, endpoint: ApiEndpoint) -> ApiRateLimit:
        """Obtiene o crea el registro de rate limit para un endpoint."""
        now = timezone.now()
        minute_start = now.replace(second=0, microsecond=0)
        
        rate_limit, created = ApiRateLimit.objects.get_or_create(
            service=self.service,
            endpoint=endpoint,
            defaults={
                'current_count': 0,
                'minute_window_start': minute_start,
                'last_request_at': now
            }
        )
        
        # Si el registro existe pero la ventana ha cambiado, resetear
        if not created and rate_limit.minute_window_start < minute_start:
            rate_limit.current_count = 0
            rate_limit.minute_window_start = minute_start
            rate_limit.save(update_fields=['current_count', 'minute_window_start'])
        
        return rate_limit
    
    # ===== VERSIÓN SÍNCRONA =====
    
    def check_rate_limit_sync(self, endpoint_name: str) -> Tuple[bool, float, int]:
        """
        Verifica rate limit.
        
        Returns:
            Tuple[bool, float, int]: (puede_proceder, tiempo_espera_segundos, límite_actual)
        """
        if not self.service:
            return True, 0.0, self.service_limit
        
        try:
            endpoint = ApiEndpoint.objects.filter(
                service=self.service, name=endpoint_name
            ).first()
            
            if not endpoint:
                return True, 0.0, self.service_limit
            
            # Obtener límite para este endpoint
            limit = self._get_endpoint_limit(endpoint)
            
            # Obtener registro de rate limit
            rate_limit = self._get_rate_limit_record(endpoint)
            
            # Verificar si podemos hacer la petición
            if rate_limit.current_count < limit:
                return True, 0.0, limit
            else:
                # Calcular tiempo de espera hasta el próximo minuto
                next_minute = rate_limit.minute_window_start + timedelta(minutes=1)
                wait_seconds = (next_minute - timezone.now()).total_seconds()
                wait_seconds = max(0, wait_seconds)  # No negativo
                
                logger.warning(
                    f"⚠️ Rate limit alcanzado para {endpoint_name}: "
                    f"{rate_limit.current_count}/{limit}. "
                    f"Esperar {wait_seconds:.1f}s"
                )
                return False, wait_seconds, limit
                
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, 0.0, self.service_limit
    
    def update_rate_limit_sync(self, endpoint_name: str) -> None:
        """Actualiza el contador después de una petición exitosa."""
        if not self.service:
            return
        
        try:
            endpoint = ApiEndpoint.objects.filter(
                service=self.service, name=endpoint_name
            ).first()
            
            if endpoint:
                rate_limit = self._get_rate_limit_record(endpoint)
                rate_limit.current_count += 1
                rate_limit.total_requests += 1
                rate_limit.last_request_at = timezone.now()
                rate_limit.save(update_fields=['current_count', 'total_requests', 'last_request_at'])
                
                limit = self._get_endpoint_limit(endpoint)
                if rate_limit.current_count >= limit * 0.9:  # 90% del límite
                    logger.info(f"⚠️ Rate limit al {rate_limit.current_count}/{limit} para {endpoint_name}")
                
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")
    
    # ===== VERSIÓN ASÍNCRONA =====
    
    async def check_rate_limit_async(self, endpoint_name: str) -> Tuple[bool, float, int]:
        """Versión asíncrona de check_rate_limit_sync."""
        return await sync_to_async(self.check_rate_limit_sync)(endpoint_name)
    
    async def update_rate_limit_async(self, endpoint_name: str) -> None:
        """Versión asíncrona de update_rate_limit_sync."""
        await sync_to_async(self.update_rate_limit_sync)(endpoint_name)