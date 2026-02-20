# tests/integration/nubefact_flow/test_step3_full.py

import pytest
import asyncio
from datetime import datetime

from .base_test import NubefactTestBase
from .test_step2_pdf import TestNubefactPDF


@pytest.mark.django_db
@pytest.mark.integration
class TestNubefactFullFlow(NubefactTestBase):
    """
    Prueba de integración: Flujo completo (envío + PDF).
    """
    
    @pytest.mark.asyncio
    async def test_full_flow_async(self, numero_factura=None):
        """
        Ejecuta el flujo completo usando servicio asíncrono.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 3: FLUJO COMPLETO ASYNC")
        print("="*60)
        
        # Configurar
        output_dir = self.setup_output_dir("step3_full_async")
        numero = numero_factura or str(int(datetime.now().timestamp() % 100000))
        invoice_data = self.create_test_invoice_data(numero)
        
        print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
        
        # 1. Enviar a NubeFact
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
            
            # Guardar respuesta
            resp_filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            resp_path = self.save_response(response, resp_filename, output_dir)
            
            # 2. Generar PDF
            print(f"\n📄 Generando PDF...")
            
            # Preparar datos para PDF
            pdf_data = invoice_data.copy()
            pdf_data.update({
                "codigo_hash": response.get("codigo_hash"),
                "cadena_para_codigo_qr": response.get("cadena_para_codigo_qr"),
                "aceptada_por_sunat": response.get("aceptada_por_sunat", False),
            })
            
            from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
            generator = InvoicePDFGenerator(pdf_data)
            pdf_content = generator.generate_sync()
            
            pdf_filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_full.pdf"
            pdf_path = output_dir / pdf_filename
            
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)
            
            print(f"✅ PDF generado: {pdf_path}")
            print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "response": response,
                "pdf_path": pdf_path,
                "output_dir": output_dir
            }
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @pytest.mark.asyncio
    async def test_full_flow_sync(self, numero_factura=None):
        """
        Ejecuta el flujo completo usando servicio síncrono.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 3: FLUJO COMPLETO SYNC")
        print("="*60)
        
        # Configurar
        output_dir = self.setup_output_dir("step3_full_sync")
        numero = numero_factura or str(int(datetime.now().timestamp() % 100000))
        invoice_data = self.create_test_invoice_data(numero)
        
        print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
        
        # 1. Enviar a NubeFact
        print(f"\n📤 Enviando a NubeFact...")
        service = self.get_sync_service()
        
        try:
            start = datetime.now()
            response = service.generar_comprobante(invoice_data)
            duration = (datetime.now() - start).total_seconds()
            
            print(f"📥 Respuesta recibida en {duration:.2f}s")
            print(f"   Hash: {response.get('codigo_hash', 'N/A')[:30]}...")
            
            # Guardar respuesta
            resp_filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            resp_path = self.save_response(response, resp_filename, output_dir)
            
            # 2. Generar PDF
            print(f"\n📄 Generando PDF...")
            
            pdf_data = invoice_data.copy()
            pdf_data.update({
                "codigo_hash": response.get("codigo_hash"),
                "cadena_para_codigo_qr": response.get("cadena_para_codigo_qr"),
                "aceptada_por_sunat": response.get("aceptada_por_sunat", False),
            })
            
            from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
            generator = InvoicePDFGenerator(pdf_data)
            pdf_content = generator.generate_sync()
            
            pdf_filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_full.pdf"
            pdf_path = output_dir / pdf_filename
            
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)
            
            print(f"✅ PDF generado: {pdf_path}")
            print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "response": response,
                "pdf_path": pdf_path,
                "output_dir": output_dir
            }
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return {"success": False, "error": str(e)}


# Función para ejecutar manualmente
async def main():
    test = TestNubefactFullFlow()
    result = await test.test_full_flow_async("91533")
    if result["success"]:
        print(f"\n✅ PRUEBA EXITOSA")
    else:
        print(f"\n❌ PRUEBA FALLÓ: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())