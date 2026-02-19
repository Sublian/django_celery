# test_nubefact.py
import os
import sys
import django
import time

# Configurar Django
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# IMPORTACIÓN CORRECTA para tu estructura
# Desde la carpeta nubefact dentro de services
from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.models import ApiCallLog

# Si no tienes el archivo exceptions.py, comenta o elimina esta línea:
# from api_service.services.nubefact_service.exceptions import NubefactAPIError
REF_NUMBER = 91431
# Tu JSON base (copiado de tu mensaje)
JSON_BASE = {
    "serie": "F001",
    "numero": 91501,
    "cliente_denominacion": "CLIENTE DE PRUEBA S.A.C.",
    "cliente_numero_de_documento": "20123456789",
    "cliente_direccion": "AV. PRUEBA 123, LIMA",
    "fecha_de_emision": "2024-01-31",
    "fecha_de_vencimiento": "2024-02-28",
    "moneda": "1",
    "total_gravada": 1000.0,
    "porcentaje_igv": 18.0,
    "total_igv": "180.00",
    "total": "1180.00",
    "observaciones": "Factura de prueba",
    "condiciones_de_pago": "CONTADO",
    "items": [
        {
            "unidad_de_medida": "ZZ",
            "codigo": "TEST001",
            "descripcion": "SERVICIO DE PRUEBA",
            "cantidad": 1.0,
            "valor_unitario": 1000.0,
            "precio_unitario": 1180.0,
            "subtotal": 1000.0,
            "igv": 180.0,
            "total": 1180.0,
            "codigo_producto_sunat": "81112101",
        }
    ],
}


def test_nubefact_with_logging():
    """Prueba la emisión de un comprobante en Nubefact."""
    print("🔧 Iniciando prueba de emisión Nubefact...")

    # Contar logs antes de la prueba
    initial_log_count = ApiCallLog.objects.filter(
        service__service_type="NUBEFACT"
    ).count()
    print(f"   Logs existentes antes: {initial_log_count}")

    try:
        # 1. Crear instancia del servicio
        print("1. Creando servicio Nubefact...")
        servicio = NubefactService()

        # 2. Verificar configuración cargada
        print(f"   URL Base: {servicio.base_url}")
        print(
            f"   Token: {'*' * 10}{servicio.auth_token[-5:] if servicio.auth_token else 'NO TOKEN'}"
        )

        # 3. Enviar comprobante
        print("\n2. Enviando comprobante a Nubefact...")
        respuesta = servicio.emitir_comprobante(JSON_BASE)
        # Esperar un momento para que se complete el logging
        time.sleep(0.5)

        # Verificar logs creados
        new_logs = ApiCallLog.objects.filter(service__service_type="NUBEFACT").order_by(
            "-created_at"
        )
        logs_count = new_logs.count()
        print(f"\n📊 Logs después de la llamada: {logs_count}")
        if logs_count > initial_log_count:
            latest_log = new_logs.first()
            print("✅ Log registrado correctamente!")
            print(
                f"   Endpoint: {latest_log.endpoint.name if latest_log.endpoint else 'N/A'}"
            )
            print(f"   Status: {latest_log.status}")
            print(f"   Duración: {latest_log.duration_ms}ms")
            print(f"   Creado: {latest_log.created_at}")

            # Mostrar respuesta guardada en el log
            if latest_log.response_data:
                print(f"   Respuesta en log:")
                print(f"     - Enlace: {latest_log.response_data.get('enlace', 'N/A')}")
                print(
                    f"     - Estado SUNAT: {latest_log.response_data.get('aceptada_por_sunat', 'N/A')}"
                )
        else:
            print(
                "⚠️  No se encontraron nuevos logs. Verifica que el modelo ApiCallLog exista."
            )

        # Mostrar respuesta directa
        print(f"\n📨 Respuesta directa de Nubefact:")
        print(f"   Enlace: {respuesta.get('enlace', 'No disponible')}")
        print(
            f"   Estado SUNAT: {respuesta.get('aceptada_por_sunat', 'No especificado')}"
        )

        return respuesta, new_logs

    except Exception as e:
        print(f"\n❌ Error durante la prueba:")
        print(f"   {type(e).__name__}: {str(e)}")

        # Verificar si se creó un log de error
        error_logs = ApiCallLog.objects.filter(
            service__service_type="NUBEFACT", status="FAILED"
        ).order_by("-created_at")

        if error_logs.exists():
            print(f"   Log de error creado: {error_logs.first().error_message[:100]}")

        raise


if __name__ == "__main__":
    try:
        resultado = test_nubefact_with_logging()
        print("\n🎉 Prueba completada exitosamente!")
    except Exception as e:
        print(f"\n💥 Prueba falló: {e}")
        sys.exit(1)
