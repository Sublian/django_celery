# tests/integration/nubefact_flow/test_step3_full.py

# Como utilizar el Test de integración completo
# # Opción 1: Flujo normal con número específico
# python -m tests.integration.nubefact_flow.test_step3_full --numero 91520

# # Opción 2: Sin número (se genera automáticamente)
# python -m tests.integration.nubefact_flow.test_step3_full

# # Opción 3: Con reintentos automáticos (para evitar duplicados)
# python -m tests.integration.nubefact_flow.test_step3_full --retry --numero 91520

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import asyncio

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

import pytest
from asgiref.sync import sync_to_async

from .base_test import NubefactTestBase
from .test_step2_pdf import TestNubefactPDF
from api_service.models import ApiCallLog


class TestNubefactFullFlow(NubefactTestBase):
    """
    Prueba de integración: Flujo completo (envío + PDF automático).
    """
    
    async def _check_log_after_send(self, numero: str, max_retries: int = 5):
        """
        Verifica que el log se haya guardado después del envío.
        """
        for attempt in range(max_retries):
            count = await sync_to_async(
                lambda: ApiCallLog.objects.filter(
                    response_data__contains=f'"{numero}"'
                ).count()
            )()
            
            if count > 0:
                print(f"✅ Log encontrado en BD (intento {attempt + 1})")
                return True
            
            if attempt < max_retries - 1:
                print(f"⏳ Esperando log... (intento {attempt + 1}/{max_retries})")
                await asyncio.sleep(1)
        
        print(f"❌ No se encontró log después de {max_retries} intentos")
        return False
    
    async def test_full_flow_async(self, numero: str = None):
        """
        Flujo completo asíncrono:
        1. Envía a NubeFact
        2. Espera confirmación de log
        3. Genera PDF automáticamente
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 3: FLUJO COMPLETO ASYNC")
        print("="*60)
        
        # 1. Preparar datos
        output_dir = self.setup_output_dir("step3_full_async")
        numero = numero or str(int(datetime.now().timestamp() % 100000))
        invoice_data = self.create_test_invoice_data(numero)
        
        print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
        
        # 2. Enviar a NubeFact
        print(f"\n📤 Enviando a NubeFact...")
        service = self.get_async_service()
        
        try:
            start = datetime.now()
            response = await service.generar_comprobante(
                invoice_data,
                caller_context="test_full_flow_async"
            )
            duration = (datetime.now() - start).total_seconds()
            
            print(f"📥 Respuesta recibida en {duration:.2f}s")
            print(f"   Hash: {response.get('codigo_hash', 'N/A')[:30]}...")
            print(f"   Estado: {'✅ ACEPTADA' if response.get('aceptada_por_sunat') else '⏳ PENDIENTE'}")
            
            # 3. Guardar respuesta
            resp_filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            resp_path = self.save_response(response, resp_filename, output_dir)
            print(f"✅ Respuesta guardada en: {resp_path}")
            
            # 4. Verificar log en BD
            log_ok = await self._check_log_after_send(invoice_data['numero'])
            if not log_ok:
                print(f"⚠️ ADVERTENCIA: No se encontró log en BD")
            
            # 5. Generar PDF automáticamente
            print(f"\n📄 Generando PDF automáticamente...")
            
            # Preparar datos para PDF
            pdf_data = invoice_data.copy()
            pdf_data.update({
                "codigo_hash": response.get("codigo_hash"),
                "cadena_para_codigo_qr": response.get("cadena_para_codigo_qr"),
                "aceptada_por_sunat": response.get("aceptada_por_sunat", False),
            })
            
            from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
            pdf_generator = InvoicePDFGenerator(pdf_data)
            pdf_content = pdf_generator.generate_sync()
            
            pdf_filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_full_async.pdf"
            pdf_path = output_dir / pdf_filename
            
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)
            
            print(f"\n✅ PDF GENERADO EXITOSAMENTE")
            print(f"   Ruta: {pdf_path}")
            print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
            print(f"   QR incluido: {'✅' if pdf_data.get('cadena_para_codigo_qr') else '❌'}")
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "response": response,
                "pdf_path": pdf_path,
                "output_dir": output_dir,
                "log_found": log_ok
            }
            
        except Exception as e:
            print(f"\n❌ Error en flujo completo: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def test_full_flow_sync(self, numero: str = None):
        """
        Flujo completo síncrono (wrapper para el asíncrono).
        """
        return asyncio.run(self.test_full_flow_async(numero))
    
    async def test_full_flow_with_retry(self, numero: str = None, max_retries: int = 3):
        """
        Flujo completo con reintentos automáticos para números duplicados.
        """
        for attempt in range(max_retries):
            print(f"\n📌 Intento {attempt + 1}/{max_retries}")
            
            # Generar nuevo número si no se proporcionó
            current_numero = numero or str(int(datetime.now().timestamp() % 100000) + attempt)
            
            result = await self.test_full_flow_async(current_numero)
            
            if result["success"]:
                return result
            
            # Si el error es por documento duplicado, intentar con otro número
            if "ya existe" in str(result.get("error", "")):
                print(f"⚠️ Documento duplicado, reintentando con otro número...")
                continue
            else:
                # Otro tipo de error, no reintentar
                break
        
        return {"success": False, "error": "Max retries exceeded"}


# Función para ejecutar manualmente
def main():
    """Punto de entrada para ejecución manual."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Flujo completo NubeFact + PDF')
    parser.add_argument('--numero', type=str, help='Número de factura específico')
    parser.add_argument('--retry', action='store_true', help='Reintentar automáticamente en caso de duplicado')
    args = parser.parse_args()
    
    test = TestNubefactFullFlow()
    
    if args.retry:
        result = asyncio.run(test.test_full_flow_with_retry(args.numero))
    else:
        result = asyncio.run(test.test_full_flow_async(args.numero))
    
    if result["success"]:
        print(f"\n✅ PRUEBA EXITOSA")
        print(f"   Factura: {result['invoice_data']['serie']}-{result['invoice_data']['numero']}")
        print(f"   PDF: {result['pdf_path']}")
        if result.get("log_found"):
            print(f"   Log en BD: ✅")
        sys.exit(0)
    else:
        print(f"\n❌ PRUEBA FALLÓ: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()