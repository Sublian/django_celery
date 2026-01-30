"""
Prueba de integración REAL para NubefactServiceAsync.
Ejecutar: python test_nubefact_integration_async.py desde el directorio myproject/
"""
import os
import sys
import django
import asyncio
import json
import time
from datetime import datetime
from asgiref.sync import sync_to_async
from functools import wraps

# Configurar ruta y Django
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.join(current_dir, "..", "..")  # Ir a myproject/
sys.path.insert(0, project_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# Inicializar Django
try:
    django.setup()
except Exception as e:
    print(f"Error en Django setup: {e}")
    sys.exit(1)

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from api_service.models import ApiCallLog


async def run_integration_test():
    print("=" * 70)
    print("PRUEBA DE INTEGRACION ASYNC - NubefactServiceAsync")
    print("=" * 70)
    
    # Querys a BD deben ser sync (envueltas con sync_to_async)
    initial_log_count = await sync_to_async(ApiCallLog.objects.count)()
    print(f"\n[LOG] Registros iniciales de ApiCallLog: {initial_log_count}")
    
    print("\n[INIT] Inicializando NubefactServiceAsync...")
    
    # La inicialización de NubefactServiceAsync hace llamadas sync a BD
    # Envolver el __init__ con sync_to_async
    async def create_service():
        def _init():
            return NubefactServiceAsync()
        return await sync_to_async(_init)()
    
    try:
        svc = await create_service()
        try:
            print(f"[CONFIG] Base URL: {svc.base_url}")
            print(f"[CONFIG] Auth Token: {svc.auth_token[:20]}..." if svc.auth_token else "N/A")
            REF_NUMBER = 91430
            # Payload de prueba (estructura compatible con API Nubefact)
            payload = {
                "operacion": "generar_comprobante",
                "tipo_de_comprobante": "1",
                "serie": "F001",
                "numero": REF_NUMBER,
                "cliente_tipo_de_documento": "6",
                "cliente_numero_de_documento": "20343443961",
                "cliente_denominacion": "Test Cliente Async",
                "cliente_email": "test@example.com",
                "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
                "moneda": "1",
                "porcentaje_de_igv": 18.0,
                "total_gravada": 100.00,
                "total_igv": 18.00,
                "total": 118.00,
                "items": [
                    {
                        "descripcion": "Producto Test",
                        "cantidad": 1,
                        "precio_unitario": 100.00,
                        "descuento": 0,
                        "total": 118.00
                    }
                ]
            }
            
            print("\n[REQUEST] Enviando generar_comprobante async...")
            print(f"[PAYLOAD] Número: {payload['numero']}")
            print(f"[PAYLOAD] Total: {payload['total']}")
            
            start = time.time()
            try:
                # Envolver send_request async en sync_to_async para evitar SynchronousOnlyOperation
                async def send_and_log():
                    return await svc.generar_comprobante(payload)
                
                response = await send_and_log()
                duration = time.time() - start
                
                print(f"\n[RESPONSE OK] Completado en {duration:.2f}s")
                print(f"[RESPONSE] Datos: {json.dumps(response, indent=2, default=str)[:800]}")
                
            except Exception as e:
                duration = time.time() - start
                print(f"\n[RESPONSE ERROR] Falló en {duration:.2f}s")
                print(f"[ERROR] {type(e).__name__}: {str(e)}")
        finally:
            # Cerrar cliente async
            if hasattr(svc, '_client') and svc._client:
                await svc._client.aclose()
    
    except Exception as e:
        print(f"[INIT_ERROR] {str(e)}")
        return
    
    final_log_count = await sync_to_async(ApiCallLog.objects.count)()
    new_logs = final_log_count - initial_log_count
    print(f"\n[LOG] Registros finales de ApiCallLog: {final_log_count}")
    print(f"[LOG] Nuevos registros: {new_logs}")
    
    if new_logs > 0:
        async def get_latest():
            return ApiCallLog.objects.order_by('-id').first()
        latest_log = await sync_to_async(get_latest)()
        print(f"\n[LATEST_LOG] ID: {latest_log.id}")
        print(f"[LATEST_LOG] Status: {latest_log.status}")
        print(f"[LATEST_LOG] Duration: {latest_log.duration_ms}ms")
        print(f"[LATEST_LOG] Error: {latest_log.error_message or 'None'}")
    
    print("\n" + "=" * 70)
    print("FIN PRUEBA DE INTEGRACION ASYNC")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_integration_test())

