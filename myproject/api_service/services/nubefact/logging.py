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
) -> None:
    """
    Guarda un log de API de manera asíncrona.
    """
    try:
        service = await sync_to_async(ApiService.objects.get)(name="NUBEFACT Perú")
        endpoint = await sync_to_async(ApiEndpoint.objects.get)(
            service=service, name=endpoint_name
        )

        is_success = 200 <= status_code < 300
        error_message = None
        if not is_success and response_data:
            error_message = response_data.get("error") or response_data.get("errors")

        await sync_to_async(ApiCallLog.objects.create)(
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
    except ApiService.DoesNotExist:
        logger.error("Servicio NUBEFACT Perú no encontrado en BD")
    except ApiEndpoint.DoesNotExist:
        logger.error(f"Endpoint '{endpoint_name}' no encontrado en BD")
    except Exception as e:
        logger.error(f"Error guardando log: {e}", exc_info=True)


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