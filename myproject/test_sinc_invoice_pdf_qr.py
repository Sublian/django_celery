"""
Prueba Sincrónica Completa: Facturación + PDF + QR
Versión Mejorada con configuración, validación y logging detallado
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django
django.setup()

# Importaciones después de configurar Django
from billing.services.invoice_service import InvoiceService
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from asgiref.sync import sync_to_async, async_to_sync

class InvoiceTestRunner:
    """Runner completo para pruebas de facturación con PDF y QR"""
    
    def __init__(self, config=None):
        self.config = config or self.get_default_config()
        self.service = None
        self.nubefact_service = None
        self.test_results = {
            'start_time': None,
            'end_time': None,
            'steps': {},
            'errors': [],
            'generated_files': []
        }
    
    def get_default_config(self):
        """Configuración por defecto"""
        return {
            'generate_pdf': True,
            'save_to_disk': True,
            'output_dir': Path('test_output'),
            'use_real_nubefact': False,  # Cambiar a True para producción
            'simulate_nubefact_response': True,  # Para desarrollo
            'log_level': 'detailed'  # 'basic', 'detailed', 'debug'
        }
    
    def log(self, message, level='info'):
        """Logging controlado por nivel"""
        if self.config['log_level'] == 'basic' and level not in ['info', 'error']:
            return
        
        prefix = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'debug': '🔍'
        }.get(level, '📝')
        
        print(f"{prefix} {message}")
    
    def create_test_invoice_data(self, invoice_number=None):
        """Crea datos de prueba completos para una factura"""
        if invoice_number is None:
            invoice_number = 91502
            # invoice_number = f"{int(datetime.now().timestamp() % 100000)}"
        
        return {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": 1,  # Factura
            "serie": "F001",
            "numero": invoice_number,
            "sunat_transaction": 1,
            "cliente_tipo_de_documento": "6",
            "cliente_numero_de_documento": "20343443961",
            "cliente_denominacion": "EMPRESA DE PRUEBA S.A.C.",
            "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
            "cliente_email": "contacto@empresaprueba.com",
            "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
            "fecha_de_vencimiento": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "moneda": "1",  # Soles
            "tipo_de_cambio": 1.0,
            "porcentaje_de_igv": 18.0,
            "total_descuento": 0.0,
            "total_gravada": 847.46,
            "total_inafecta": 0.0,
            "total_exonerada": 0.0,
            "total_igv": 152.54,
            "total_gratuita": 0.0,
            "total": 1000.00,
            "condiciones_de_pago": "CREDITO",
            "medio_de_pago": "credito",
            "observaciones": "Factura de prueba generada automáticamente\nEsta factura cubre servicios del mes actual",
            "enviar_automaticamente_a_la_sunat": "false",
            "enviar_automaticamente_al_cliente": "false",
            "venta_al_credito": [
                {
                    "cuota": 1,
                    "fecha_de_pago": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "importe": 1000.00
                }
            ],
            "items": [
                {
                    "unidad_de_medida": "ZZ",
                    "codigo": "SERV-001",
                    "descripcion": "SERVICIO DE CONSULTORÍA IT - Asesoría técnica especializada en desarrollo de software",
                    "cantidad": 10.0,
                    "valor_unitario": 84.746,
                    "precio_unitario": 100.00,
                    "descuento": 0.0,
                    "subtotal": 847.46,
                    "tipo_de_igv": "1",
                    "igv": 152.54,
                    "total": 1000.00,
                    "codigo_producto_sunat": "81112105"
                }
            ]
        }
    
    def simulate_nubefact_response(self, invoice_data):
        """Simula respuesta de NubeFact para desarrollo"""
        self.log("Simulando respuesta de NubeFact...", "warning")
        
        return {
            "success": True,
            "tipo_de_comprobante": invoice_data["tipo_de_comprobante"],
            "serie": invoice_data["serie"],
            "numero": invoice_data["numero"],
            "enlace": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}",
            "aceptada_por_sunat": True,
            "sunat_description": f"La Factura Electrónica {invoice_data['serie']}-{invoice_data['numero']} ha sido ACEPTADA",
            "sunat_responsecode": "0",
            "cadena_para_codigo_qr": f"20123456789|01|{invoice_data['serie']}|{invoice_data['numero']}|{invoice_data['total_igv']}|{invoice_data['total']}|{invoice_data['fecha_de_emision']}|6|{invoice_data['cliente_numero_de_documento']}|TEST_HASH_SIMULADO|",
            "codigo_hash": f"TEST_HASH_{invoice_data['numero']}_SIMULADO",
            "codigo_de_barras": f"20123456789|01|{invoice_data['serie']}|{invoice_data['numero']}|{invoice_data['total_igv']}|{invoice_data['total']}|{invoice_data['fecha_de_emision']}|6|{invoice_data['cliente_numero_de_documento']}|TEST_HASH_SIMULADO|",
            "enlace_del_pdf": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}.pdf",
            "enlace_del_xml": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}.xml",
            "enlace_del_cdr": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}.cdr"
        }
    
    async def send_to_nubefact_async(self, invoice_data):
        """Envía factura a NubeFact (real o simulado)"""
        self.log(f"Enviando factura {invoice_data['serie']}-{invoice_data['numero']} a NubeFact...")
        
        if not self.config['use_real_nubefact'] and self.config['simulate_nubefact_response']:
            # Modo simulación para desarrollo
            await asyncio.sleep(1)  # Simular delay de red
            return self.simulate_nubefact_response(invoice_data)
        
        # Modo real - usar NubefactServiceAsync
        if self.nubefact_service is None:
            self.nubefact_service = NubefactServiceAsync()
        
        try:
            response = await self.nubefact_service.generar_comprobante(invoice_data)
            self.log(f"✅ Respuesta recibida de NubeFact", "success")
            return response
        except Exception as e:
            self.log(f"❌ Error enviando a NubeFact: {str(e)}", "error")
            raise
    
    async def generate_pdf_with_qr_async(self, invoice_data, nubefact_response):
        """Genera PDF con QR a partir de los datos"""
        self.log("Generando PDF con código QR...")
        
        try:
            # Actualizar invoice_data con respuesta de NubeFact
            invoice_data.update({
                'codigo_unico': nubefact_response.get('codigo_hash'),
                'cadena_para_codigo_qr': nubefact_response.get('cadena_para_codigo_qr'),
                'qr_url': nubefact_response.get('cadena_para_codigo_qr'),
                'xml_url': nubefact_response.get('enlace_del_xml'),
                'enlace_del_pdf': nubefact_response.get('enlace_del_pdf'),
                'sunat_response': nubefact_response,
                'aceptada_por_sunat': nubefact_response.get('aceptada_por_sunat', False)
            })
            
            # Generar PDF
            template_name = invoice_data.get(
                'template', 
                'billing/factura_electronica.html'
            )
            
            pdf_generator = InvoicePDFGenerator(invoice_data, template_name)
            pdf_content = await pdf_generator.generate_async()
            
            self.log(f"✅ PDF generado ({len(pdf_content)} bytes)", "success")
            return pdf_content
            
        except Exception as e:
            self.log(f"❌ Error generando PDF: {str(e)}", "error")
            raise
    
    def save_pdf_to_disk(self, pdf_content, invoice_data, output_dir=None):
        """Guarda el PDF en disco"""
        if output_dir is None:
            output_dir = self.config['output_dir']
        
        # Crear directorio si no existe
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombre del archivo
        filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}.pdf"
        filepath = output_dir / filename
        
        # Guardar archivo
        with open(filepath, 'wb') as f:
            f.write(pdf_content)
        
        self.log(f"💾 PDF guardado: {filepath}", "success")
        return str(filepath)
    
    def validate_invoice_data(self, invoice_data):
        """Valida que los datos de la factura sean completos"""
        required_fields = [
            'tipo_de_comprobante', 'serie', 'numero',
            'cliente_denominacion', 'cliente_numero_de_documento',
            'fecha_de_emision', 'total', 'items'
        ]
        
        errors = []
        for field in required_fields:
            if field not in invoice_data or not invoice_data[field]:
                errors.append(f"Campo requerido faltante: {field}")
        
        # Validar items
        if 'items' in invoice_data:
            if not invoice_data['items']:
                errors.append("La factura debe tener al menos un item")
            else:
                for i, item in enumerate(invoice_data['items']):
                    item_required = ['descripcion', 'cantidad', 'precio_unitario']
                    for field in item_required:
                        if field not in item:
                            errors.append(f"Item {i+1} falta campo: {field}")
        
        return errors
    
    async def run_single_test(self, invoice_number=None):
        """Ejecuta una prueba completa individual"""
        self.test_results['start_time'] = datetime.now()
        
        try:
            # Paso 1: Preparar datos de prueba
            self.log("\n" + "="*60)
            self.log("PASO 1: PREPARANDO DATOS DE FACTURA")
            self.log("="*60)
            
            invoice_data = self.create_test_invoice_data(invoice_number)
            
            # Validar datos
            validation_errors = self.validate_invoice_data(invoice_data)
            if validation_errors:
                for error in validation_errors:
                    self.log(f"❌ {error}", "error")
                raise ValueError("Datos de factura inválidos")
            
            self.log(f"✅ Datos preparados: {invoice_data['serie']}-{invoice_data['numero']}", "success")
            self.log(f"   Cliente: {invoice_data['cliente_denominacion']}")
            self.log(f"   Total: S/ {invoice_data['total']:.2f}")
            self.log(f"   Items: {len(invoice_data['items'])}")
            
            self.test_results['steps']['data_preparation'] = 'success'
            
            # Paso 2: Enviar a NubeFact
            self.log("\n" + "="*60)
            self.log("PASO 2: ENVIANDO A NUBEFACT")
            self.log("="*60)
            
            nubefact_response = await self.send_to_nubefact_async(invoice_data)
            
            if nubefact_response.get('errors', False):
                raise ValueError(f"NubeFact respondió con error: {nubefact_response}")
            
            self.log(f"✅ Factura aceptada por SUNAT: {nubefact_response.get('aceptada_por_sunat', False)}")
            self.log(f"   Hash: {nubefact_response.get('codigo_hash', 'N/A')[:30]}...")
            self.log(f"   Enlace: {nubefact_response.get('enlace', 'N/A')}")
            
            self.test_results['steps']['nubefact_submission'] = 'success'
            self.test_results['nubefact_response'] = nubefact_response
            
            # Paso 3: Generar PDF con QR
            if self.config['generate_pdf']:
                self.log("\n" + "="*60)
                self.log("PASO 3: GENERANDO PDF CON CÓDIGO QR")
                self.log("="*60)
                
                pdf_content = await self.generate_pdf_with_qr_async(invoice_data, nubefact_response)
                
                self.test_results['steps']['pdf_generation'] = 'success'
                self.test_results['pdf_size'] = len(pdf_content)
                
                # Paso 4: Guardar en disco
                if self.config['save_to_disk'] and pdf_content:
                    self.log("\n" + "="*60)
                    self.log("PASO 4: GUARDANDO ARCHIVO")
                    self.log("="*60)
                    
                    filepath = self.save_pdf_to_disk(pdf_content, invoice_data)
                    
                    self.test_results['steps']['file_saving'] = 'success'
                    self.test_results['generated_files'].append(filepath)
                    
                    # Mostrar información del archivo
                    file_size_kb = len(pdf_content) / 1024
                    self.log(f"📊 RESUMEN DEL ARCHIVO:")
                    self.log(f"   Ruta: {filepath}")
                    self.log(f"   Tamaño: {file_size_kb:.1f} KB")
                    self.log(f"   Factura: {invoice_data['serie']}-{invoice_data['numero']}")
                    self.log(f"   QR incluido: {'✅' if nubefact_response.get('cadena_para_codigo_qr') else '❌'}")
                    self.log(f"   Hash incluido: {'✅' if nubefact_response.get('codigo_hash') else '❌'}")
            
            # Éxito completo
            self.test_results['end_time'] = datetime.now()
            duration = (self.test_results['end_time'] - self.test_results['start_time']).total_seconds()
            
            self.log("\n" + "="*60)
            self.log("🏁 PRUEBA COMPLETADA EXITOSAMENTE")
            self.log("="*60)
            self.log(f"⏱️  Duración total: {duration:.2f} segundos")
            self.log(f"📄 Archivos generados: {len(self.test_results['generated_files'])}")
            
            return {
                'success': True,
                'invoice_data': invoice_data,
                'nubefact_response': nubefact_response,
                'test_results': self.test_results,
                'generated_files': self.test_results['generated_files']
            }
            
        except Exception as e:
            self.test_results['end_time'] = datetime.now()
            self.test_results['errors'].append(str(e))
            
            self.log(f"\n❌ PRUEBA FALLIDA: {str(e)}", "error")
            
            return {
                'success': False,
                'error': str(e),
                'test_results': self.test_results
            }
    
    def run_sync(self, invoice_number=None):
        """Versión síncrona para scripts tradicionales"""
        return async_to_sync(self.run_single_test)(invoice_number)
    
    async def run_batch_test(self, count=3):
        """Ejecuta múltiples pruebas en lote"""
        results = []
        
        self.log(f"\n🚀 INICIANDO PRUEBA EN LOTE ({count} facturas)")
        self.log("="*60)
        
        for i in range(count):
            self.log(f"\n📦 FACTURA {i+1}/{count}")
            self.log("-"*40)
            
            result = await self.run_single_test()
            results.append(result)
            
            if not result['success']:
                self.log(f"⚠️  Prueba {i+1} falló, continuando...", "warning")
        
        # Resumen del lote
        successful = sum(1 for r in results if r['success'])
        failed = count - successful
        
        self.log("\n" + "="*60)
        self.log("📊 RESUMEN DE LOTE")
        self.log("="*60)
        self.log(f"✅ Exitosa: {successful}")
        self.log(f"❌ Fallidas: {failed}")
        self.log(f"📄 Total archivos: {sum(len(r.get('generated_files', [])) for r in results)}")
        
        return results

def main():
    """Función principal"""
    print("\n" + "="*60)
    print("🧪 PRUEBA COMPLETA: FACTURACIÓN + PDF + QR")
    print("="*60)
    
    # Configuración
    config = {
        'generate_pdf': True,
        'save_to_disk': True,
        'output_dir': Path('test_output') / datetime.now().strftime('%Y%m%d'),
        'use_real_nubefact': True,  # Cambiar a True para pruebas reales
        'simulate_nubefact_response': True,
        'log_level': 'detailed'
    }
    
    # Crear runner
    runner = InvoiceTestRunner(config)
    
    # Opciones de ejecución
    import argparse
    parser = argparse.ArgumentParser(description='Prueba de facturación con PDF y QR')
    parser.add_argument('--batch', type=int, help='Número de pruebas en lote')
    parser.add_argument('--numero', type=str, help='Número específico de factura')
    parser.add_argument('--real', action='store_true', help='Usar NubeFact real (no simulado)')
    parser.add_argument('--output', type=str, help='Directorio de salida')
    
    args = parser.parse_args()
    
    # Aplicar argumentos
    if args.real:
        config['use_real_nubefact'] = True
        config['simulate_nubefact_response'] = False
        print("⚠️  MODO REAL: Se enviará a NubeFact real")
    
    if args.output:
        config['output_dir'] = Path(args.output)
    
    # Ejecutar
    if args.batch:
        # Modo lote
        results = async_to_sync(runner.run_batch_test)(args.batch)
        
        # Guardar resultados en JSON
        output_file = config['output_dir'] / 'batch_results.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'config': config,
                'results': [{
                    'success': r['success'],
                    'invoice': r.get('invoice_data', {}).get('numero', 'N/A'),
                    'error': r.get('error'),
                    'files': r.get('generated_files', [])
                } for r in results]
            }, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 Resultados guardados en: {output_file}")
        
    else:
        # Modo individual
        result = runner.run_sync(args.numero)
        
        if result['success']:
            print(f"\n🎉 ¡PRUEBA EXITOSA!")
            print(f"   Factura: {result['invoice_data']['serie']}-{result['invoice_data']['numero']}")
            print(f"   Archivo: {result['generated_files'][0] if result['generated_files'] else 'No guardado'}")
            
            # Mostrar información del QR
            if 'nubefact_response' in result:
                qr_data = result['nubefact_response'].get('cadena_para_codigo_qr', '')
                if qr_data:
                    print(f"\n🔗 DATOS DEL QR:")
                    print(f"   {qr_data[:80]}...")
        else:
            print(f"\n💀 PRUEBA FALLIDA: {result.get('error')}")
            sys.exit(1)

if __name__ == "__main__":
    main()