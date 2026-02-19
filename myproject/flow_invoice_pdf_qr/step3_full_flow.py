# flow_invoice_pdf_qr/step3_full_flow.py
"""
PASO 3: Flujo completo - envía a NubeFact y genera PDF automáticamente.
Integra los pasos 1 y 2 en un solo flujo.
"""

import asyncio
import httpx
from pathlib import Path
from datetime import datetime
import sys

from .shared import (
    setup_directories,
    create_test_invoice_data,
    save_response_to_file,
    check_logs,
    save_api_log,
    load_response_from_file  # Por si necesitamos recargar
)
from .step2_generate_pdf import generate_pdf_from_response


async def full_flow(invoice_number=None):
    """
    Flujo completo: 
    1. Envía factura a NubeFact
    2. Guarda respuesta en archivo
    3. Registra log en BD
    4. Genera PDF automáticamente
    """
    
    print("\n" + "=" * 60)
    print("🧪 PASO 3: FLUJO COMPLETO (NUBEFACT + PDF)")
    print("=" * 60)
    
    # 1. Preparar directorios
    base_output_dir = Path("test_output/step3")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_output_dir / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Crear datos de factura
    invoice_data = create_test_invoice_data(invoice_number)
    factura_num = invoice_data['numero']
    
    print(f"\n📄 Factura: {invoice_data['serie']}-{factura_num}")
    print(f"   Cliente: {invoice_data['cliente_denominacion']}")
    print(f"   Total: S/ {invoice_data['total']}")
    
    # 3. Configurar petición a NubeFact
    url = "https://api.nubefact.com/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 737745e11f79445d8b3658e66ee0a085de51aefe18554c4ba51532d8f0e57e9b",
        "Accept": "application/json",
    }
    
    # 4. Enviar a NubeFact
    print(f"\n📤 Enviando a NubeFact...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        start = datetime.now()
        resp = await client.post(url, json=invoice_data, headers=headers)
        duration = (datetime.now() - start).total_seconds() * 1000
        
        print(f"📥 Respuesta: HTTP {resp.status_code} ({duration:.0f}ms)")
        
        try:
            response_data = resp.json()
        except:
            response_data = {"error": "Respuesta no JSON", "text": resp.text}
        
        # 5. Guardar respuesta en archivo
        response_filename = f"response_{invoice_data['serie']}_{factura_num}.json"
        response_path = save_response_to_file(response_data, response_filename, output_dir)
        
        # 6. Guardar log en BD
        await save_api_log(
            endpoint_name="generar_comprobante",
            status_code=resp.status_code,
            duration_ms=int(duration),
            request_data=invoice_data,
            response_data=response_data,
            called_from="step3_full_flow"
        )
        
        # 7. Mostrar resultado del envío
        if resp.status_code == 200:
            print(f"\n✅ ENVÍO EXITOSO")
            if response_data.get('aceptada_por_sunat'):
                print(f"   ✅ ACEPTADA por SUNAT")
            else:
                print(f"   ⏳ PENDIENTE de SUNAT")
            print(f"   Hash: {response_data.get('codigo_hash', 'N/A')[:30]}...")
            envio_exitoso = True
        else:
            print(f"\n❌ ERROR {resp.status_code}")
            error_msg = response_data.get('errors', response_data)
            if isinstance(error_msg, dict):
                error_msg = str(error_msg)
            print(f"   {error_msg[:200]}")
            envio_exitoso = False
    
    # 8. Verificar logs en BD
    print(f"\n⏳ Verificando logs en BD...")
    await asyncio.sleep(1)
    await check_logs(factura_num)
    
    # 9. Si el envío fue exitoso, generar PDF
    if envio_exitoso:
        print(f"\n📄 Generando PDF desde la respuesta...")
        
        # Extraer datos actualizados con la respuesta de NubeFact
        invoice_data.update({
            "codigo_hash": response_data.get("codigo_hash"),
            "cadena_para_codigo_qr": response_data.get("cadena_para_codigo_qr"),
            "aceptada_por_sunat": response_data.get("aceptada_por_sunat", False),
        })
        
        # Usar la función del paso 2 para generar PDF
        pdf_result = generate_pdf_from_response(
            response_file=response_path,
            output_dir=output_dir,
            log_to_db=False  # Ya tenemos el log del envío
        )
        
        if pdf_result and pdf_result["success"]:
            print(f"\n✅ PDF GENERADO EXITOSAMENTE")
            print(f"   Ruta: {pdf_result['pdf_path']}")
            print(f"   Tamaño: {pdf_result['pdf_size'] / 1024:.1f} KB")
        else:
            print(f"\n❌ Error generando PDF")
            envio_exitoso = False
    else:
        print(f"\n⏭️  No se generará PDF debido a error en el envío")
    
    # 10. Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN DEL FLUJO COMPLETO")
    print("=" * 60)
    print(f"   Factura: {invoice_data['serie']}-{factura_num}")
    print(f"   Envío: {'✅ EXITOSO' if envio_exitoso else '❌ FALLIDO'}")
    if envio_exitoso:
        print(f"   Estado SUNAT: {'✅ ACEPTADA' if response_data.get('aceptada_por_sunat') else '⏳ PENDIENTE'}")
        print(f"   PDF generado: {pdf_result['pdf_path'] if 'pdf_result' in locals() else 'N/A'}")
    print(f"   Logs guardados: test_output/step3/{timestamp}/")
    print("=" * 60)
    
    return {
        "success": envio_exitoso,
        "invoice_data": invoice_data,
        "response": response_data if envio_exitoso else None,
        "pdf_path": pdf_result["pdf_path"] if envio_exitoso and "pdf_result" in locals() else None,
        "output_dir": output_dir
    }


def main():
    """Punto de entrada."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Flujo completo: NubeFact + PDF')
    parser.add_argument('--numero', type=str, help='Número de factura (opcional)')
    args = parser.parse_args()
    
    # Ejecutar flujo completo
    result = asyncio.run(full_flow(args.numero))
    
    if result["success"]:
        print(f"\n🎯 PASO 3 COMPLETADO EXITOSAMENTE")
        print(f"   PDF: {result['pdf_path']}")
        sys.exit(0)
    else:
        print(f"\n❌ PASO 3 FALLÓ")
        sys.exit(1)


if __name__ == "__main__":
    main()