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
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": "1",
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
        "total": "5900.00",
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


    print(f"\n🔧 Datos de prueba:")
    print(f"   Serie-Número: {test_data['serie']}-{test_data['numero']}")
    print(f"   Cliente: {test_data['cliente_denominacion']}")
    print(f"   Monto: S/ {test_data['total']}")
    
    # Opción 1: Probar solo generación de PDF (sin NubeFact)
    print("\n" + "-" * 60)
    print("🔄 OPCIÓN 1: Generando solo PDF (sin NubeFact)")
    print("-" * 60)
    
    pdf_only = service.generate_pdf_only(test_data)
    if pdf_only:
        with open("test_factura_solo_pdf.pdf", "wb") as f:
            f.write(pdf_only)
        print(f"✅ PDF guardado: test_factura_solo_pdf.pdf ({len(pdf_only)} bytes)")
    
    # Opción 2: Probar flujo completo (con NubeFact SIMULADO)
    print("\n" + "-" * 60)
    print("🔄 OPCIÓN 2: Flujo completo (con NubeFact)")
    print("-" * 60)
    
    # IMPORTANTE: En desarrollo, puedes simular la respuesta de NubeFact
    # o usar un endpoint de prueba si tienes uno
    
    # Para prueba, desactivamos el envío real a NubeFact
    # Modifica test_data para simular
    test_data_simulado = test_data.copy()
    test_data_simulado["simular_nubefact"] = True  # Bandera para tu servicio
    
    result = await service.create_invoice(
        test_data_simulado, 
        generate_pdf=True, 
        save_to_disk=False
    )
    print(f"\n🔍 Resultado del flujo completo: {result}")
    
    if result['success']:
        print("\n✅ FLUJO COMPLETADO EXITOSAMENTE")
        print(f"   Factura: {result['invoice_data'].get('serie')}-{result['invoice_data'].get('numero')}")
        
        if result.get('pdf_content'):
            with open("test_factura_completa.pdf", "wb") as f:
                f.write(result['pdf_content'])
            print(f"✅ PDF completo guardado: test_factura_completa.pdf")
            
        # Mostrar datos importantes
        if 'nubefact_response' in result:
            resp = result['nubefact_response']
            print(f"\n📊 Respuesta NubeFact:")
            print(f"   Success: {resp.get('success')}")
            print(f"   Número: {resp.get('numero')}")
            print(f"   Hash: {resp.get('codigo_hash', '')[:30]}...")
    else:
        print(f"\n❌ ERROR: {result.get('error')}")
    
    print("\n" + "=" * 60)
    print("🏁 PRUEBA FINALIZADA")
    print("=" * 60)

def main():
    """Punto de entrada principal"""
    # Crear un nuevo bucle de eventos
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(test_invoice_flow())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
