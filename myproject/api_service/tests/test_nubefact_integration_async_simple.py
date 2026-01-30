"""
Prueba de integración REAL para NubefactServiceAsync (payload simplificado).
"""
import os
import sys
import django
import asyncio
import json
import time

# Configurar ruta y Django
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.join(current_dir, "..", "..")
sys.path.insert(0, project_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

try:
    django.setup()
except Exception as e:
    print(f"Error en Django setup: {e}")
    sys.exit(1)

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync


async def run_test():
    print("=" * 70)
    print("PRUEBA DE INTEGRACION ASYNC - NubefactServiceAsync")
    print("=" * 70)
    
    print("\n[INIT] Inicializando NubefactServiceAsync...")
    try:
        async with NubefactServiceAsync() as svc:
            print(f"[CONFIG] Base URL: {svc.base_url}")
            print(f"[CONFIG] Auth Token: {svc.auth_token[:20]}..." if svc.auth_token else "N/A")
            
            # Payload base (del sync test que funciona)
            payload = {
                'operacion': 'generar_comprobante',
                'tipo_de_comprobante': '1',
                'serie': 'F001',
                'numero': 91431,
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
                'observaciones': 'Async Service Test',
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
            
            print("\n[REQUEST] Enviando generar_comprobante async...")
            print(f"[PAYLOAD] Número: {payload['numero']}")
            print(f"[PAYLOAD] Total: {payload['total']}")
            
            start = time.time()
            try:
                response = await svc.generar_comprobante(payload)
                duration = time.time() - start
                
                print(f"\n[SUCCESS] Completado en {duration:.2f}s")
                print(f"[RESPONSE] Datos: {json.dumps(response, indent=2, default=str)[:800]}")
                
            except Exception as e:
                duration = time.time() - start
                print(f"\n[ERROR] Falló en {duration:.2f}s")
                print(f"[ERROR] {type(e).__name__}: {str(e)}")
    
    except Exception as e:
        print(f"[INIT_ERROR] {str(e)}")
        return
    
    print("\n" + "=" * 70)
    print("FIN PRUEBA DE INTEGRACION ASYNC")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_test())
