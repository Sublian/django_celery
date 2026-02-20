# api_service/services/base/rate_limit.py
"""
Módulo compartido para rate limiting.
Puede ser usado por NubeFact, Migo y cualquier otro servicio.
"""

import logging
from typing import Tuple, Optional
from asgiref.sync import sync_to_async

from api_service.models import ApiService, ApiEndpoint, ApiRateLimit

logger = logging.getLogger(__name__)


class RateLimitManager:
    """
    Manejador de rate limiting que soporta operaciones sync y async.
    Totalmente agnóstico al servicio (NubeFact, Migo, etc.)
    """
    
    def __init__(self, service: Optional[ApiService] = None):
        self.service = service
    
    def set_service(self, service: ApiService):
        """Establece el servicio para operaciones."""
        self.service = service
    
    # ===== VERSIÓN SÍNCRONA =====
    
    def check_rate_limit_sync(self, endpoint_name: str) -> Tuple[bool, float]:
        """Verifica rate limit (síncrono)."""
        if not self.service:
            return True, 0.0
            
        try:
            endpoint = ApiEndpoint.objects.filter(
                service=self.service, name=endpoint_name
            ).first()
            
            if not endpoint:
                return True, 0.0
            
            rate_limit = ApiRateLimit.objects.filter(endpoint=endpoint).first()
            if not rate_limit:
                return True, 0.0
            
            if rate_limit.can_make_request():
                return True, 0.0
            else:
                wait_seconds = rate_limit.get_wait_time()
                logger.warning(
                    f"Rate limit excedido para {endpoint_name}. "
                    f"Esperar {wait_seconds:.1f}s"
                )
                return False, wait_seconds
                
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, 0.0
    
    def update_rate_limit_sync(self, endpoint_name: str) -> None:
        """Actualiza rate limit (síncrono)."""
        if not self.service:
            return
            
        try:
            endpoint = ApiEndpoint.objects.filter(
                service=self.service, name=endpoint_name
            ).first()
            
            if endpoint:
                rate_limit, created = ApiRateLimit.objects.get_or_create(
                    endpoint=endpoint,
                    defaults={"service": self.service}
                )
                rate_limit.increment_count()
                
        except Exception as e:
            logger.error(f"Error updating rate limit: {e}")
    
    # ===== VERSIÓN ASÍNCRONA =====
    
    async def check_rate_limit_async(self, endpoint_name: str) -> Tuple[bool, float]:
        """Verifica rate limit (asíncrono)."""
        return await sync_to_async(self.check_rate_limit_sync)(endpoint_name)
    
    async def update_rate_limit_async(self, endpoint_name: str) -> None:
        """Actualiza rate limit (asíncrono)."""
        await sync_to_async(self.update_rate_limit_sync)(endpoint_name)