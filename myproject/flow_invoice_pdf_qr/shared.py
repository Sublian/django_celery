# test_sinc_invoice_pdf_qr/shared.py
"""
Código compartido para todos los pasos de prueba.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from asgiref.sync import sync_to_async
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django
django.setup()

from api_service.models import ApiCallLog, ApiService, ApiEndpoint


def setup_directories(base_dir: Path = Path("test_output")) -> Path:
    """Crea y retorna el directorio para esta ejecución."""
    output_dir = base_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_test_invoice_data(invoice_number: Optional[str] = None) -> Dict[str, Any]:
    """Crea datos de prueba para una factura - VERSIÓN CON STRINGS (que funciona)"""
    if invoice_number is None:
        invoice_number = f"{int(datetime.now().timestamp() % 100000)}"

    return {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": "1",
        "serie": "F001",
        "numero": str(invoice_number),
        "sunat_transaction": "1",
        "cliente_tipo_de_documento": "6",
        "cliente_numero_de_documento": "20343443961",
        "cliente_denominacion": "EMPRESA DE PRUEBA V2 S.A.C.",
        "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
        "cliente_email": "contacto@empresaprueba.com",
        "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
        "fecha_de_vencimiento": datetime.now().strftime("%Y-%m-%d"),
        "moneda": "1",
        "tipo_de_cambio": "1",
        "porcentaje_de_igv": "18.00",
        "total_gravada": "847.46",
        "total_igv": "152.54",
        "total": "1000.00",
        "enviar_automaticamente_a_la_sunat": "false",
        "enviar_automaticamente_al_cliente": "false",
        "items": [
            {
                "unidad_de_medida": "ZZ",
                "codigo": "SERV-001",
                "descripcion": "SERVICIO DE CONSULTORÍA IT - Asesoría técnica",
                "cantidad": "10",
                "valor_unitario": "84.746",
                "precio_unitario": "100.00",
                "subtotal": "847.46",
                "tipo_de_igv": "1",
                "igv": "152.54",
                "total": "1000.00",
                "codigo_producto_sunat": "81112105",
            }
        ],
    }


def save_response_to_file(response: Dict, filename: str, output_dir: Path) -> Path:
    """Guarda la respuesta de NubeFact en un archivo JSON."""
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False)
    print(f"✅ Respuesta guardada en: {filepath}")
    return filepath


def load_response_from_file(filepath: Path) -> Dict:
    """Carga una respuesta guardada desde un archivo JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


async def check_logs(invoice_number: str) -> None:
    """Verifica que exista un log para esta factura - VERSIÓN ASÍNCRONA"""    
    
    # ✅ Usar sync_to_async para la consulta
    logs = await sync_to_async(
        lambda: list(
            ApiCallLog.objects.filter(
                response_data__contains=f'"{invoice_number}"'
            ).order_by('-created_at')[:3]
        )
    )()
    
    # También obtener el count con sync_to_async
    count = await sync_to_async(
        lambda: ApiCallLog.objects.filter(
            response_data__contains=f'"{invoice_number}"'
        ).count()
    )()
    
    print(f"\n📊 LOGS ENCONTRADOS: {count}")
    for log in logs:
        # ✅ Usar sync_to_async para acceder a cada campo
        created_at = await sync_to_async(lambda: log.created_at)()
        status = await sync_to_async(lambda: log.status)()
        response_code = await sync_to_async(lambda: log.response_code)()
        
        print(f"   - {created_at}: {status} ({response_code})")
        
        error_message = await sync_to_async(lambda: log.error_message)()
        if error_message:
            print(f"     Error: {error_message[:100]}")
    
async def save_api_log(
    endpoint_name: str,
    status_code: int,
    duration_ms: int,
    request_data: dict = None,
    response_data: dict = None,
    called_from: str = "step1_send_only"
) -> None:
    """
    Guarda un log en ApiCallLog de manera asíncrona.
    """
    try:
        # Buscar servicio y endpoint usando sync_to_async
        service = await sync_to_async(ApiService.objects.get)(name="NUBEFACT Perú")
        endpoint = await sync_to_async(ApiEndpoint.objects.get)(
            service=service, 
            name=endpoint_name
        )
        
        # Determinar estado
        is_success = 200 <= status_code < 300
        
        # Crear log
        await sync_to_async(ApiCallLog.objects.create)(
            service=service,
            endpoint=endpoint,
            response_code=status_code,
            duration_ms=duration_ms,
            request_data=request_data,
            response_data=response_data,
            called_from=called_from,
            status="SUCCESS" if is_success else "FAILED",
            error_message=(
                response_data.get("error") or response_data.get("errors")
                if not is_success and response_data
                else None
            ),
            created_at=timezone.now(),
        )
        
        logger.debug(f"✅ Log guardado para {endpoint_name} - status: {status_code}")
        
    except ApiService.DoesNotExist:
        logger.error("⚠️ Servicio 'NUBEFACT Perú' no encontrado en BD")
    except ApiEndpoint.DoesNotExist:
        logger.error(f"⚠️ Endpoint '{endpoint_name}' no encontrado en BD")
    except Exception as e:
        logger.error(f"⚠️ Error guardando log: {str(e)}")