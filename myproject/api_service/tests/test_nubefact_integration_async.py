"""
Prueba de integración REAL para NubefactServiceAsync.
Envía datos reales a la API de Nubefact usando async.
Requiere credenciales configuradas en ApiService (NUBEFACT).

Ejecutar: python manage.py shell < api_service/tests/test_nubefact_integration_async.py
"""

import asyncio
import json
import time
from datetime import datetime
from decimal import Decimal


async def run_test():
    from api_service.services.nubefact.nubefact_service_async import (
        NubefactServiceAsync,
    )
    from api_service.models import ApiCallLog

    print("=" * 70)
    print("PRUEBA DE INTEGRACION ASYNC - NubefactServiceAsync")
    print("=" * 70)

    # Obtener conteo inicial de logs
    initial_log_count = ApiCallLog.objects.count()
    print(f"\n[LOG] Registros iniciales de ApiCallLog: {initial_log_count}")

    # Crear servicio
    print("\n[INIT] Inicializando NubefactServiceAsync...")
    try:
        async with NubefactServiceAsync() as svc:
            print(f"[CONFIG] Base URL: {svc.base_url}")
            print(
                f"[CONFIG] Auth Token: {svc.auth_token[:20]}..."
                if svc.auth_token
                else "N/A"
            )

            # Payload de prueba
            payload = {
                "serie": "F001",
                "numero": int(time.time()) % 10000,  # Número único por timestamp
                "cliente": {
                    "tipo_documento": 6,
                    "numero_documento": "20123456789",
                    "nombre": "Test Cliente Async",
                    "email": "test@example.com",
                },
                "tipo_comprobante": 1,
                "fecha_emision": datetime.now().strftime("%Y-%m-%d"),
                "moneda": 1,
                "items": [
                    {
                        "descripcion": "Producto Test Async",
                        "cantidad": 1,
                        "precio_unitario": 100.00,
                        "descuento": 0,
                        "igv": 18.00,
                    }
                ],
                "total_gravada": 100.00,
                "total_igv": 18.00,
                "total": 118.00,
            }

            print("\n[REQUEST] Enviando generar_comprobante async...")
            print(
                f"[PAYLOAD] Número de documento cliente: {payload['cliente']['numero_documento']}"
            )
            print(f"[PAYLOAD] Total: {payload['total']}")

            start = time.time()
            try:
                response = await svc.generar_comprobante(payload)
                duration = time.time() - start

                print(f"\n[RESPONSE] Éxito en {duration:.2f}s")
                print(f"[RESPONSE] Status Code: {response.get('status_code', 'N/A')}")
                print(f"[RESPONSE] Enlace: {response.get('enlace', 'N/A')}")
                print(f"[RESPONSE] Número: {response.get('numero', 'N/A')}")
                print(
                    f"[RESPONSE] Completo: {json.dumps(response, indent=2, default=str)[:500]}"
                )

            except Exception as e:
                duration = time.time() - start
                print(f"\n[ERROR] Falló en {duration:.2f}s")
                print(f"[ERROR] {str(e)}")

    except Exception as e:
        print(f"[INIT_ERROR] {str(e)}")
        return

    # Verificar logs creados
    final_log_count = ApiCallLog.objects.count()
    new_logs = final_log_count - initial_log_count
    print(f"\n[LOG] Registros finales de ApiCallLog: {final_log_count}")
    print(f"[LOG] Nuevos registros: {new_logs}")

    if new_logs > 0:
        latest_log = ApiCallLog.objects.order_by("-id").first()
        print(f"\n[LATEST_LOG] ID: {latest_log.id}")
        print(f"[LATEST_LOG] Status: {latest_log.status}")
        print(f"[LATEST_LOG] Duration: {latest_log.duration_ms}ms")
        print(f"[LATEST_LOG] Error: {latest_log.error_message or 'None'}")

    print("\n" + "=" * 70)
    print("FIN DE PRUEBA DE INTEGRACION ASYNC")
    print("=" * 70)


# Ejecutar desde manage.py shell
if __name__ == "__main__" or True:  # Always run in shell context
    asyncio.run(run_test())
