# myproject/test_factura_completo.py
#!/usr/bin/env python
"""
Test completo de generación de factura con PDF
"""
import os
import sys
import django
from datetime import datetime

# ================= CONFIGURACIÓN =================
# Determinar rutas correctamente
if __name__ == "__main__":
    # Si ejecutamos desde myproject/
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Si el script está en myproject/ y shared está en myproject/shared/
    PROJECT_ROOT = CURRENT_DIR
    
    # Agregar al path
    sys.path.insert(0, PROJECT_ROOT)
    sys.path.insert(0, os.path.dirname(PROJECT_ROOT))  # django_fx si existe
    print(f"📁 Current directory: {CURRENT_DIR}")
    print(f"📁 Project root: {PROJECT_ROOT}")
    
    # Verificar estructura
    print("\n📂 Verifying directory structure:")
    check_paths = [
        ('shared/', os.path.join(PROJECT_ROOT, 'shared')),
        ('shared/utils/pdf/', os.path.join(PROJECT_ROOT, 'shared/utils/pdf')),
        ('billing/', os.path.join(PROJECT_ROOT, 'billing')),
    ]
    
    for label, path in check_paths:
        exists = os.path.exists(path)
        print(f"   {'✅' if exists else '❌'} {label} -> {exists}")

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    django.setup()
    print("\n✅ Django setup successful")
    
    # Verificar settings
    from django.conf import settings
    print(f"✅ Settings module: {settings.SETTINGS_MODULE}")
    
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# ================= DATOS DE PRUEBA =================
test_invoice_data = {
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',
    'serie': 'F001',
    'numero': 100001,
    'fecha_de_emision': datetime.now().strftime('%d/%m/%Y'),
    'fecha_de_vencimiento': (datetime.now().replace(day=28)).strftime('%d/%m/%Y'),
    'sunat_transaction': 1,
    'cliente_tipo_de_documento': '6',
    'cliente_numero_de_documento': '20343443961',
    'cliente_denominacion': 'EMPRESA DE PRUEBA S.A.C.',
    'cliente_direccion': 'AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO',
    'cliente_email': 'cliente@ejemplo.com',
    'moneda': '1',
    'tipo_de_cambio': '',
    'porcentaje_de_igv': 18.0,
    'descuento_global': 100.00,
    'orden_compra_servicio': 'OC-2024-001',
    'total_descuento': 100,
    'total_anticipo': 0,
    'total_gravada': 847.46,
    'total_inafecta': 0,
    'total_exonerada': 0,
    'total_igv': '152.54',
    'total_gratuita': 0,
    'total_otros_cargos': '',
    'total_impuestos_bolsas': 0,
    'total': '1000.00',
    'percepcion_tipo': '',
    'percepcion_base_imponible': '',
    'total_percepcion': '',
    'total_incluido_percepcion': '',
    'detraccion': 'false',
    'detraccion_tipo': '',
    'detraccion_total': 0,
    'detraccion_porcentaje': 0,
    'medio_de_pago_detraccion': '',
    'observaciones': 'Pedido: TEST-2024-001\nEsta factura cubre servicios del mes de Enero 2024',
    'documento_que_se_modifica_tipo': '',
    'documento_que_se_modifica_serie': '',
    'documento_que_se_modifica_numero': '',
    'tipo_de_nota_de_credito': '',
    'tipo_de_nota_de_debito': '',
    'enviar_automaticamente_a_la_sunat': 'false',
    'enviar_automaticamente_al_cliente': 'false',
    'codigo_unico': 'TEST-HASH-123456',
    'condiciones_de_pago': 'CREDITO',
    'medio_de_pago': 'credito',
    'placa_vehiculo': '',
    'tabla_personalizada_codigo': '',
    'formato_de_pdf': '',
    'venta_al_credito': [
        {'cuota': 1, 'fecha_de_pago': (datetime.now().replace(day=5)).strftime('%Y-%m-%d'), 'importe': 500.00},
        {'cuota': 2, 'fecha_de_pago': (datetime.now().replace(day=20)).strftime('%Y-%m-%d'), 'importe': 500.00}
    ],
    'items': [
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        }
        ,
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        }
        ,{
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'SERV-001',
            'descripcion': 'SERVICIO DE CONSULTORÍA IT\nAsesoría técnica especializada en desarrollo de software',
            'cantidad': 10.0,
            'valor_unitario': 84.746,
            'precio_unitario': 100.0,
            'descuento': 100.0,
            'subtotal': 847.46,
            'tipo_de_igv': '1',
            'igv': 152.54,
            'impuesto_bolsas': 0,
            'total': 1000.00,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112105'
        }
        
    ]
}

