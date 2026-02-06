# myproject/test_simple.py
#!/usr/bin/env python
"""
Simple Test - Verifica configuración básica
"""
import os
import sys
import time
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
        from billing.services.invoice_service import InvoiceService

        print("✅ billing.services import successful")
    except ImportError as e:
        print(f"❌ billing.services import failed: {e}")

except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

# 4. Probar generación de PDF simple
print("\n" + "=" * 60)
print("TEST SENDING JSON + PDF GENERATION")
print("=" * 60)

try:
    from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
    from api_service.services.nubefact.nubefact_service import NubefactService
    from api_service.models import ApiCallLog
    
    print("🔧 Iniciando prueba de emisión Nubefact...")

    # Contar logs antes de la prueba
    initial_log_count = ApiCallLog.objects.filter(
        service__service_type="NUBEFACT"
    ).count()
    print(f"   Logs existentes antes: {initial_log_count}")
    
    # Datos de prueba mínimos
    test_data = {
        "serie": "F001",
        "numero": 91508,
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": "1",
        "sunat_transaction": 30,
        "cliente_tipo_de_documento": "6",
        "cliente_numero_de_documento": "20343443961",
        "cliente_denominacion": "UNNA TRANSPORTE S.A.C.",
        "cliente_direccion": "AV. PETIT THOUARS NRO 4957",
        "cliente_email": "",
        "cliente_email_1": "",
        "cliente_email_2": "",
        "fecha_de_emision": "2026-02-06",
        "fecha_de_vencimiento": "2026-02-28",
        "moneda": "1",
        "tipo_de_cambio": "",
        "porcentaje_de_igv": 18.0,
        "descuento_global": "",
        "orden_compra_servicio": "OC 10000018442",
        "total_descuento": 0.0,
        "total_anticipo": 0,
        "total_gravada": 1440.0,
        "total_inafecta": 0,
        "total_exonerada": 0,
        "total_igv": "259.20",
        "total_gratuita": 0,
        "total_otros_cargos": "",
        "total_impuestos_bolsas": 0,
        "total": "1699.20",
        "percepcion_tipo": "",
        "percepcion_base_imponible": "",
        "total_percepcion": "",
        "total_incluido_percepcion": "",
        "detraccion": "true",
        "detraccion_tipo": 35,
        "detraccion_total": 204.0,
        "detraccion_porcentaje": 12.0,
        "medio_de_pago_detraccion": "003",
        "observaciones": "Pedido: SUB51946\nEsta factura cubre el siguiente periodo: 01/09/2025 - 30/09/2025",
        "documento_que_se_modifica_tipo": "",
        "documento_que_se_modifica_serie": "",
        "documento_que_se_modifica_numero": "",
        "tipo_de_nota_de_credito": "",
        "tipo_de_nota_de_debito": "",
        "enviar_automaticamente_a_la_sunat": "false",
        "enviar_automaticamente_al_cliente": "false",
        "codigo_unico": "",
        "condiciones_de_pago": "CREDITO",
        "medio_de_pago": "credito",
        "placa_vehiculo": "",
        "tabla_personalizada_codigo": "",
        "formato_de_pdf": "",
        "venta_al_credito": [
            {"cuota": 1, "fecha_de_pago": "2026-02-28", "importe": 1495.2}
        ],
        "items": [
            {
                "unidad_de_medida": "ZZ",
                "codigo": "S00137",
                "descripcion": "[S00137] Internet Dedicado",
                "cantidad": 80.0,
                "valor_unitario": 18.0,
                "precio_unitario": 21.24,
                "descuento": 0.0,
                "subtotal": 1440.0,
                "tipo_de_igv": "1",
                "igv": 259.2,
                "impuesto_bolsas": 0,
                "total": 1699.2,
                "anticipo_regularizacion": "false",
                "anticipo_documento_serie": "",
                "anticipo_documento_numero": "",
                "codigo_producto_sunat": "81112101",
            }
        ],
    }

    # Crear instancia del servicio
    print("1. Creando servicio Nubefact...")
    servicio = NubefactService()
    
    # Verificar configuración cargada
    print(f"   URL Base: {servicio.base_url}")
    print(
        f"   Token: {'*' * 10}{servicio.auth_token[-5:] if servicio.auth_token else 'NO TOKEN'}"
    )
    
    # 3. Enviar comprobante
    print("\n2. Enviando comprobante a Nubefact...")
    respuesta = servicio.generar_comprobante(test_data)
    # Esperar un momento para que se complete el logging
    time.sleep(0.5)
    
    # Verificar logs creados
    new_logs = ApiCallLog.objects.filter(service__service_type="NUBEFACT").order_by(
        "-created_at"
    )
    logs_count = new_logs.count()
    print(f"\n📊 Logs después de la llamada: {logs_count}")
    
    if logs_count > initial_log_count:
        latest_log = new_logs.first()
        print("✅ Log registrado correctamente!")
        print(
            f"   Endpoint: {latest_log.endpoint.name if latest_log.endpoint else 'N/A'}"
        )
        print(f"   Status: {latest_log.status}")
        print(f"   Duración: {latest_log.duration_ms}ms")
        print(f"   Creado: {latest_log.created_at}")

        # Mostrar respuesta guardada en el log
        if latest_log.response_data:
            print(f"   Respuesta en log:")
            print(f"     - Enlace: {latest_log.response_data.get('enlace', 'N/A')}")
            print(
                f"     - Estado SUNAT: {latest_log.response_data.get('aceptada_por_sunat', 'N/A')}"
            )
    else:
        print(
            "⚠️  No se encontraron nuevos logs. Verifica que el modelo ApiCallLog exista."
        )
        
     # Mostrar respuesta directa
    print(f"\n📨 Respuesta directa de Nubefact:")
    print(f"   Enlace: {respuesta.get('enlace', 'No disponible')}")
    print(
        f"   Estado SUNAT: {respuesta.get('aceptada_por_sunat', 'No especificado')}"
    )
    
    # Generar PDF
    generator = InvoicePDFGenerator(test_data)
    pdf_bytes = generator.generate_sync()

    print(f"✅ PDF generated successfully")
    print(f"   Size: {len(pdf_bytes)} bytes")

    # Guardar para verificar    
    filename = f"{test_data.get('serie', 'N/A')}{test_data.get('numero', 'N/A')}.pdf"
    test_pdf_path = os.path.join(project_dir, f"myproject\\file_store\\billing\\invoices\\2026\\02\\{filename}")
    with open(test_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF saved to: {test_pdf_path}")

except Exception as e:
    print(f"❌ PDF generation failed: {e}")
    import traceback

    traceback.print_exc()
