# myproject/test_simple.py
#!/usr/bin/env python
"""
Simple Test - Verifica configuración básica
"""
import os
import sys
import django

# Setup Django CORRECTO
# 1. Asegurar que estamos en el directorio correcto
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

# 2. Establecer settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

# 3. Configurar Django
try:
    django.setup()
    print("✅ Django setup successful")

    # Verificar algunas configuraciones
    from django.conf import settings

    print(f"✅ BASE_DIR: {settings.BASE_DIR}")
    print(f"✅ INSTALLED_APPS: {len(settings.INSTALLED_APPS)} apps")

    # Verificar si el módulo de billing existe
    try:
        from billing.services import InvoiceService

        print("✅ billing.services import successful")
    except ImportError as e:
        print(f"❌ billing.services import failed: {e}")

except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# 4. Probar generación de PDF simple
print("\n" + "=" * 60)
print("TEST PDF GENERATION")
print("=" * 60)

try:
    from shared.utils.pdf.invoice_generator import InvoicePDFGenerator

    # Datos de prueba mínimos
    test_data = {
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

    # Generar PDF
    generator = InvoicePDFGenerator(test_data)
    pdf_bytes = generator.generate_sync()

    print(f"✅ PDF generated successfully")
    print(f"   Size: {len(pdf_bytes)} bytes")

    # Guardar para verificar
    test_pdf_path = os.path.join(project_dir, "test_output.pdf")
    with open(test_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF saved to: {test_pdf_path}")

except Exception as e:
    print(f"❌ PDF generation failed: {e}")
    import traceback

    traceback.print_exc()
