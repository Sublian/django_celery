# myproject/create_templates.py
#!/usr/bin/env python
"""
Script para crear templates básicos si no existen
"""
import os
import sys

# Determinar rutas
project_dir = os.path.dirname(os.path.abspath(__file__))

# Template básico para factura
factura_template = """{% extends "shared/utils/pdf/templates/base_pdf.html" %}

{% block title %}Factura Electrónica {{ serie_numero }}{% endblock %}

{% block document_header %}
<h2 style="margin: 0; color: #2980b9;">FACTURA ELECTRÓNICA</h2>
<p style="margin: 0.2cm 0; font-size: 10pt; font-weight: bold;">
    {{ serie_numero }}
</p>
<p style="margin: 0; font-size: 9pt;">
    Fecha Emisión: {{ fecha_emision }}
</p>
{% endblock %}

{% block content %}
<div style="text-align: center; margin-bottom: 1cm;">
    <h1>FACTURA ELECTRÓNICA</h1>
    <h2>{{ serie_numero }}</h2>
</div>

<div style="background: #f8f9fa; padding: 0.5cm; border-radius: 5px; margin-bottom: 1cm;">
    <h3>INFORMACIÓN DEL CLIENTE</h3>
    <p><strong>Razón Social:</strong> {{ cliente }}</p>
    <p><strong>RUC:</strong> {{ ruc_cliente }}</p>
    <p><strong>Dirección:</strong> {{ direccion_cliente }}</p>
</div>

<div style="margin-bottom: 1cm;">
    <h3>DETALLE</h3>
    <table style="width: 100%; border-collapse: collapse;">
        <thead>
            <tr style="background: #e9ecef;">
                <th style="border: 1px solid #dee2e6; padding: 0.3cm;">Descripción</th>
                <th style="border: 1px solid #dee2e6; padding: 0.3cm;">Cantidad</th>
                <th style="border: 1px solid #dee2e6; padding: 0.3cm;">P. Unitario</th>
                <th style="border: 1px solid #dee2e6; padding: 0.3cm;">Total</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td style="border: 1px solid #dee2e6; padding: 0.3cm;">{{ item.descripcion }}</td>
                <td style="border: 1px solid #dee2e6; padding: 0.3cm; text-align: center;">{{ item.cantidad }}</td>
                <td style="border: 1px solid #dee2e6; padding: 0.3cm; text-align: right;">S/ {{ item.precio_unitario }}</td>
                <td style="border: 1px solid #dee2e6; padding: 0.3cm; text-align: right;">S/ {{ item.total }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<div style="float: right; width: 40%;">
    <div style="border-top: 2px solid #000; padding-top: 0.5cm;">
        <div style="display: flex; justify-content: space-between;">
            <span>Subtotal:</span>
            <span>S/ {{ totales.gravada }}</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
            <span>IGV (18%):</span>
            <span>S/ {{ totales.igv }}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 1.1em;">
            <span>TOTAL:</span>
            <span>S/ {{ totales.total }}</span>
        </div>
    </div>
</div>

<div style="clear: both;"></div>

{% if observaciones %}
<div style="margin-top: 1cm; padding: 0.5cm; background: #fff3cd; border-radius: 5px;">
    <strong>Observaciones:</strong><br>
    {{ observaciones }}
</div>
{% endif %}

<div style="text-align: center; margin-top: 2cm;">
    <p>Documento generado electrónicamente</p>
</div>
{% endblock %}
"""

# Template básico personalizado
plantilla_personalizada = """{% extends "shared/utils/pdf/templates/base_pdf.html" %}

{% block title %}Factura {{ serie_numero }} - Personalizada{% endblock %}

{% block content %}
<div style="text-align: center; padding: 1cm; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px;">
    <h1 style="margin: 0;">FACTURA ELECTRÓNICA</h1>
    <h2 style="margin: 0.5cm 0;">{{ serie_numero }}</h2>
    <p>Fecha: {{ fecha_emision }}</p>
</div>

<div style="margin: 1cm 0;">
    <h3>📋 Detalles del Cliente</h3>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5cm;">
        <div><strong>Cliente:</strong> {{ cliente }}</div>
        <div><strong>RUC:</strong> {{ ruc_cliente }}</div>
        <div><strong>Dirección:</strong> {{ direccion_cliente }}</div>
        <div><strong>Condiciones:</strong> {{ condiciones_pago }}</div>
    </div>
</div>

<!-- Más contenido aquí -->
<div style="text-align: center; margin-top: 2cm;">
    <p>✨ Plantilla personalizada ✨</p>
</div>
{% endblock %}
"""

# Template base
base_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Documento PDF{% endblock %}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            font-size: 12pt;
            line-height: 1.4;
            color: #000;
            margin: 1cm;
        }
        .header {
            text-align: center;
            margin-bottom: 1cm;
            border-bottom: 2px solid #000;
            padding-bottom: 0.5cm;
        }
        .footer {
            text-align: center;
            margin-top: 1cm;
            border-top: 1px solid #ccc;
            padding-top: 0.5cm;
            font-size: 10pt;
            color: #666;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 0.5cm 0;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 0.3cm;
            text-align: left;
        }
        th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="header">
        {% block header %}
        <h1>{{ company_info.nombre|default:"MI EMPRESA" }}</h1>
        <p>RUC: {{ company_info.ruc|default:"00000000000" }}</p>
        {% endblock %}
    </div>
    
    <div class="content">
        {% block content %}
        <!-- Contenido principal aquí -->
        {% endblock %}
    </div>
    
    <div class="footer">
        {% block footer %}
        <p>Página <pdf:pagenumber> de <pdf:pagecount></p>
        <p>Generado el {% now "d/m/Y H:i" %}</p>
        {% endblock %}
    </div>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
"""

# Directorios a crear
directories = [
    os.path.join(project_dir, "billing/templates/billing"),
    os.path.join(project_dir, "shared/utils/pdf/templates"),
]

# Archivos a crear
files_to_create = [
    (
        os.path.join(project_dir, "billing/templates/billing/factura_electronica.html"),
        factura_template,
    ),
    (
        os.path.join(
            project_dir, "billing/templates/billing/plantilla_personalizada.html"
        ),
        plantilla_personalizada,
    ),
    (
        os.path.join(project_dir, "shared/utils/pdf/templates/base_pdf.html"),
        base_template,
    ),
]

print("=" * 60)
print("CREATING TEMPLATE FILES")
print("=" * 60)

# Crear directorios
for directory in directories:
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    else:
        print(f"📁 Directory exists: {directory}")

# Crear archivos
for file_path, content in files_to_create:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created file: {file_path}")
    else:
        print(f"📄 File exists: {file_path}")

print("\n" + "=" * 60)
print("TEMPLATES READY")
print("=" * 60)
print("Now run: python test_template_fix.py")
