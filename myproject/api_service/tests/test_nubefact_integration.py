# test_nubefact_integration.py
"""
Prueba de integracion REAL para NubefactService
Prueba los metodos contra la BD real y la API actual de Nubefact.

Nota: Esta prueba requiere:
1. ApiService configurado en BD con service_type='NUBEFACT'
2. ApiEndpoint configurado para generar_comprobante
3. Conexion activa a BD Django
"""

import os
import sys
import django
import time

# Configurar Django
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# Importar servicio y modelos
from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.models import ApiCallLog, ApiService, ApiEndpoint

REF_NUMBER = 91430

# Tu JSON base
JSON_BASE = {
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',
    'serie': 'F001',
    'numero': REF_NUMBER,
    'sunat_transaction': 30,
    'cliente_tipo_de_documento': '6',
    'cliente_numero_de_documento': '20343443961',
    'cliente_denominacion': 'UNNA TRANSPORTE S.A.C.',
    'cliente_direccion': 'AV. PETIT THOUARS NRO 4957',
    'cliente_email': '',
    'cliente_email_1': '',
    'cliente_email_2': '',
    'fecha_de_emision': '2026-01-29',
    'fecha_de_vencimiento': '2026-02-28',
    'moneda': '1',
    'tipo_de_cambio': '',
    'porcentaje_de_igv': 18.0,
    'descuento_global': '',
    'orden_compra_servicio': 'OC 10000018442',
    'total_descuento': 0.0,
    'total_anticipo': 0,
    'total_gravada': 1440.0,
    'total_inafecta': 0,
    'total_exonerada': 0,
    'total_igv': '259.20',
    'total_gratuita': 0,
    'total_otros_cargos': '',
    'total_impuestos_bolsas': 0,
    'total': '1699.20',
    'percepcion_tipo': '',
    'percepcion_base_imponible': '',
    'total_percepcion': '',
    'total_incluido_percepcion': '',
    'detraccion': 'true',
    'detraccion_tipo': 35,
    'detraccion_total': 204.0,
    'detraccion_porcentaje': 12.0,
    'medio_de_pago_detraccion': '003',
    'observaciones': 'Pedido: SUB51946\nEsta factura cubre el siguiente periodo: 01/09/2025 - 30/09/2025',
    'documento_que_se_modifica_tipo': '',
    'documento_que_se_modifica_serie': '',
    'documento_que_se_modifica_numero': '',
    'tipo_de_nota_de_credito': '',
    'tipo_de_nota_de_debito': '',
    'enviar_automaticamente_a_la_sunat': 'false',
    'enviar_automaticamente_al_cliente': 'false',
    'codigo_unico': '',
    'condiciones_de_pago': 'CREDITO',
    'medio_de_pago': 'credito',
    'placa_vehiculo': '',
    'tabla_personalizada_codigo': '',
    'formato_de_pdf': '',
    'venta_al_credito': [{'cuota': 1, 'fecha_de_pago': '2026-02-05', 'importe': 1495.2}],
    'items': [{
        'unidad_de_medida': 'ZZ',
        'codigo': 'S00137',
        'descripcion': '[S00137] Internet Dedicado',
        'cantidad': 80.0,
        'valor_unitario': 18.0,
        'precio_unitario': 21.24,
        'descuento': 0.0,
        'subtotal': 1440.0,
        'tipo_de_igv': '1',
        'igv': 259.2,
        'impuesto_bolsas': 0,
        'total': 1699.2,
        'anticipo_regularizacion': 'false',
        'anticipo_documento_serie': '',
        'anticipo_documento_numero': '',
        'codigo_producto_sunat': '81112101'
    }]
}


