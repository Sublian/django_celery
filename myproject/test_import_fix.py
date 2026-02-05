# myproject/test_template_fix.py
#!/usr/bin/env python
"""
Test para verificar templates de factura
"""
import os
import sys
import django
from datetime import datetime

# Setup Django
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(project_dir))
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

try:
    django.setup()
    print("✅ Django setup successful")
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

from django.conf import settings
from django.template.loader import render_to_string, get_template
from django.template import TemplateDoesNotExist

print("\n" + "="*60)
print("TEMPLATES VERIFICATION")
print("="*60)

# Verificar templates en settings
print("\n[1/4] Checking PDF_TEMPLATES in settings...")
if hasattr(settings, 'PDF_TEMPLATES'):
    for key, template_path in settings.PDF_TEMPLATES.items():
        print(f"   📄 {key}: {template_path}")
else:
    print("   ❌ PDF_TEMPLATES not found in settings")
    # Crear default
    settings.PDF_TEMPLATES = {
        'invoice': 'billing/factura_electronica.html',
        'invoice_custom': 'billing/plantilla_personalizada.html',
    }

# Verificar si los templates existen
print("\n[2/4] Checking if templates exist...")
templates_to_check = [
    'billing/factura_electronica.html',
    'billing/plantilla_personalizada.html',
    'shared/utils/pdf/templates/base_pdf.html',
]

for template_path in templates_to_check:
    try:
        template = get_template(template_path)
        print(f"   ✅ {template_path} - FOUND")
        
        # Verificar que el template se puede renderizar
        test_context = {'test': 'data'}
        html = template.render(test_context)
        print(f"        Can render: {len(html)} chars")
        
    except TemplateDoesNotExist:
        print(f"   ❌ {template_path} - NOT FOUND")
        
        # Mostrar posibles ubicaciones
        from django.template.loader import get_template_loader
        loaders = []
        for loader in get_template_loader('django'):
            if hasattr(loader, 'get_dirs'):
                loaders.extend(loader.get_dirs())
        
        print(f"        Searching in: {loaders[:2]}...")
        
    except Exception as e:
        print(f"   ⚠️  {template_path} - ERROR: {e}")

# Verificar estructura de directorios
print("\n[3/4] Checking directory structure...")
base_dirs_to_check = [
    ('billing/templates/billing/', os.path.join(project_dir, 'billing/templates/billing')),
    ('shared/utils/pdf/templates/', os.path.join(project_dir, 'shared/utils/pdf/templates')),
]

for label, path in base_dirs_to_check:
    exists = os.path.exists(path)
    print(f"   {'✅' if exists else '❌'} {label}")
    
    if exists:
        # Mostrar archivos en el directorio
        files = [f for f in os.listdir(path) if f.endswith('.html')]
        if files:
            print(f"        Files: {', '.join(files[:5])}{'...' if len(files) > 5 else ''}")
        else:
            print(f"        No HTML files found")

# Test con datos reales
print("\n[4/4] Testing with real data...")
try:
    from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
    
    # Datos de prueba
    test_data = {
        'serie': 'F001',
        'numero': 100001,
        'cliente_denominacion': 'CLIENTE DE PRUEBA S.A.C.',
        'cliente_numero_de_documento': '20123456789',
        'cliente_direccion': 'AV. PRUEBA 123, LIMA',
        'fecha_de_emision': '2024-01-31',
        'fecha_de_vencimiento': '2024-02-28',
        'moneda': '1',
        'total_gravada': 1000.0,
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
        }]
    }
    
    # Probar con template específico
    print("   Testing with template from settings...")
    
    # Obtener template de settings
    template_name = settings.PDF_TEMPLATES.get('invoice', 'billing/factura_electronica.html')
    print(f"   Template name: {template_name}")
    
    # Crear generador
    generator = InvoicePDFGenerator(test_data, template_name=template_name)
    
    # Renderizar HTML
    html = generator.render_html()
    print(f"   ✅ HTML rendered: {len(html)} chars")
    
    # Generar PDF
    pdf_bytes = generator.generate_sync()
    print(f"   ✅ PDF generated: {len(pdf_bytes):,} bytes")
    
    # Guardar
    output_path = os.path.join(project_dir, 'test_fixed.pdf')
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"   ✅ PDF saved to: {output_path}")
    
except TemplateDoesNotExist as e:
    print(f"   ❌ Template error: {e}")
    print("\n💡 Create the missing template file:")
    print(f"   Create: billing/templates/billing/factura_electronica.html")
    
except ImportError as e:
    print(f"   ❌ Import error: {e}")
    
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()