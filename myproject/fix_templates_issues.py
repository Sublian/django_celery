# myproject/fix_templates_issues.py
#!/usr/bin/env python
"""
Script para corregir problemas comunes en templates de PDF
"""
import os
import re

project_dir = os.path.dirname(os.path.abspath(__file__))

print("="*60)
print("FIXING TEMPLATE ISSUES")
print("="*60)

# 1. Verificar encoding en base_pdf.html
base_pdf_path = os.path.join(project_dir, 'billing/templates/billing/base_pdf.html')
print("\n[1/4] Checking base_pdf.html encoding...")

with open(base_pdf_path, 'r', encoding='utf-8') as f:
    content = f.read()

encoding_fixes = [
    (r'<head>', '<head>\n    <meta charset="UTF-8">\n    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'),
    (r'<meta charset="UTF-8">\s*<meta charset="UTF-8">', '<meta charset="UTF-8">'),  # Remove duplicates
]

fixed_count = 0
for pattern, replacement in encoding_fixes:
    if re.search(pattern, content, re.IGNORECASE):
        content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
        fixed_count += 1

if fixed_count > 0:
    with open(base_pdf_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Fixed {fixed_count} encoding issues in base_pdf.html")
else:
    print("✅ Encoding already correct in base_pdf.html")

# 2. Verificar tablas en factura_electronica.html
factura_path = os.path.join(project_dir, 'billing/templates/billing/factura_electronica.html')
print("\n[2/4] Checking factura_electronica.html tables...")

with open(factura_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Verificar estructura de tabla
table_issues = []

# Verificar etiquetas table/tr/td cerradas
if content.count('<table') != content.count('</table>'):
    table_issues.append("Mismatched <table> tags")
if content.count('<tr') != content.count('</tr>'):
    table_issues.append("Mismatched <tr> tags")
if content.count('<td') != content.count('</td>') and content.count('<th') != content.count('</th>'):
    table_issues.append("Mismatched <td>/<th> tags")

if table_issues:
    print(f"⚠️  Table issues found: {table_issues}")
    
    # Corregir tabla común
    table_fixes = [
        # Asegurar que las tablas tengan estructura correcta
        (r'<table>([^<]*)</table>', r'<table>\n<tbody>\n\1\n</tbody>\n</table>'),
        (r'<table([^>]*)>([^<]*)</table>', r'<table\1>\n<tbody>\n\2\n</tbody>\n</table>'),
    ]
    
    for pattern, replacement in table_fixes:
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            print(f"✅ Applied table fix: {pattern[:50]}...")
    
    with open(factura_path, 'w', encoding='utf-8') as f:
        f.write(content)
else:
    print("✅ Table structure looks good")

# 3. Verificar que no haya HTML mal formado
print("\n[3/4] Checking for malformed HTML...")

malformed_patterns = [
    r'<table[^>]*>\s*</table>',  # Tablas vacías
    r'<td[^>]*>\s*</td>',        # Celdas vacías
    r'<tr[^>]*>\s*</tr>',        # Filas vacías
]

for pattern in malformed_patterns:
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        print(f"⚠️  Found {len(matches)} malformed: {pattern[:30]}...")
        for match in matches[:3]:
            print(f"   - {match[:50]}...")

# 4. Agregar estilos CSS para tablas
print("\n[4/4] Adding CSS for better table rendering...")

css_to_add = '''
/* Mejoras para tablas en PDF */
table.items-table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    font-size: 10pt;
}

table.items-table th {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    padding: 6px 8px;
    text-align: center;
    font-weight: bold;
}

table.items-table td {
    border: 1px solid #dee2e6;
    padding: 6px 8px;
    vertical-align: top;
}

table.items-table .text-left {
    text-align: left;
}

table.items-table .text-right {
    text-align: right;
}

table.items-table .text-center {
    text-align: center;
}

/* Evitar que las tablas se rompan entre páginas */
table.items-table {
    page-break-inside: avoid;
}

table.items-table tr {
    page-break-inside: avoid;
    page-break-after: auto;
}
'''

# Agregar CSS al template base
with open(base_pdf_path, 'r', encoding='utf-8') as f:
    base_content = f.read()

if 'table.items-table' not in base_content:
    # Buscar donde agregar el CSS
    if '<style>' in base_content:
        # Agregar después del tag <style>
        base_content = base_content.replace('<style>', f'<style>\n{css_to_add}')
        print("✅ Added table CSS to base_pdf.html")
    elif '</head>' in base_content:
        # Agregar antes de </head>
        base_content = base_content.replace('</head>', f'<style>{css_to_add}</style>\n</head>')
        print("✅ Added table CSS to head")
    
    with open(base_pdf_path, 'w', encoding='utf-8') as f:
        f.write(base_content)

print("\n" + "="*60)
print("CREATING OPTIMIZED TEMPLATE")
print("="*60)

# Crear una versión optimizada del template
optimized_template = '''{% extends "billing/base_pdf.html" %}

{% block title %}Factura Electrónica {{ serie_numero }}{% endblock %}

{% block extra_css %}
<style>
    /* Estilos específicos para facturas */
    .invoice-header {
        text-align: center;
        margin-bottom: 20px;
        border-bottom: 2px solid #333;
        padding-bottom: 15px;
    }
    
    .invoice-number {
        font-size: 18px;
        font-weight: bold;
        color: #2c3e50;
        margin: 10px 0;
    }
    
    .client-info {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 20px;
        border-left: 4px solid #3498db;
    }
    
    .items-table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 11px;
    }
    
    .items-table th {
        background-color: #2c3e50;
        color: white;
        padding: 8px 10px;
        text-align: center;
        border: 1px solid #34495e;
    }
    
    .items-table td {
        padding: 8px 10px;
        border: 1px solid #ddd;
        vertical-align: top;
    }
    
    .text-left { text-align: left; }
    .text-right { text-align: right; }
    .text-center { text-align: center; }
    
    .totals {
        float: right;
        width: 300px;
        margin-top: 20px;
    }
    
    .total-row {
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
        border-bottom: 1px solid #eee;
    }
    
    .total-final {
        font-weight: bold;
        font-size: 14px;
        border-top: 2px solid #333;
        margin-top: 10px;
        padding-top: 10px;
    }
    
    .qr-section {
        text-align: center;
        margin-top: 30px;
        padding-top: 20px;
        border-top: 1px solid #eee;
    }
    
    .observation {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 10px;
        margin: 15px 0;
        font-size: 12px;
    }
</style>
{% endblock %}

{% block content %}
<div class="invoice-header">
    <h1>FACTURA ELECTRÓNICA</h1>
    <div class="invoice-number">{{ serie_numero }}</div>
    <div>
        <strong>Fecha Emisión:</strong> {{ fecha_emision }}
        {% if fecha_vencimiento %}
        | <strong>Fecha Vencimiento:</strong> {{ fecha_vencimiento }}
        {% endif %}
    </div>
</div>

<div class="client-info">
    <h3>INFORMACIÓN DEL CLIENTE</h3>
    <p><strong>Razón Social:</strong> {{ cliente }}</p>
    <p><strong>RUC:</strong> {{ ruc_cliente }}</p>
    <p><strong>Dirección:</strong> {{ direccion_cliente }}</p>
    {% if condiciones_pago %}
    <p><strong>Condiciones de Pago:</strong> {{ condiciones_pago }}</p>
    {% endif %}
</div>

<h4>DETALLE DE PRODUCTOS/SERVICIOS</h4>
<table class="items-table">
    <thead>
        <tr>
            <th width="8%">Cant.</th>
            <th width="10%">Unidad</th>
            <th width="12%">Código</th>
            <th width="35%" class="text-left">Descripción</th>
            <th width="10%" class="text-right">V. Unit.</th>
            <th width="10%" class="text-right">P. Unit.</th>
            <th width="15%" class="text-right">Valor Venta</th>
        </tr>
    </thead>
    <tbody>
        {% for item in items %}
        <tr>
            <td class="text-center">{{ item.cantidad|floatformat:2 }}</td>
            <td class="text-center">{{ item.unidad_de_medida }}</td>
            <td class="text-center">{{ item.codigo }}</td>
            <td class="text-left">
                {{ item.descripcion|linebreaksbr }}
                {% if item.codigo_producto_sunat %}
                <br><small>Cód. SUNAT: {{ item.codigo_producto_sunat }}</small>
                {% endif %}
            </td>
            <td class="text-right">S/ {{ item.valor_unitario|floatformat:2 }}</td>
            <td class="text-right">S/ {{ item.precio_unitario|floatformat:2 }}</td>
            <td class="text-right">S/ {{ item.subtotal|floatformat:2 }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<div class="totals">
    <div class="total-row">
        <span>Op. Gravadas:</span>
        <span>S/ {{ totales.gravada }}</span>
    </div>
    <div class="total-row">
        <span>Op. Inafectas:</span>
        <span>S/ {{ total_inafecta|default:"0.00" }}</span>
    </div>
    <div class="total-row">
        <span>Op. Exoneradas:</span>
        <span>S/ {{ total_exonerada|default:"0.00" }}</span>
    </div>
    <div class="total-row">
        <span>Op. Gratuitas:</span>
        <span>S/ {{ total_gratuita|default:"0.00" }}</span>
    </div>
    <div class="total-row">
        <span>Descuentos:</span>
        <span>S/ {{ total_descuento|default:"0.00" }}</span>
    </div>
    <div class="total-row">
        <span>IGV (18%):</span>
        <span>S/ {{ totales.igv }}</span>
    </div>
    <div class="total-row total-final">
        <span>IMPORTE TOTAL:</span>
        <span>S/ {{ totales.total }}</span>
    </div>
</div>

<div style="clear: both;"></div>

{% if observaciones %}
<div class="observation">
    <strong>Observaciones:</strong><br>
    {{ observaciones|linebreaksbr }}
</div>
{% endif %}

{% if venta_al_credito %}
<div style="margin: 15px 0; padding: 10px; background-color: #f1f8e9; border-radius: 4px;">
    <strong>Condiciones de Crédito:</strong>
    <ul style="margin: 5px 0 0 20px;">
        {% for cuota in venta_al_credito %}
        <li>Cuota {{ cuota.cuota }}: S/ {{ cuota.importe|floatformat:2 }} - Fecha: {{ cuota.fecha_de_pago }}</li>
        {% endfor %}
    </ul>
</div>
{% endif %}

{% if qr_data %}
<div class="qr-section">
    <h4>REPRESENTACIÓN IMPRESA DE COMPROBANTE ELECTRÓNICO</h4>
    <div style="margin: 15px 0; padding: 10px; background-color: #f8f9fa; display: inline-block; border: 1px solid #dee2e6;">
        <strong>CÓDIGO QR</strong><br>
        <div style="width: 100px; height: 100px; background-color: #e9ecef; margin: 10px auto; display: flex; align-items: center; justify-content: center;">
            QR
        </div>
        <small>Datos: {{ qr_data|truncatechars:50 }}</small>
    </div>
    <p>
        <strong>Código Hash:</strong> {{ codigo_unico|default:"Generado por SUNAT" }}<br>
        <strong>Fecha de emisión:</strong> {{ fecha_emision }}
    </p>
</div>
{% endif %}

<div style="margin-top: 30px; padding: 10px; background-color: #f8f9fa; border-radius: 4px; font-size: 10px; text-align: justify;">
    <strong>LEYENDA:</strong> Esta factura electrónica ha sido generada y autorizada conforme a la Ley N° 28035, Ley de Firmas y Certificados Digitales, y a la Resolución de Superintendencia N° 007-2006/SUNAT. Representación impresa del comprobante de pago electrónico. Para consultar la validez del comprobante, ingresar a https://www.sunat.gob.pe/ o escanear el código QR.
</div>
{% endblock %}
'''

# Guardar template optimizado
optimized_path = os.path.join(project_dir, 'billing/templates/billing/factura_optimizada.html')
with open(optimized_path, 'w', encoding='utf-8') as f:
    f.write(optimized_template)

print(f"✅ Created optimized template: {optimized_path}")

print("\n" + "="*60)
print("TEST THE FIXED TEMPLATE")
print("="*60)

test_code = '''
import os
import sys
import django
from datetime import datetime

project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

django.setup()

from shared.utils.pdf.invoice_generator import InvoicePDFGenerator

# Datos de prueba
test_data = {
    'serie': 'F001',
    'numero': 100002,
    'cliente_denominacion': 'EMPRESA DE PRUEBA OPTIMIZADA S.A.C.',
    'cliente_numero_de_documento': '20123456789',
    'cliente_direccion': 'AV. OPTIMIZADA 456, LIMA',
    'fecha_de_emision': datetime.now().strftime('%%Y-%%m-%%d'),
    'fecha_de_vencimiento': (datetime.now().replace(day=28)).strftime('%%Y-%%m-%%d'),
    'moneda': '1',
    'total_gravada': 847.46,
    'total_igv': '152.54',
    'total': '1000.00',
    'observaciones': 'Factura optimizada\\nSegunda línea de observaciones',
    'condiciones_de_pago': 'CREDITO',
    'venta_al_credito': [
        {'cuota': 1, 'fecha_de_pago': '2024-02-05', 'importe': 500.00},
        {'cuota': 2, 'fecha_de_pago': '2024-02-20', 'importe': 500.00}
    ],
    'items': [{
        'unidad_de_medida': 'ZZ',
        'codigo': 'SERV-001',
        'descripcion': 'SERVICIO DE CONSULTORÍA IT\\nAsesoría técnica especializada',
        'cantidad': 10.0,
        'valor_unitario': 84.746,
        'precio_unitario': 100.0,
        'subtotal': 847.46,
        'total': 1000.00,
        'codigo_producto_sunat': '81112105'
    }]
}

print("Testing with optimized template...")
generator = InvoicePDFGenerator(test_data, template_name='billing/factura_optimizada.html')

try:
    html = generator.render_html()
    print(f"✅ HTML rendered: {len(html)} chars")
    
    # Verificar que no haya tags mal cerrados
    if html.count('<table') == html.count('</table>'):
        print("✅ Tables properly closed")
    else:
        print(f"⚠️  Table tag mismatch: {html.count('<table')} opening, {html.count('</table>')} closing")
    
    pdf_bytes = generator.generate_sync()
    print(f"✅ PDF generated: {len(pdf_bytes):,} bytes")
    
    output_path = os.path.join(project_dir, 'test_optimized.pdf')
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"✅ Saved to: {output_path}")
    
    # Verificar encoding
    if b'%PDF' in pdf_bytes[:10]:
        print("✅ Valid PDF header")
    else:
        print("⚠️  Invalid PDF header")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
'''

test_path = os.path.join(project_dir, 'test_optimized.py')
with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_code)

print(f"\n📄 Created test script: {test_path}")
print("Running test...")
print("-"*40)

os.system(f'python {test_path}')

# Limpiar
os.remove(test_path)
print(f"\n✅ Cleaned up test script")

print("\n" + "="*60)
print("NEXT STEPS")
print("="*60)
print("1. Check the generated PDF: test_optimized.pdf")
print("2. If it looks good, update your main template")
print("3. Or use the optimized template by default")