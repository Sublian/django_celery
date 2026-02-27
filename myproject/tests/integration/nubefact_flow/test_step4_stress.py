# tests/integration/nubefact_flow/test_step4_stress.py

# Como probar la prueba de integracion
# # Opción 1: Valores por defecto (desde 91500, 50 facturas, concurrencia 5)
# python -m tests.integration.nubefact_flow.test_step4_stress

# # Opción 2: Especificar número inicial
# python -m tests.integration.nubefact_flow.test_step4_stress --start 91500

# # Opción 3: Cambiar cantidad (máx 50)
# python -m tests.integration.nubefact_flow.test_step4_stress --start 91500 --count 50

# # Opción 4: Ajustar concurrencia
# python -m tests.integration.nubefact_flow.test_step4_stress --start 91500 --count 50 --concurrency 10

# # Opción 5: Con todos los parámetros
# python -m tests.integration.nubefact_flow.test_step4_stress --start 91500 --count 50 --concurrency 5

import os
import sys
import django
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import time

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from .base_test import NubefactTestBase
from api_service.models import ApiCallLog
from asgiref.sync import sync_to_async
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator


# tests/integration/nubefact_flow/test_step4_stress.py

class TestNubefactStress(NubefactTestBase):
    """
    Prueba de estrés: Genera 50 facturas consecutivas con sus PDFs.
    """
    
    def __init__(self, verbose: bool = False):
        super().__init__()
        self.verbose = verbose  # Control de logging
        self.results = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "duplicate": 0,
            "other_errors": 0,
            "details": []
        }
    
    def log(self, message: str, level: str = "info"):
        """Log condicional según verbose."""
        if self.verbose:
            print(message)
    
    async def send_single_invoice(self, numero: int, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """
        Envía una factura individual y genera su PDF.
        Versión optimizada sin prints innecesarios.
        """
        start_time = time.time()
        result = {
            "numero": numero,
            "success": False,
            "error": None,
            "duration_ms": 0,
            "log_found": False,
            "pdf_path": None
        }
        
        async with semaphore:
            # Solo mostrar inicio si es verbose
            if self.verbose:
                print(f"\n📤 [{numero}] Iniciando...", end="", flush=True)
            
            try:
                # 1. Preparar datos
                invoice_data = self.create_test_invoice_data(str(numero))
                
                # 2. Enviar a NubeFact
                service = self.get_async_service()
                response = await service.generar_comprobante(
                    invoice_data,
                    caller_context="test_stress_4"
                )
                
                duration = int((time.time() - start_time) * 1000)
                result["duration_ms"] = duration
                
                # 3. Verificar si es duplicado
                if response.get('codigo') == 23:
                    result["error"] = "Documento duplicado"
                    self.results["duplicate"] += 1
                    if self.verbose:
                        print(f" ⚠️ DUPLICADO")
                    return result
                
                # 4. Guardar respuesta (siempre, independiente de verbose)
                output_dir = self.BASE_OUTPUT_DIR / "stress_test" / f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                resp_filename = f"response_F001_{numero}.json"
                self.save_response(response, resp_filename, output_dir)
                
                # 5. Verificar log en BD (con reintentos pero sin prints)
                log_ok = await self._check_log_with_retry(str(numero))
                result["log_found"] = log_ok
                
                # 6. Generar PDF (siempre)
                pdf_data = invoice_data.copy()
                pdf_data.update({
                    "codigo_hash": response.get("codigo_hash"),
                    "cadena_para_codigo_qr": response.get("cadena_para_codigo_qr"),
                    "aceptada_por_sunat": response.get("aceptada_por_sunat", False),
                })
                
                from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
                pdf_generator = InvoicePDFGenerator(pdf_data)
                pdf_content = pdf_generator.generate_sync()
                
                pdf_filename = f"factura_F001_{numero}.pdf"
                pdf_path = output_dir / pdf_filename
                
                with open(pdf_path, "wb") as f:
                    f.write(pdf_content)
                
                result["pdf_path"] = str(pdf_path)
                result["success"] = True
                self.results["successful"] += 1
                
                # Solo mostrar éxito si es verbose
                # if self.verbose:
                #     print(f" ✅ [{numero}] {duration}ms")
                
            except Exception as e:
                result["error"] = str(e)
                self.results["other_errors"] += 1
                # if self.verbose:
                #     print(f" ❌ [{numero}] {str(e)[:30]}...")
            
            finally:
                self.results["total"] += 1
                self.results["details"].append(result)
            
            return result
    
    async def _check_log_with_retry(self, numero: str, max_retries: int = 2) -> bool:
        """
        Verifica el log en BD con reintentos (silencioso).
        """
        for attempt in range(max_retries):
            count = await sync_to_async(
                lambda: ApiCallLog.objects.filter(
                    response_data__contains=f'"{numero}"'
                ).count()
            )()
            
            if count > 0:
                return True
            
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
        
        return False
    
    async def run_stress_test(self, start_numero: int = 91500, count: int = 50, 
                              concurrency: int = 5, verbose: bool = False):
        """
        Ejecuta prueba de estrés con control de verbose.
        """
        self.verbose = verbose
        max_requests_per_minute = 180 
        
        print("\n" + "="*70)
        print(f"🧪 TEST STEP 4: PRUEBA DE ESTRÉS - {count} FACTURAS")
        print("="*70)
        print(f"\n📊 Configuración:")
        print(f"   Números: {start_numero} - {start_numero + count - 1}")
        print(f"   Concurrencia: {concurrency}")
        print(f"   Verbose: {'SÍ' if verbose else 'NO'}")
        print(f"   Inicio: {datetime.now().strftime('%H:%M:%S')}")
        
        if concurrency * 60 > max_requests_per_minute:
            print(
                f"⚠️ Concurrencia {concurrency} podría exceder límite de {max_requests_per_minute} rpm"
            )
        # Resetear resultados
        self.results = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "duplicate": 0,
            "other_errors": 0,
            "details": []
        }
        # Crear un chunk de números
        numeros = list(range(start_numero, start_numero + count))
        
        # Dividir en lotes según concurrencia
        batches = [numeros[i:i+concurrency] for i in range(0, len(numeros), concurrency)]
        
        start_time = time.time()
        
        for batch_num, batch in enumerate(batches):
            print(f"\n📦 Lote {batch_num + 1}/{len(batches)}: {batch[0]}-{batch[-1]}")
            
            # Crear tareas para este lote
            tasks = [self.send_single_invoice(num, asyncio.Semaphore(concurrency)) 
                    for num in batch]
            
            # Ejecutar lote completo
            await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Mostrar resumen
        self._show_summary(total_time, concurrency)
        self._save_results(start_numero, count, total_time)
        
        return self.results

    def _show_summary(self, total_time: float, concurrency: int):
        """
        Muestra resumen de la prueba de estrés.
        """
        print("\n" + "="*70)
        print("📊 RESUMEN DE PRUEBA DE ESTRÉS")
        print("="*70)
        print(f"\n📈 Estadísticas:")
        print(f"   Total facturas: {self.results['total']}")
        print(f"   ✅ Exitosas: {self.results['successful']}")
        print(f"   ❌ Fallidas: {self.results['failed']}")
        print(f"      ├─ Duplicados: {self.results['duplicate']}")
        print(f"      └─ Otros errores: {self.results['other_errors']}")
        print(f"\n⏱️  Tiempo total: {total_time:.2f}s")
        print(f"   Promedio por factura: {total_time/self.results['total']:.2f}s")
        print(f"   Facturas por segundo: {self.results['total']/total_time:.2f}")
        print(f"   Concurrencia: {concurrency}")
        
        if self.results['successful'] > 0:
            # Calcular tiempos de las exitosas
            successful_times = [r['duration_ms'] for r in self.results['details'] if r['success']]
            if successful_times:
                avg_time = sum(successful_times) / len(successful_times)
                min_time = min(successful_times)
                max_time = max(successful_times)
                print(f"\n⏱️  Tiempos de respuesta (éxitos):")
                print(f"   Mínimo: {min_time}ms")
                print(f"   Máximo: {max_time}ms")
                print(f"   Promedio: {avg_time:.0f}ms")
                
    def _save_results(self, start_numero: int, count: int, total_time: float):
        """
        Guarda resultados en archivo JSON.
        """
        output_dir = self.BASE_OUTPUT_DIR / "stress_test" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stress_report_{start_numero}_{count}_{timestamp}.json"
        filepath = output_dir / filename
        
        report = {
            "config": {
                "start_numero": start_numero,
                "count": count,
                "timestamp": timestamp
            },
            "summary": {
                "total": self.results["total"],
                "successful": self.results["successful"],
                "failed": self.results["failed"],
                "duplicate": self.results["duplicate"],
                "other_errors": self.results["other_errors"],
                "total_time_seconds": total_time,
                "requests_per_second": self.results["total"] / total_time
            },
            "details": self.results["details"]
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n📄 Reporte guardado en: {filepath}")

# En la función main, agregar opción --verbose
async def main():
    """Punto de entrada para ejecución manual."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Prueba de estrés NubeFact')
    parser.add_argument('--start', type=int, default=91500, help='Número inicial')
    parser.add_argument('--count', type=int, default=50, help='Cantidad de facturas')
    parser.add_argument('--concurrency', type=int, default=5, help='Peticiones simultáneas')
    parser.add_argument('--verbose', action='store_true', help='Mostrar progreso detallado')
    args = parser.parse_args()
    
    print(f"\n🚀 INICIANDO PRUEBA DE ESTRÉS")
    print(f"   {args.count} facturas desde {args.start}")
    print(f"   Concurrencia: {args.concurrency}")
    print(f"   Verbose: {'SÍ' if args.verbose else 'NO'} (los prints ralentizan)")
    
    test = TestNubefactStress()
    results = await test.run_stress_test(
        start_numero=args.start,
        count=min(args.count, 50),
        concurrency=args.concurrency,
        verbose=args.verbose
    )
    
    if results["successful"] == results["total"]:
        print(f"\n✅ PRUEBA DE ESTRÉS COMPLETADA EXITOSAMENTE")
        sys.exit(0)
    else:
        print(f"\n❌ PRUEBA DE ESTRÉS CON FALLOS")
        sys.exit(1)
        

if __name__ == "__main__":
    asyncio.run(main())