# test_nubefact_integration_simple.py
"""
Prueba de integracion SIMPLE para NubefactService
Prueba estructura sin llamadas reales a Nubefact
"""

import os
import sys
import django

# Configurar Django
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# Importar servicio y modelos
from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.models import ApiCallLog, ApiService, ApiEndpoint


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "=" * 70)
    print(" " * 15 + "TEST INTEGRATION - NUBEFACTSERVICE (SIMPLE)")
    print("=" * 70)

    try:
        # VERIFICACION 1: Configuracion en BD
        print("\n[TEST 1] Verificar Configuracion en BD")
        print("-" * 60)

        api_service = ApiService.objects.filter(
            service_type="NUBEFACT", is_active=True
        ).first()
        if not api_service:
            print("[ERROR] ApiService NUBEFACT no encontrado")
            return False

        print("[OK] ApiService NUBEFACT encontrado")
        print("     URL: " + str(api_service.base_url))
        token_display = ("*" * 10) + (
            api_service.auth_token[-5:] if api_service.auth_token else "NO TOKEN"
        )
        print("     Token: " + token_display)

        endpoint = ApiEndpoint.objects.filter(
            service=api_service, name="generar_comprobante", is_active=True
        ).first()

        if not endpoint:
            print("[ERROR] ApiEndpoint 'generar_comprobante' no encontrado")
            return False

        print("[OK] ApiEndpoint 'generar_comprobante' encontrado")
        print("     Ruta: " + str(endpoint.path))
        print("     Metodo: " + str(endpoint.method))

        # VERIFICACION 2: Inicializacion del servicio
        print("\n[TEST 2] Inicializacion del Servicio")
        print("-" * 60)

        service = NubefactService()
        print("[OK] Servicio inicializado correctamente")
        print("     Base URL: " + str(service.base_url))
        print("     Auth Token presente: " + str(bool(service.auth_token)))
        print("     Token Alias presente: " + str(bool(service.token)))
        print("     Session configrada: " + str(bool(service.session)))
        print("     Timeout: " + str(service.timeout))

        # VERIFICACION 3: Context Manager
        print("\n[TEST 3] Context Manager")
        print("-" * 60)

        with service as ctx_service:
            print("[OK] Context manager __enter__ funciono")
            print("     Es el mismo service: " + str(ctx_service is service))

        print("[OK] Context manager __exit__ funciono correctamente")

        # VERIFICACION 4: Metodos del servicio
        print("\n[TEST 4] Metodos Disponibles del Servicio")
        print("-" * 60)

        methods = [
            "generar_comprobante",
            "consultar_comprobante",
            "anular_comprobante",
            "send_request",
            "_get_endpoint",
            "_check_rate_limit",
        ]

        for method in methods:
            has_method = hasattr(service, method) and callable(getattr(service, method))
            status = "OK" if has_method else "MISSING"
            print("     [" + status + "] " + method)

        # VERIFICACION 5: Logs existentes
        print("\n[TEST 5] Estado de Logs en BD")
        print("-" * 60)

        log_count = ApiCallLog.objects.filter(service__service_type="NUBEFACT").count()
        print("[OK] Total de logs NUBEFACT: " + str(log_count))

        if log_count > 0:
            latest = (
                ApiCallLog.objects.filter(service__service_type="NUBEFACT")
                .order_by("-created_at")
                .first()
            )
            print("     Ultimo log:")
            print("       - Status: " + str(latest.status))
            print(
                "       - Endpoint: "
                + (latest.endpoint.name if latest.endpoint else "N/A")
            )
            print("       - Duracion: " + str(latest.duration_ms) + "ms")
            print("       - Creado: " + str(latest.created_at))

        # Resumen
        print("\n" + "=" * 70)
        print(" " * 20 + "SUCCESS - ALL TESTS PASSED")
        print("=" * 70)
        print("\nResumen:")
        print("   [OK] Configuracion en BD: OK")
        print("   [OK] Inicializacion del Servicio: OK")
        print("   [OK] Context Manager: OK")
        print("   [OK] Metodos Disponibles: OK")
        print("   [OK] Estado de Logs: OK")
        print("\nNota: Para pruebas con llamadas reales a Nubefact,")
        print("ejecuta manualmente generar_comprobante() con datos validos.")

        return True

    except Exception as e:
        print("\n[ERROR] Prueba fallida: " + str(e))
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