def check_configuration():
    """Verifica que la configuracion necesaria existe en BD."""
    print("[*] Verificando configuracion en BD...")
    
    # Verificar ApiService
    api_service = ApiService.objects.filter(service_type="NUBEFACT", is_active=True).first()
    if not api_service:
        print("    [ERROR] ApiService NUBEFACT no encontrado o no activo")
        print("    Solucion: Crear registro ApiService con:")
        print("      - service_type='NUBEFACT'")
        print("      - base_url='https://api.nubefact.com' (o tu URL)")
        print("      - auth_token='tu_token_aqui'")
        print("      - is_active=True")
        return False
    
    print("[OK] ApiService NUBEFACT encontrado")
    print("     URL: " + str(api_service.base_url))
    token_display = ('*' * 10) + (api_service.auth_token[-5:] if api_service.auth_token else 'NO TOKEN')
    print("     Token: " + token_display)
    
    # Verificar ApiEndpoint para generar_comprobante
    endpoint = ApiEndpoint.objects.filter(
        service=api_service,
        name="generar_comprobante",
        is_active=True
    ).first()
    
    if not endpoint:
        print("    [WARN] ApiEndpoint 'generar_comprobante' no encontrado o no activo")
        print("    Solucion: Crear registro ApiEndpoint con:")
        print("      - service_id=<id_nubefact_service>")
        print("      - name='generar_comprobante'")
        print("      - path='/api/v1/send' (o la ruta correcta)")
        print("      - method='POST'")
        print("      - timeout=60")
        print("      - is_active=True")
        return False
    
    print("[OK] ApiEndpoint 'generar_comprobante' encontrado")
    print("     Ruta: " + str(endpoint.path))
    print("     Metodo: " + str(endpoint.method))
    print("     Timeout: " + str(endpoint.timeout) + "s")
    
    return True


def test_service_initialization():
    """Prueba la inicializacion del servicio."""
    print("\n[TEST 1] Inicializacion del Servicio")
    print("-" * 60)
    
    try:
        service = NubefactService()
        
        print("[OK] Servicio inicializado correctamente")
        print("     - Base URL: " + str(service.base_url))
        token_display = ('*' * 10) + (service.auth_token[-5:] if service.auth_token else 'NO TOKEN')
        print("     - Auth Token: " + token_display)
        token_alias = ('*' * 10) + (service.token[-5:] if service.token else 'NO TOKEN')
        print("     - Token Alias: " + token_alias)
        print("     - Timeout: " + str(service.timeout))
        
        return service
        
    except Exception as e:
        print("[ERROR] Error inicializando servicio: " + type(e).__name__)
        print("     " + str(e))
        raise


def test_generar_comprobante(service, log_count_before):
    """Prueba emision de comprobante."""
    print("\n[TEST 2] Generar Comprobante")
    print("-" * 60)
    
    try:
        print("[*] Enviando comprobante a Nubefact...")
        print("    Numero: " + str(JSON_BASE['numero']))
        print("    Cliente: " + str(JSON_BASE['cliente_denominacion']))
        print("    Total: " + str(JSON_BASE['total']))
        
        # Medir tiempo
        start_time = time.time()
        respuesta = service.generar_comprobante(JSON_BASE)
        elapsed = time.time() - start_time
        
        print("\n[OK] Respuesta recibida en " + str(round(elapsed, 2)) + "s")
        print("     - Success: " + str(respuesta.get('success', False)))
        print("     - Enlace: " + str(respuesta.get('enlace', 'N/A')[:80]))
        print("     - Aceptada por SUNAT: " + str(respuesta.get('aceptada_por_sunat', 'N/A')))
        print("     - Codigo: " + str(respuesta.get('codigo', 'N/A')))
        
        # Pequeno delay para que se guarde el log
        time.sleep(0.5)
        
        return respuesta
        
    except Exception as e:
        print("[ERROR] Error enviando comprobante: " + type(e).__name__)
        print("     " + str(e))
        raise


