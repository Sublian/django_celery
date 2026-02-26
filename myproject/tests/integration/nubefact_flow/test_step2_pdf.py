# tests/integration/nubefact_flow/test_step2_pdf.py

# Cómo ejecutar el Paso 2
# # Opción 1: Usar el último response encontrado
# python -m tests.integration.nubefact_flow.test_step2_pdf

# # Opción 2: Especificar un número de factura
# python -m tests.integration.nubefact_flow.test_step2_pdf --numero 91512

# # Opción 3: Usar un archivo específico
# python -m tests.integration.nubefact_flow.test_step2_pdf --file test_output/integration/step1_send/20260223_120353/response_F001_91512.json

# # Opción 4: Generar PDF directamente desde el log en BD
# python -m tests.integration.nubefact_flow.test_step2_pdf --from-log --numero 91512

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import json

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

import pytest
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from api_service.services.nubefact.schemas.comprobante import ComprobanteSchema
from api_service.models import ApiCallLog

from .base_test import NubefactTestBase


class TestNubefactPDF(NubefactTestBase):
    """
    Prueba de integración: Generar PDF desde respuesta guardada.
    """
    
    def find_latest_response(self, numero: str = None) -> Path:
        """
        Encuentra el archivo de respuesta más reciente.
        Si se proporciona número, busca específicamente ese.
        """
        base_dir = self.BASE_OUTPUT_DIR
        
        if numero:
            # Buscar específicamente por número
            pattern = f"*{numero}*.json"
            response_files = list(base_dir.rglob(pattern))
        else:
            # Buscar todos los archivos response
            response_files = list(base_dir.rglob("response_*.json"))
        
        if not response_files:
            return None
        
        return max(response_files, key=lambda p: p.stat().st_mtime)
    
    def extract_invoice_data_from_response(self, response: dict) -> dict:
        """
        Extrae datos necesarios para el PDF desde la respuesta de NubeFact.
        """
        # Datos básicos de la respuesta
        invoice_data = {
            "serie": response.get('serie', 'F001'),
            "numero": str(response.get('numero', '00000')),
            "fecha_de_emision": response.get('fecha_de_emision', datetime.now().strftime("%d-%m-%Y")),
            "cliente_denominacion": "EMPRESA DE PRUEBA INTEGRACIÓN S.A.C.",
            "cliente_numero_de_documento": "20343443961",
            "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
            "total_gravada": str(response.get('total_gravada', '847.46')),
            "total_igv": str(response.get('total_igv', '152.54')),
            "total": str(response.get('total', '1000.00')),
            "codigo_hash": response.get('codigo_hash'),
            "cadena_para_codigo_qr": response.get('cadena_para_codigo_qr'),
            "aceptada_por_sunat": response.get('aceptada_por_sunat', False),
            "enlace_del_pdf": response.get('enlace_del_pdf'),
            "observaciones": f"Factura generada el {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "items": [
                {
                    "unidad_de_medida": "ZZ",
                    "codigo": "SERV-001",
                    "descripcion": "SERVICIO DE CONSULTORÍA IT - Prueba integración",
                    "cantidad": "10",
                    "precio_unitario": "100.00",
                    "subtotal": "847.46",
                    "igv": "152.54",
                    "total": "1000.00",
                }
            ],
        }
        
        # Intentar extraer items de la respuesta si existen
        if 'items' in response and response['items']:
            invoice_data['items'] = response['items']
        
        return invoice_data
    
    def test_generate_pdf_from_response(self, numero: str = None, response_file: Path = None):
        """
        Genera PDF a partir de un archivo de respuesta.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 2: GENERAR PDF DESDE RESPUESTA")
        print("="*60)
        
        # 1. Encontrar archivo de respuesta
        if response_file is None:
            response_file = self.find_latest_response(numero)
        
        if not response_file or not response_file.exists():
            print(f"\n❌ No se encontró archivo de respuesta")
            print("   Ejecuta primero: python -m tests.integration.nubefact_flow.test_step1_send")
            return {"success": False, "error": "No response file"}
        
        print(f"\n📂 Usando respuesta: {response_file}")
        
        # 2. Cargar respuesta
        try:
            with open(response_file, "r", encoding="utf-8") as f:
                response = json.load(f)
            print(f"✅ Respuesta cargada correctamente")
            print(f"   Factura: {response.get('serie', 'F001')}-{response.get('numero', 'N/A')}")
            print(f"   Hash: {response.get('codigo_hash', 'N/A')[:30]}...")
            print(f"   Estado SUNAT: {'✅ ACEPTADA' if response.get('aceptada_por_sunat') else '⏳ PENDIENTE'}")
        except Exception as e:
            print(f"\n❌ Error cargando respuesta: {e}")
            return {"success": False, "error": str(e)}
        
        # 3. Extraer datos para PDF
        invoice_data = self.extract_invoice_data_from_response(response)
        
        # 4. Configurar salida
        output_dir = self.setup_output_dir("step2_pdf")
        
        # 5. Validar que tenemos los datos necesarios para el QR
        if not invoice_data.get('codigo_hash'):
            print(f"\n⚠️ ADVERTENCIA: No hay código hash en la respuesta")
        if not invoice_data.get('cadena_para_codigo_qr'):
            print(f"\n⚠️ ADVERTENCIA: No hay cadena para QR en la respuesta")
        
        # 6. Generar PDF
        print(f"\n📄 Generando PDF...")
        
        try:
            start = datetime.now()
            generator = InvoicePDFGenerator(invoice_data)
            pdf_content = generator.generate_sync()
            duration = (datetime.now() - start).total_seconds()
            
            # 7. Guardar PDF
            filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_from_response.pdf"
            filepath = output_dir / filename
            
            with open(filepath, "wb") as f:
                f.write(pdf_content)
            
            print(f"\n✅ PDF GENERADO EXITOSAMENTE")
            print(f"   Ruta: {filepath}")
            print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
            print(f"   Tiempo: {duration:.2f}s")
            print(f"   QR incluido: {'✅' if invoice_data.get('cadena_para_codigo_qr') else '❌'}")
            print(f"   Hash incluido: {'✅' if invoice_data.get('codigo_hash') else '❌'}")
            print(f"   Estado SUNAT: {'✅ ACEPTADA' if invoice_data.get('aceptada_por_sunat') else '⏳ PENDIENTE'}")
            
            # 8. Verificar que el PDF se creó correctamente
            if len(pdf_content) < 1000:
                print(f"\n⚠️ ADVERTENCIA: El PDF es muy pequeño ({len(pdf_content)} bytes)")
            
            return {
                "success": True,
                "response_file": response_file,
                "invoice_data": invoice_data,
                "pdf_path": filepath,
                "pdf_size": len(pdf_content),
                "output_dir": output_dir
            }
            
        except Exception as e:
            print(f"\n❌ Error generando PDF: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def test_generate_pdf_from_log(self, numero: str):
        """
        Genera PDF directamente desde el log en BD (sin archivo JSON).
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 2: GENERAR PDF DESDE LOG EN BD")
        print("="*60)
        
        # 1. Buscar log en BD
        from django.db import connection
        
        logs = ApiCallLog.objects.filter(
            response_data__contains=f'"{numero}"'
        ).order_by('-created_at')
        
        if not logs.exists():
            print(f"\n❌ No se encontraron logs para el número {numero}")
            return {"success": False, "error": "Log not found"}
        
        latest_log = logs.first()
        print(f"\n📄 Log encontrado:")
        print(f"   ID: {latest_log.id}")
        print(f"   Fecha: {latest_log.created_at}")
        print(f"   Estado: {latest_log.status}")
        
        # 2. Extraer response_data
        response = latest_log.response_data
        
        # 3. Generar PDF (reutilizando método anterior)
        return self.test_generate_pdf_from_response(
            response_file=None,
            numero=numero
        )


# Función para ejecutar manualmente
def main():
    """Punto de entrada para ejecución manual."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generar PDF desde respuesta de NubeFact')
    parser.add_argument('--numero', type=str, help='Número de factura específico')
    parser.add_argument('--file', type=str, help='Ruta específica al archivo de respuesta')
    parser.add_argument('--from-log', action='store_true', help='Usar log de BD en lugar de archivo')
    args = parser.parse_args()
    
    test = TestNubefactPDF()
    
    if args.from_log and args.numero:
        result = test.test_generate_pdf_from_log(args.numero)
    elif args.file:
        result = test.test_generate_pdf_from_response(response_file=Path(args.file))
    elif args.numero:
        result = test.test_generate_pdf_from_response(numero=args.numero)
    else:
        # Usar el último response encontrado
        result = test.test_generate_pdf_from_response()
    
    if result["success"]:
        print(f"\n✅ PRUEBA EXITOSA")
        print(f"   PDF: {result['pdf_path']}")
        sys.exit(0)
    else:
        print(f"\n❌ PRUEBA FALLÓ: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()