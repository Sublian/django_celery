# myproject/quick_fix.py
#!/usr/bin/env python
"""
Solución inmediata al problema de templates
"""
import os
import shutil

project_dir = os.path.dirname(os.path.abspath(__file__))

print("="*60)
print("QUICK FIX FOR TEMPLATE ISSUE")
print("="*60)

# 1. Copiar base_pdf.html a billing/templates/billing/
source = os.path.join(project_dir, 'shared/utils/pdf/templates/base_pdf.html')
destination = os.path.join(project_dir, 'billing/templates/billing/base_pdf.html')

if os.path.exists(source):
    shutil.copy2(source, destination)
    print(f"✅ Copied: {source}")
    print(f"    To: {destination}")
else:
    print(f"❌ Source not found: {source}")
    
    # Crear un base_pdf.html básico
    basic_base = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Documento{% endblock %}</title>
    <style>
        body { font-family: Arial; margin: 2cm; }
        .header { text-align: center; border-bottom: 2px solid #000; margin-bottom: 1cm; }
        .footer { text-align: center; margin-top: 2cm; border-top: 1px solid #ccc; padding-top: 0.5cm; }
        table { width: 100%; border-collapse: collapse; margin: 1cm 0; }
        th, td { border: 1px solid #ddd; padding: 8px; }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <div class="header">
        {% block header %}
        <h1>{{ company_info.nombre|default:"Empresa" }}</h1>
        <p>RUC: {{ company_info.ruc|default:"00000000000" }}</p>
        {% endblock %}
    </div>
    
    <div class="content">
        {% block content %}
        {% endblock %}
    </div>
    
    <div class="footer">
        {% block footer %}
        <p>Página <pdf:pagenumber> de <pdf:pagecount></p>
        {% endblock %}
    </div>
</body>
</html>'''
    
    with open(destination, 'w', encoding='utf-8') as f:
        f.write(basic_base)
    print(f"✅ Created basic base_pdf.html at: {destination}")

# 2. Actualizar factura_electronica.html para usar la nueva ruta
factura_path = os.path.join(project_dir, 'billing/templates/billing/factura_electronica.html')
if os.path.exists(factura_path):
    with open(factura_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Reemplazar la ruta de extends
    old_extends = 'shared/utils/pdf/templates/base_pdf.html'
    new_extends = 'billing/base_pdf.html'
    
    if old_extends in content:
        content = content.replace(old_extends, new_extends)
        with open(factura_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Updated factura_electronica.html to use: {new_extends}")
    else:
        print(f"⚠️  factura_electronica.html doesn't extend {old_extends}")
        
        # Verificar qué está extendiendo
        import re
        match = re.search(r'\{% extends "([^"]+)"', content)
        if match:
            print(f"   Currently extends: {match.group(1)}")
            print(f"   Changing to: {new_extends}")
            content = re.sub(r'\{% extends "[^"]+"', f'{{% extends "{new_extends}" %}}', content)
            with open(factura_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated extends path")

print("\n" + "="*60)
print("TESTING THE FIX")
print("="*60)

# 3. Probar la solución
test_script = '''
import os
import sys
import django

project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

django.setup()

from django.template.loader import get_template

try:
    # Verificar que encuentra ambos templates
    t1 = get_template('billing/factura_electronica.html')
    print("✅ Found: billing/factura_electronica.html")
    
    t2 = get_template('billing/base_pdf.html')
    print("✅ Found: billing/base_pdf.html")
    
    # Probar que se pueden renderizar
    context = {
        'company_info': {'nombre': 'Test', 'ruc': '123'},
        'serie_numero': 'F001-00001',
        'cliente': 'Test Client',
        'items': [],
        'totales': {'total': '100.00'}
    }
    
    html = t1.render(context)
    print(f"✅ Template renders: {len(html)} chars")
    
except Exception as e:
    print(f"❌ Error: {e}")
'''

# Guardar y ejecutar test
test_path = os.path.join(project_dir, 'test_fix.py')
with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_script)

print(f"📄 Created test script: {test_path}")
print("\nRunning test...")
print("-"*40)

os.system(f'python {test_path}')

# Limpiar
os.remove(test_path)
print(f"\n✅ Cleaned up test script")

print("\n" + "="*60)
print("FINAL STEP: Test PDF generation")
print("="*60)
print("Run: python test_simple_pdf.py")