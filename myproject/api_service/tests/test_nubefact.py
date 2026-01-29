# test_nubefact.py
import os
import sys
import django

# Agregar el directorio raíz del proyecto al path
# Esto permite importar desde 'api_service'
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# IMPORTACIÓN CORRECTA para tu estructura
# Desde la carpeta nubefact dentro de services
from api_service.services.nubefact.nubefact_service import NubefactService

# Si no tienes el archivo exceptions.py, comenta o elimina esta línea:
# from api_service.services.nubefact_service.exceptions import NubefactAPIError

# Tu JSON base (copiado de tu mensaje)
JSON_BASE = {
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',
    'serie': 'F001',
    'numero': 91430.,
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


def test_nubefact_emision():
    """Prueba la emisión de un comprobante en Nubefact."""
    print("🔧 Iniciando prueba de emisión Nubefact...")
    
    try:
        # 1. Crear instancia del servicio
        print("1. Creando servicio Nubefact...")
        servicio = NubefactService()
        
        # 2. Verificar configuración cargada
        print(f"   URL Base: {servicio.base_url}")
        print(f"   Token: {'*' * 10}{servicio.auth_token[-5:] if servicio.auth_token else 'NO TOKEN'}")
        
        # 3. Enviar comprobante
        print("\n2. Enviando comprobante a Nubefact...")
        respuesta = servicio.emitir_comprobante(JSON_BASE)
        
        # 4. Mostrar resultados
        print("\n✅ Comprobante enviado con éxito!")
        print(f"   Enlace: {respuesta.get('enlace', 'No disponible')}")
        print(f"   Estado SUNAT: {respuesta.get('aceptada_por_sunat', 'No especificado')}")
        print(f"   Descripción: {respuesta.get('sunat_description', 'Sin descripción')}")
        
        return respuesta
        
    except Exception as e:
        print(f"\n❌ Error durante la emisión:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        resultado = test_nubefact_emision()
        print("\n🎉 Prueba completada exitosamente!")
    except Exception as e:
        print(f"\n💥 Prueba falló: {e}")
        sys.exit(1)
        