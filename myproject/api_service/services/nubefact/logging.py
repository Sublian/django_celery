"""
Módulo de logging para API calls.
Proporciona funciones para guardar logs en ApiCallLog de forma síncrona y asíncrona.
"""

import logging
from typing import Optional, Dict
from django.utils import timezone
from asgiref.sync import sync_to_async

from api_service.models import ApiCallLog, ApiService, ApiEndpoint, ApiBatchRequest

logger = logging.getLogger(__name__)

async def save_api_log_async(
    endpoint_name: str,
    status_code: int,
    duration_ms: int,
    request_data: Optional[Dict] = None,
    response_data: Optional[Dict] = None,
    called_from: str = "unknown",
    batch_request: ApiBatchRequest = None,
    config=None,
    verbose: bool = False, 
) -> None:
    """
    Guarda un log de API de manera asíncrona.
    """
    
    try:
        # 1. Obtener servicio (prioridad: config -> BD)
        if config and config.service:
            service = config.service
            if verbose:
                print(f"🔍 DEBUG - [logging] Usando service desde config: ID={service.id}")
        else:
            if verbose:
                print(f"🔍 DEBUG - [logging] Buscando servicio en BD...")
            service = await sync_to_async(ApiService.objects.get)(name="NUBEFACT Perú")
            if verbose:            
                print(f"🔍 DEBUG - [logging] Service encontrado en BD: ID={service.id}")
        
        # 2. Obtener endpoint (prioridad: config -> BD)
        if config:
            endpoint = config.get_endpoint(endpoint_name)
            if endpoint and verbose:
                # ✅ Imprimir solo ID y path, no acceder a relaciones
                print(f"🔍 DEBUG - [logging] Endpoint desde config: ID={endpoint.id}, path={endpoint.path}")
        
        if not endpoint:
            if verbose:
                print(f"🔍 DEBUG - [logging] Buscando endpoint en BD...")
            endpoint = await sync_to_async(ApiEndpoint.objects.get)(
                service=service, name=endpoint_name
            )
            if verbose:
                print(f"🔍 DEBUG - [logging] Endpoint encontrado en BD: ID={endpoint.id}")
        
        # 3. Determinar estado
        is_success = 200 <= status_code < 300
        error_message = None
        if not is_success and response_data:
            error_message = response_data.get("error") or response_data.get("errors")

        # 4. Crear log con objetos reales
        log_entry = await sync_to_async(ApiCallLog.objects.create)(
            service=service,
            endpoint=endpoint,
            response_code=status_code,
            duration_ms=duration_ms,
            request_data=request_data,
            response_data=response_data,
            called_from=called_from,
            batch_request=batch_request,
            status="SUCCESS" if is_success else "FAILED",
            error_message=error_message,
            created_at=timezone.now(),
        )
        if verbose:
            print(f"✅ [logging] Log guardado con ID: {log_entry.id}")
        else:
            # En producción, solo logs de error
            if not is_success:
                logger.warning(f"API call failed: {endpoint_name} - {status_code} - {error_message}")
        
    except ApiService.DoesNotExist:
        if verbose:
            print(f"❌ [logging] ERROR: Servicio 'NUBEFACT Perú' no encontrado en BD")
        else: 
            logger.error(f"❌ [logging] ERROR: Servicio 'NUBEFACT Perú' no encontrado en BD")
        
    except ApiEndpoint.DoesNotExist:
        if verbose:
            print(f"❌ [logging] ERROR: Endpoint '{endpoint_name}' no encontrado en BD")
        else: 
            logger.error(f"❌ [logging] ERROR: Endpoint '{endpoint_name}' no encontrado en BD")
        # if service:
        #     endpoints = await sync_to_async(list)(
        #         ApiEndpoint.objects.filter(service=service).values_list('name', flat=True)
        #     )
        #     print(f"🔍 DEBUG - [logging] Endpoints disponibles: {endpoints}")
    except Exception as e:
        if verbose:
            print(f"❌ [logging] ERROR inesperado: {type(e).__name__}: {str(e)}")
        else:
            logger.error(f"❌ [logging] ERROR: Endpoint '{endpoint_name}' no encontrado en BD")
            import traceback
            logger.error(traceback.print_exc())

def save_api_log_sync(
    endpoint_name: str,
    status_code: int,
    duration_ms: int,
    request_data: Optional[Dict] = None,
    response_data: Optional[Dict] = None,
    called_from: str = "unknown",
    batch_request: ApiBatchRequest = None,
) -> None:
    """
    Guarda un log de API de manera síncrona.
    """
    try:
        service = ApiService.objects.get(name="NUBEFACT Perú")
        endpoint = ApiEndpoint.objects.get(service=service, name=endpoint_name)

        is_success = 200 <= status_code < 300
        error_message = None
        if not is_success and response_data:
            error_message = response_data.get("error") or response_data.get("errors")

        ApiCallLog.objects.create(
            service=service,
            endpoint=endpoint,
            response_code=status_code,
            duration_ms=duration_ms,
            request_data=request_data,
            response_data=response_data,
            called_from=called_from,
            batch_request=batch_request,
            status="SUCCESS" if is_success else "FAILED",
            error_message=error_message,
            created_at=timezone.now(),
        )
        logger.debug(f"Log guardado para {endpoint_name} - status: {status_code}")
    except Exception as e:
        logger.error(f"Error guardando log síncrono: {e}", exc_info=True)