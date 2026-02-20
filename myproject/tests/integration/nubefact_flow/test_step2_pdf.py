# tests/integration/nubefact_flow/test_step2_pdf.py

import pytest
from pathlib import Path

from .base_test import NubefactTestBase
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator


@pytest.mark.integration
class TestNubefactPDF(NubefactTestBase):
    """
    Prueba de integración: Generar PDF desde respuesta guardada.
    """
    
    def test_generate_pdf_from_response(self, response_file: Path = None):
        """
        Genera PDF a partir de un archivo de respuesta.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 2: GENERAR PDF DESDE RESPUESTA")
        print("="*60)
        
        # Buscar respuesta si no se proporciona
        if response_file is None:
            response_file = self._find_latest_response()
        
        if not response_file or not response_file.exists():
            print(f"❌ No se encontró archivo de respuesta")
            return {"success": False, "error": "No response file"}
        
        print(f"\n📂 Usando respuesta: {response_file}")
        
        # Cargar respuesta
        response = self.load_response(response_file)
        
        # Extraer datos para PDF
        invoice_data = self._extract_pdf_data(response)
        
        # Configurar salida
        output_dir = self.setup_output_dir("step2_pdf")
        
        # Generar PDF
        print(f"\n📄 Generando PDF...")
        
        try:
            generator = InvoicePDFGenerator(invoice_data)
            pdf_content = generator.generate_sync()
            
            # Guardar PDF
            filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_from_response.pdf"
            filepath = output_dir / filename
            
            with open(filepath, "wb") as f:
                f.write(pdf_content)
            
            print(f"\n✅ PDF GENERADO EXITOSAMENTE")
            print(f"   Ruta: {filepath}")
            print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
            print(f"   QR incluido: {'✅' if invoice_data.get('cadena_para_codigo_qr') else '❌'}")
            print(f"   Hash incluido: {'✅' if invoice_data.get('codigo_hash') else '❌'}")
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "pdf_path": filepath,
                "pdf_size": len(pdf_content)
            }
            
        except Exception as e:
            print(f"\n❌ Error generando PDF: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _find_latest_response(self) -> Path:
        """Encuentra el archivo de respuesta más reciente."""
        base_dir = self.BASE_OUTPUT_DIR
        response_files = list(base_dir.rglob("response_*.json"))
        
        if not response_files:
            return None
        
        return max(response_files, key=lambda p: p.stat().st_mtime)
    
    def _extract_pdf_data(self, response: dict) -> dict:
        """Extrae datos necesarios para el PDF desde la respuesta."""
        return {
            "serie": response.get('serie', 'F001'),
            "numero": str(response.get('numero', '00000')),
            "fecha_de_emision": response.get('fecha_de_emision', ''),
            "cliente_denominacion": "EMPRESA DE PRUEBA INTEGRACIÓN S.A.C.",
            "cliente_numero_de_documento": "20343443961",
            "total": str(response.get('total', '1000.00')),
            "codigo_hash": response.get('codigo_hash'),
            "cadena_para_codigo_qr": response.get('cadena_para_codigo_qr'),
            "aceptada_por_sunat": response.get('aceptada_por_sunat', False),
            "items": [
                {
                    "descripcion": "SERVICIO DE CONSULTORÍA IT",
                    "cantidad": "10",
                    "precio_unitario": "100.00",
                    "subtotal": "847.46",
                    "igv": "152.54"
                }
            ]
        }


# Función para ejecutar manualmente
def main():
    test = TestNubefactPDF()
    result = test.test_generate_pdf_from_response()
    if result["success"]:
        print(f"\n✅ PRUEBA EXITOSA")
    else:
        print(f"\n❌ PRUEBA FALLÓ: {result['error']}")

if __name__ == "__main__":
    main()