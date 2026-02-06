# myproject/test_simple_pdf.py
#!/usr/bin/env python
"""
Test simplificado de generación de PDF
"""
import os
import sys

# Setup básico sin Django primero
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

print("=" * 60)
print("SIMPLE PDF GENERATION TEST")
print("=" * 60)

# Opción 1: Usar directamente xhtml2pdf sin Django templates
try:
    print("\n[1/3] Testing direct xhtml2pdf...")
    from xhtml2pdf import pisa
    from io import BytesIO

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial; }
            h1 { color: #333; }
        </style>
    </head>
    <body>
        <h1>Test PDF Directo</h1>
        <p>Este es un test sin usar Django templates.</p>
        <p>Fecha: 2024-01-31</p>
        <p>Cliente: TEST CLIENT</p>
        <table border="1" cellpadding="5">
            <tr><th>Item</th><th>Cantidad</th><th>Precio</th></tr>
            <tr><td>Producto 1</td><td>2</td><td>100.00</td></tr>
            <tr><td>Producto 2</td><td>1</td><td>200.00</td></tr>
        </table>
    </body>
    </html>
    """

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_content.encode("utf-8")), result)

    if not pdf.err:
        pdf_bytes = result.getvalue()
        print(f"✅ PDF generated directly: {len(pdf_bytes)} bytes")

        # Guardar
        output_path = os.path.join(project_dir, "test_direct.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"✅ Saved to: {output_path}")
    else:
        print(f"❌ Error generating PDF: {pdf.err}")

except ImportError as e:
    print(f"❌ xhtml2pdf not installed: {e}")

# Opción 2: Verificar templates manualmente
print("\n[2/3] Checking template files manually...")

template_paths = [
    os.path.join(project_dir, "billing/templates/billing/factura_electronica.html"),
    os.path.join(project_dir, "shared/utils/pdf/templates/base_pdf.html"),
]

for path in template_paths:
    if os.path.exists(path):
        print(f"✅ Template exists: {os.path.relpath(path, project_dir)}")

        # Leer primera línea
        with open(path, "r", encoding="utf-8") as f:
            first_lines = []
            for i in range(3):
                line = f.readline().strip()
                if line:
                    first_lines.append(line)

            # Verificar si extiende base_pdf
            for line in first_lines:
                if "base_pdf.html" in line:
                    print(f"   Extends: base_pdf.html")
                    break
    else:
        print(f"❌ Template missing: {os.path.relpath(path, project_dir)}")

# Opción 3: Probar con Django después de verificar settings
print("\n[3/3] Testing with Django...")
try:
    # Setup Django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    import django

    django.setup()
    print("✅ Django setup successful")

    # Verificar que puede encontrar templates
    from django.template.loader import get_template

    templates_to_find = [
        "billing/factura_electronica.html",
        "shared/utils/pdf/templates/base_pdf.html",
    ]

    for template_name in templates_to_find:
        try:
            template = get_template(template_name)
            print(f"✅ Template found by Django: {template_name}")
        except Exception as e:
            print(f"❌ Django cannot find: {template_name}")
            print(f"   Error: {e}")

            # Mostrar donde está buscando Django
            from django.template.engine import Engine

            engine = Engine.get_default()
            print(f"   Django is looking in:")
            for loader in engine.template_loaders:
                if hasattr(loader, "get_dirs"):
                    for dir_path in loader.get_dirs():
                        print(f"     - {dir_path}")

    # Si todo está bien, intentar generar PDF
    print("\n[4/3] Attempting to generate PDF with our generator...")
    try:
        from shared.utils.pdf.invoice_generator import InvoicePDFGenerator

        test_data = {
            "serie": "F001",
            "numero": 100001,
            "cliente_denominacion": "TEST CLIENT",
            "cliente_numero_de_documento": "12345678901",
            "cliente_direccion": "Test Address",
            "fecha_de_emision": "2024-01-31",
            "moneda": "1",
            "total_gravada": 1000.0,
            "total_igv": "180.00",
            "total": "1180.00",
            "items": [
                {
                    "descripcion": "Test Item",
                    "cantidad": 1,
                    "precio_unitario": 1180.0,
                    "total": 1180.0,
                }
            ],
        }

        # Usar template path directo
        template_path = "billing/factura_electronica.html"
        generator = InvoicePDFGenerator(test_data, template_name=template_path)

        # Probar render HTML primero
        html = generator.render_html()
        print(f"✅ HTML rendered: {len(html)} chars")

        # Generar PDF
        pdf_bytes = generator.generate_sync()
        print(f"✅ PDF generated: {len(pdf_bytes)} bytes")

        output_path = os.path.join(project_dir, "test_final.pdf")
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"✅ Saved to: {output_path}")

    except Exception as e:
        print(f"❌ Error in PDF generation: {e}")
        import traceback

        traceback.print_exc()

except Exception as e:
    print(f"❌ Django setup failed: {e}")