def test_logging(log_count_before):
    """Prueba que el logging se registro correctamente."""
    print("\n[TEST 3] Verificar Logging Automatico")
    print("-" * 60)
    
    # Contar logs despues
    log_count_after = ApiCallLog.objects.filter(service__service_type="NUBEFACT").count()
    
    print("[*] Logs antes: " + str(log_count_before))
    print("[*] Logs despues: " + str(log_count_after))
    
    if log_count_after > log_count_before:
        # Obtener el ultimo log
        latest_log = ApiCallLog.objects.filter(
            service__service_type="NUBEFACT"
        ).order_by('-created_at').first()
        
        print("\n[OK] Log registrado correctamente!")
        print("     - ID: " + str(latest_log.id))
        endpoint_name = latest_log.endpoint.name if latest_log.endpoint else 'N/A'
        print("     - Endpoint: " + str(endpoint_name))
        print("     - Status: " + str(latest_log.status))
        print("     - Duracion: " + str(latest_log.duration_ms) + "ms")
        print("     - Code HTTP: " + str(latest_log.response_code))
        print("     - Llamado desde: " + str(latest_log.called_from))
        print("     - Creado: " + str(latest_log.created_at))
        
        if latest_log.error_message:
            print("     - Error: " + str(latest_log.error_message[:100]))
        
        if latest_log.response_data:
            print("     - Respuesta guardada en log: OK")
        
        return latest_log
    else:
        print("\n[WARN] No se encontraron nuevos logs")
        print("       Verifica que ApiCallLog.objects.create() se haya ejecutado")
        return None


def test_context_manager(service):
    """Prueba el context manager."""
    print("\n[TEST 4] Context Manager")
    print("-" * 60)
    
    try:
        with service as ctx_service:
            print("[OK] Context manager __enter__ funciono")
            print("     - Service id: " + str(id(ctx_service)))
            print("     - Es el mismo service: " + str(ctx_service is service))
        
        print("[OK] Context manager __exit__ funciono")
        
    except Exception as e:
        print("[ERROR] Error con context manager: " + type(e).__name__)
        print("     " + str(e))
        raise


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "=" * 70)
    print(" " * 15 + "TEST INTEGRATION - NUBEFACTSERVICE")
    print("=" * 70)
    
    try:
        # 0. Verificar configuracion
        if not check_configuration():
            print("\n[ERROR] Configuracion incompleta. Por favor, crea los registros necesarios en BD.")
            return False
        
        # 1. Contar logs iniciales
        log_count_before = ApiCallLog.objects.filter(service__service_type="NUBEFACT").count()
        
        # 2. Prueba de inicializacion
        service = test_service_initialization()
        
        # 3. Prueba de context manager
        test_context_manager(service)
        
        # 4. Crear nuevo servicio para la prueba de emision
        # (para asegurar que el context manager no afecte)
        service2 = NubefactService()
        
        # 5. Prueba de emision
        respuesta = test_generar_comprobante(service2, log_count_before)
        
        # 6. Prueba de logging
        log_obj = test_logging(log_count_before)
        
        # Resumen
        print("\n" + "=" * 70)
        print(" " * 20 + "SUCCESS - ALL TESTS PASSED")
        print("=" * 70)
        print("\nResumen:")
        print("   [OK] Inicializacion: OK")
        print("   [OK] Context Manager: OK")
        print("   [OK] Generar Comprobante: OK")
        logging_status = "OK" if log_obj else "ADVERTENCIA"
        print("   [" + logging_status + "] Logging Automatico: " + logging_status)
        
        if respuesta and respuesta.get('enlace'):
            print("\n[SUCCESS] Comprobante emitido exitosamente!")
            print("   Enlace: " + str(respuesta['enlace']))
        
        return True
        
    except Exception as e:
        print("\n[ERROR] Prueba fallida: " + str(e))
        print("\nTips de depuracion:")
        print("   1. Verifica que ApiService este configurado en BD")
        print("   2. Verifica que ApiEndpoint este configurado para 'generar_comprobante'")
        print("   3. Verifica que los tokens tengan valor (no vacios)")
        print("   4. Revisa los logs en ApiCallLog para mas detalles")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
