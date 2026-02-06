# test_invoice_service.py
import asyncio
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from billing.services.invoice_service import InvoiceService


async def test_invoice_flow():
    service = InvoiceService()

    # Datos mínimos para prueba
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
        "total_descuento": 100,
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
                "total": 1180.0,
                "codigo_producto_sunat": "81112101",
            },
            {
                "unidad_de_medida": "ZZ",
                "codigo": "TEST002",
                "descripcion": "OTRO SERVICIO DE PRUEBA",
                "cantidad": 1.0,
                "valor_unitario": 1000.0,
                "precio_unitario": 1180.0,
                "subtotal": 1000.0,
                "total": 1180.0,
                "codigo_producto_sunat": "81112101",
            },
            {
                "unidad_de_medida": "ZZ",
                "codigo": "TEST003",
                "descripcion": "OTRO SERVICIO DE PRUEBA",
                "cantidad": 1.0,
                "valor_unitario": 1000.0,
                "precio_unitario": 1180.0,
                "subtotal": 1000.0,
                "total": 1180.0,
                "codigo_producto_sunat": "81112101",
            },
            {
                "unidad_de_medida": "ZZ",
                "codigo": "TEST004",
                "descripcion": "OTRO SERVICIO DE PRUEBA",
                "cantidad": 1.0,
                "valor_unitario": 1000.0,
                "precio_unitario": 1180.0,
                "subtotal": 1000.0,
                "total": 1180.0,
                "codigo_producto_sunat": "81112101",
            },
            {
                "unidad_de_medida": "ZZ",
                "codigo": "TEST005",
                "descripcion": "OTRO SERVICIO DE PRUEBA",
                "cantidad": 1.0,
                "valor_unitario": 1000.0,
                "precio_unitario": 1180.0,
                "subtotal": 1000.0,
                "total": 1180.0,
                "codigo_producto_sunat": "81112101",
            },
        ],
    }

    print("📝 Probando flujo de facturación...")
    result = await service.create_invoice(
        test_data, generate_pdf=True, save_to_disk=False
    )

    if result["success"]:
        print("✅ Servicio funcionando correctamente")
        print(f"   PDF generado: {len(result.get('pdf_content', b''))} bytes")
    else:
        print(f"❌ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_invoice_flow())
