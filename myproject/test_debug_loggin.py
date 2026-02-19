# test_debug_loggin_fixed.py
import os
import django
import asyncio
from asgiref.sync import sync_to_async

# Configurar Django PRIMERO
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()


async def test_single_request_with_logging():
    """Hace una sola petición y verifica el logging"""
    print("=" * 60)
    print("🔍 DIAGNÓSTICO DE LOGGING (FIXED)")
    print("=" * 60)

    from api_service.models import ApiCallLog
    from api_service.services.nubefact.nubefact_service_async import (
        NubefactServiceAsync,
    )

    # Contar logs antes (usando sync_to_async)
    initial_count = await sync_to_async(ApiCallLog.objects.count)()
    print(f"Logs en BD antes: {initial_count}")

    # Verificar configuración
    from api_service.models import ApiService, ApiEndpoint

    service_exists = await sync_to_async(
        ApiService.objects.filter(name="NubeFact").exists
    )()
    endpoint_exists = await sync_to_async(
        lambda: ApiEndpoint.objects.filter(name="generar_comprobante").exists()
    )()

    print(f"\n🔧 Configuración:")
    print(f"   Servicio NubeFact en BD: {'✅' if service_exists else '❌'}")
    print(f"   Endpoint generar_comprobante: {'✅' if endpoint_exists else '❌'}")

    if not service_exists or not endpoint_exists:
        print("\n⚠️  ¡Necesitas configurar la BD primero!")
        print("   Ejecuta: python manage.py migrate")
        print("   Y crea los registros en el admin de Django")
        return

    # Crear servicio
    service = NubefactServiceAsync()

    # Datos mínimos para prueba
    test_data = {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": 1,
        "serie": "F001",
        "numero": "99999",
        "cliente_denominacion": "TEST LOGGING",
        "cliente_numero_de_documento": "20123456789",
        "fecha_de_emision": "2024-02-06",
        "total": 100.00,
    }

    print(f"\n📤 Enviando petición de prueba...")

    try:
        # Hacer una sola petición
        result = await service.generar_comprobante(test_data)
        print(f"✅ Petición exitosa")
        print(f"   Número: {result.get('numero', 'N/A')}")
        print(f"   Hash: {result.get('codigo_hash', 'N/A')[:30]}...")

        # Esperar para que el log asíncrono se complete
        print(f"\n⏳ Esperando que se complete el logging async...")
        await asyncio.sleep(3)  # Dar tiempo al task async

        # Contar logs después
        final_count = await sync_to_async(ApiCallLog.objects.count)()
        print(f"Logs en BD después: {final_count}")

        if final_count > initial_count:
            print(f"✅ SE CREÓ LOG NUEVO (+{final_count - initial_count})")

            # Mostrar el último log
            latest = await sync_to_async(
                lambda: ApiCallLog.objects.order_by("-created_at").first()
            )()

            if latest:
                print(f"\n📝 ÚLTIMO LOG CREADO:")
                print(f"   ID: {latest.id}")
                print(
                    f"   Endpoint: {latest.endpoint.name if latest.endpoint else 'N/A'}"
                )
                print(f"   Status: {latest.status}")
                print(f"   Duration: {latest.duration_ms}ms")
                print(f"   Created: {latest.created_at}")

                # Mostrar parte de los datos
                if latest.request_data:
                    req_data = latest.request_data
                    if isinstance(req_data, str) and len(req_data) > 100:
                        print(f"   Request Data: {req_data[:100]}...")
                    else:
                        print(f"   Request Data: {str(req_data)[:100]}...")

                if latest.response_data:
                    resp_data = latest.response_data
                    if isinstance(resp_data, str) and len(resp_data) > 100:
                        print(f"   Response Data: {resp_data[:100]}...")
                    else:
                        print(f"   Response Data: {str(resp_data)[:100]}...")

                print(f"   Called From: '{latest.called_from}'")
        else:
            print("❌ NO SE CREÓ NINGÚN LOG NUEVO")

            # Verificar si hay logs recientes
            print(f"\n📋 Últimos 3 logs (cualquier origen):")
            logs = await sync_to_async(
                lambda: list(ApiCallLog.objects.order_by("-created_at")[:3])
            )()

            for log in logs:
                print(
                    f"   - {log.created_at}: {log.endpoint.name if log.endpoint else 'N/A'} ({log.status})"
                )

    except Exception as e:
        print(f"❌ ERROR en la petición: {str(e)}")
        import traceback

        traceback.print_exc()


async def check_database_setup():
    """Verifica que la BD tenga la configuración necesaria"""
    from api_service.models import ApiService, ApiEndpoint

    print("\n" + "=" * 60)
    print("🏗️  VERIFICACIÓN DE CONFIGURACIÓN DE BD")
    print("=" * 60)

    # Crear servicio si no existe
    service, created = await sync_to_async(
        lambda: ApiService.objects.get_or_create(
            name="NUBEFACT Perú",
            defaults={
                "base_url": "https://api.nubefact.com",
                "service_type": "NUBEFACT",
            },
        )
    )()

    if created:
        print(f"✅ Servicio 'NubeFact' creado (ID: {service.id})")
    else:
        print(f"✅ Servicio 'NubeFact' ya existe (ID: {service.id})")

    # Crear endpoints si no existen
    endpoints = [
        ("generar_comprobante", "POST", "/api/v1/comprobante"),
        ("consultar_comprobante", "GET", "/api/v1/comprobante"),
        ("anular_comprobante", "POST", "/api/v1/comprobante/anular"),
    ]

    for name, method, path in endpoints:
        endpoint, created = await sync_to_async(
            lambda n, m, p: ApiEndpoint.objects.get_or_create(
                service=service, name=n, defaults={"method": m, "path": p}
            )
        )(name, method, path)

        if created:
            print(f"✅ Endpoint '{name}' creado")
        else:
            print(f"✅ Endpoint '{name}' ya existe")


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Primero verificar/crear configuración
        loop.run_until_complete(check_database_setup())

        # Luego probar el logging
        loop.run_until_complete(test_single_request_with_logging())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