# ================= PRUEBA PRINCIPAL =================
def main():
    print("\n" + "="*70)
    print("COMPLETE INVOICE PDF GENERATION TEST")
    print("="*70)
    
    try:
        # 1. Importar generador
        print("\n[1/6] Importing InvoicePDFGenerator...")
        from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
        print("   ✅ Import successful")
        
        # 2. Crear instancia
        print("\n[2/6] Creating generator instance...")
        generator = InvoicePDFGenerator(test_invoice_data)
        print("   ✅ Generator instance created")
        
        # 3. Obtener contexto
        print("\n[3/6] Getting template context...")
        context = generator.get_template_context()
        print(f"   ✅ Context generated")
        print(f"   - Serie/Número: {context.get('serie_numero')}")
        print(f"   - Cliente: {context.get('cliente')[:30]}...")
        print(f"   - Total: {context.get('totales', {}).get('total')}")
        
        # 4. Verificar company info
        print("\n[4/6] Checking company info...")
        company_info = context.get('company_info', {})
        if company_info:
            print(f"   ✅ Company info found")
            print(f"   - Nombre: {company_info.get('nombre')}")
            print(f"   - RUC: {company_info.get('ruc')}")
        else:
            print("   ⚠️  No company info in context")
            print("   💡 Check settings.py for COMPANY_* variables")
        
        # 5. Generar PDF
        print("\n[5/6] Generating PDF (sync)...")
        pdf_bytes = generator.generate_sync()
        print(f"   ✅ PDF generated - Size: {len(pdf_bytes):,} bytes")
        
        # 6. Guardar y verificar
        print("\n[6/6] Saving PDF file...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"factura_test_{timestamp}.pdf"
        output_path = os.path.join(PROJECT_ROOT, output_filename)
        
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"   ✅ PDF saved to: {output_filename}")
        
        # Verificación adicional
        print("\n" + "-"*70)
        print("VERIFICATION")
        print("-"*70)
        
        if len(pdf_bytes) > 5000:  # PDFs legítimos son > 5KB
            print(f"✅ PDF size OK (> 5KB)")
        else:
            print(f"⚠️  PDF size suspiciously small: {len(pdf_bytes)} bytes")
        
        # Intentar abrir el PDF (verificación básica)
        if pdf_bytes.startswith(b'%PDF'):
            print("✅ PDF header valid (%PDF)")
        else:
            print("⚠️  PDF header not found")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        
        return True
        
    except AttributeError as e:
        print(f"\n❌ AttributeError: {e}")
        print("\n💡 Most likely missing settings in settings.py")
        print("   Add these to your settings.py:")
        print("   COMPANY_NAME = 'Tu Empresa S.A.C.'")
        print("   COMPANY_RUC = '20123456789'")
        print("   COMPANY_ADDRESS = 'Tu Dirección'")
        print("   ...")
        return False
        
    except ImportError as e:
        print(f"\n❌ ImportError: {e}")
        print("\n💡 Check that:")
        print("   1. shared/utils/pdf/__init__.py exists")
        print("   2. invoice_generator.py imports with '.' (relative)")
        print("   3. Project structure is correct")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    
    # Mostrar ayuda adicional si falla
    if not success:
        print("\n" + "="*70)
        print("TROUBLESHOOTING GUIDE")
        print("="*70)
        print("1. Check settings.py has COMPANY_* variables")
        print("2. Ensure all __init__.py files exist:")
        print("   - myproject/shared/__init__.py")
        print("   - myproject/shared/utils/__init__.py")
        print("   - myproject/shared/utils/pdf/__init__.py")
        print("3. Verify import in invoice_generator.py:")
        print("   from .base_generator import BasePDFGenerator")
        print("4. Check Django is properly setup:")
        print("   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')")
        print("   django.setup()")