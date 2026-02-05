# test_weasyprint.py
import os
import sys
import django

# 1. Configurar la ruta a la configuración de tu proyecto Django
#    Ajusta 'myproject.settings' al módulo correcto de tu settings.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# 2. Configurar Django (esto carga los settings)
django.setup()

# 3. AHORA puedes importar tus clases que dependen de settings
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator

# Datos de prueba similares a tu JSON de factura
test_data = {
        'serie': 'F001',
        'numero': 91501,
        'cliente_denominacion': 'CLIENTE DE PRUEBA S.A.C.',
        'cliente_numero_de_documento': '20123456789',
        'cliente_direccion': 'AV. PRUEBA 123, LIMA',
        'fecha_de_emision': '2024-01-31',
        'fecha_de_vencimiento': '2024-02-28',
        'moneda': '1',
        'total_gravada': 1000.0,
        'total_descuento': 100,
        'porcentaje_igv': 18.0,
        'total_igv': '180.00',
        'total': '1180.00',
        'observaciones': 'Factura de prueba',
        'condiciones_de_pago': 'CONTADO',
        'items': [{
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST001',
            'descripcion': 'SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST003',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST004',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST005',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        },
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'TEST002',
            'descripcion': 'OTRO SERVICIO DE PRUEBA',
            'cantidad': 1.0,
            'valor_unitario': 1000.0,
            'precio_unitario': 1180.0,
            'subtotal': 1000.0,
            'total': 1180.0,
            'codigo_producto_sunat': '81112101'
        }
                  ]
    }

generator = InvoicePDFGenerator(test_data)
pdf_bytes = generator.generate_sync()

with open("test_factura_weasyprint.pdf", "wb") as f:
    f.write(pdf_bytes)

print("✅ PDF generado con WeasyPrint. Verifica la paginación.")