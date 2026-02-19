# flow_invoice_pdf_qr/step1_send_only.py

import asyncio
import httpx
from pathlib import Path
from datetime import datetime

from .shared import (
    setup_directories,
    create_test_invoice_data,
    save_response_to_file,
    check_logs,
    save_api_log  # ✅ NUEVA IMPORTACIÓN
)


async def send_to_nubefact_only(invoice_number=None):
    """Envía a NubeFact, guarda respuesta y registra en BD."""
    
    print("\n" + "=" * 60)
    print("🧪 PASO 1: ENVÍO A NUBEFACT (CON LOGGING EN BD)")
    print("=" * 60)
    
    # 1. Preparar datos
    output_dir = setup_directories(Path("test_output/step1"))
    invoice_data = create_test_invoice_data(invoice_number)
    
    print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
    print(f"   Cliente: {invoice_data['cliente_denominacion']}")
    print(f"   Total: S/ {invoice_data['total']}")
    
    # 2. Configurar petición
    url = "https://api.nubefact.com/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 737745e11f79445d8b3658e66ee0a085de51aefe18554c4ba51532d8f0e57e9b",
        "Accept": "application/json",
    }
    
    # 3. Enviar petición
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
        
        # 4. Guardar respuesta en archivo
        filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
        save_response_to_file(response_data, filename, output_dir)
        
        # 5. ✅ GUARDAR LOG EN BD
        await save_api_log(
            endpoint_name="generar_comprobante",
            status_code=resp.status_code,
            duration_ms=int(duration),
            request_data=invoice_data,
            response_data=response_data,
            called_from="step1_send_only"
        )
        
        # 6. Mostrar resultado
        if resp.status_code == 200:
            print(f"\n✅ ENVÍO EXITOSO")
            if response_data.get('aceptada_por_sunat'):
                print(f"   ✅ ACEPTADA por SUNAT")
            else:
                print(f"   ⏳ PENDIENTE de SUNAT")
            print(f"   Hash: {response_data.get('codigo_hash', 'N/A')[:30]}...")
            success = True
        else:
            print(f"\n❌ ERROR {resp.status_code}")
            error_msg = response_data.get('errors', response_data)
            if isinstance(error_msg, dict):
                error_msg = str(error_msg)
            print(f"   {error_msg[:200]}")
            success = False
        
        # 7. Verificar logs en BD
        print(f"\n⏳ Verificando logs en BD...")
        await asyncio.sleep(1)  # Pequeña pausa
        await check_logs(invoice_data['numero'])
        
        return {
            "success": success,
            "invoice_data": invoice_data,
            "response": response_data,
            "output_dir": output_dir,
            "filename": filename
        }


def main():
    """Punto de entrada."""
    import sys
    
    # Tomar número de argumento o usar default
    numero = sys.argv[1] if len(sys.argv) > 1 else "91521"
    
    # Forzar a string si es necesario
    numero = str(numero)
    
    result = asyncio.run(send_to_nubefact_only(numero))
    
    if result["success"]:
        print(f"\n🎯 PASO 1 COMPLETADO")
        print(f"   Respuesta guardada en: {result['output_dir'] / result['filename']}")
    else:
        print(f"\n❌ PASO 1 FALLÓ")
        sys.exit(1)


if __name__ == "__main__":
    main()