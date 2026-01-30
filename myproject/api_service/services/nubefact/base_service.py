# api_service/services/base_service.py
import inspect
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional
from django.conf import settings
from api_service.models import ApiEndpoint, ApiService, ApiCallLog

logger = logging.getLogger(__name__)

class BaseAPIService(ABC):
    """Clase base abstracta para todos los servicios de API con logging integrado."""
    
    def __init__(self, service_type: str):
        self.service_type = service_type
        self.service = None
        self._load_config()
    
    def _load_config(self):
        """Carga la configuración del servicio desde la base de datos."""
        try:            
            
            self.service = ApiService.objects.filter(
                service_type=self.service_type,
                is_active=True
            ).first()
            
            if not self.service:
                raise ValueError(
                    f"No se encontró configuración activa para el servicio {self.service_type}"
                )
                
            logger.info(f"Configuración cargada para {self.service_type}: {self.service.base_url}")
            
        except Exception as e:
            logger.error(f"Error cargando configuración para {self.service_type}: {e}")
            raise
    
    @abstractmethod
    def send_request(self, endpoint: str, data: dict, method: str = "POST"):
        """Método abstracto para enviar solicitudes."""
        pass
    
    def _get_caller_info(self) -> str:
        """Obtiene información del llamador para logging."""
        
        try:
            # Obtener el frame del llamador (2 niveles arriba)
            frame = inspect.currentframe().f_back.f_back
            if frame:
                module = inspect.getmodule(frame)
                if module:
                    return f"{module.__name__}:{frame.f_code.co_name}"
        except:
            pass
        return "unknown"
    
    def _get_endpoint(self, endpoint_name: str):
        """Obtiene o crea un endpoint en la base de datos."""
               
        if not self.service:
            return None
            
        return ApiEndpoint.objects.filter(
                service=self.service,
                name=endpoint_name
            ).first()     
    
    def _log_api_call(self, endpoint_name: str, request_data: dict, 
                     response_data: dict, status: str, error_message: str = "", 
                     duration_ms: int = 0, batch_request=None,
                     caller_info: str = None) -> None:
        """
        Registra llamada API en base de datos.
        FUNCIÓN REUTILIZADA: Copiada desde tu código existente.
        
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

        # Si no hay servicio (p.ej. tests que evitan inicializar DB), solo loguear
        if not self.service:
            logger.debug(
                f"[API_CALL] {endpoint_name} status={status} duration={duration_ms}ms error={error_message}"
            )
            return

        try:
            endpoint = self._get_endpoint(endpoint_name)
            print(f" 🔍 Endpoint encontrado: {endpoint}")

            # Si es un RUC inválido (404), registrar información adicional
            if status == "FAILED" and "404" in error_message:
                response_data['invalid_ruc'] = True
                response_data['invalid_reason'] = "RUC_NO_EXISTE_SUNAT"

            ApiCallLog.objects.create(
                service=self.service,
                endpoint=endpoint.id if endpoint else None,
                batch_request=batch_request,
                status=status,
                request_data=request_data,
                response_data=response_data,
                response_code=response_data.get('status_code', 200) if isinstance(response_data, dict) else 200,
                error_message=error_message[:500],
                duration_ms=duration_ms,
                called_from=caller_info
            )
            
            logger.info(f"[API_CALL_LOGGED] {endpoint_name} - {status} - {duration_ms}ms")
            
        except Exception as e:
            logger.error(f"Error logging API call: {str(e)}")
            
    @property
    def base_url(self):
        return self.service.base_url if self.service else None
    
    @property
    def auth_token(self):
        return self.service.auth_token if self.service else None
    
    @property
    def auth_type(self):
        return self.service.auth_type if self.service else None
    
    @abstractmethod
    def send_request(self, endpoint: str, data: dict, method: str = "POST"):
        """Método abstracto para enviar solicitudes."""
        pass