# tests/integration/nubefact_flow/test_service.py

"""
Servicio unificado para pruebas de NubeFact.
Integra todas las funcionalidades probadas.
"""

import os
import sys
import django

# ✅ Configurar Django ANTES de cualquier otra importación
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# Ahora sí, el resto de importaciones
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import StressTestConfig, DevelopmentConfig, ProductionConfig
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from api_service.services.base.timeout_config import TimeoutConfig
from .base_test import NubefactTestBase
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator


class NubefactTestService:
    """
    Servicio de pruebas unificado con las mejores prácticas identificadas.
    """
    
    def __init__(self, config: Optional[StressTestConfig] = None):
        self.config = config or DevelopmentConfig()
        self.service = NubefactServiceAsync(
            timeout_config=self.config.timeout_config
        )
        self.service.set_logging_mode(verbose=self.config.verbose)
        
        self.results = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "duplicate": 0,
            "other_errors": 0,
            "details": []
        }
        self.start_time = None  # ✅ Inicializar aquí
    
    async def send_invoice(self, numero: int) -> Dict[str, Any]:
        """
        Envía una factura individual con la configuración actual.
        Versión corregida con manejo de rutas.
        """
        start_time = time.time()
        result = {
            "numero": numero,
            "success": False,
            "error": None,
            "duration_ms": 0,
            "pdf_path": None,
            "error_code": None
        }
        
        try:
            # Crear datos de factura
            invoice_data = NubefactTestBase.create_test_invoice_data(str(numero))
            
            # Enviar a NubeFact
            response = await self.service.generar_comprobante(
                invoice_data,
                caller_context="nubefact_test_service"
            )
            
            duration = int((time.time() - start_time) * 1000)
            result["duration_ms"] = duration
            
            # ✅ VERIFICAR SI ES ERROR (tiene campo 'codigo')
            if 'codigo' in response:
                error_code = response.get('codigo')
                result["error_code"] = error_code
                result["success"] = False
                
                if error_code == 23:
                    result["error"] = "Documento duplicado"
                    self.results["duplicate"] += 1
                else:
                    error_msg = response.get('errors', f'Error código {error_code}')
                    result["error"] = error_msg
                    self.results["other_errors"] += 1
                
                if self.config.verbose:
                    print(f"⚠️ Factura {numero} - Error {error_code}: {result['error'][:50]}")
                return result
            
            # ✅ SI NO HAY 'codigo', ES ÉXITO
            result["success"] = True
            self.results["successful"] += 1
            
            # ✅ Crear directorio para esta ejecución (UNA SOLA VEZ)
            batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            batch_dir = Path(self.config.output_base) / f"batch_{batch_timestamp}"
            batch_dir.mkdir(parents=True, exist_ok=True)
            
            # Guardar respuesta (solo si verbose o para debugging)
            if self.config.verbose:
                resp_path = batch_dir / f"response_F001_{numero}.json"
                # ✅ Pasar solo el directorio, no la ruta completa
                NubefactTestBase.save_response(response, f"response_F001_{numero}.json", batch_dir)
                
                # Generar PDF
                pdf_data = invoice_data.copy()
                pdf_data.update({
                    "codigo_hash": response.get("codigo_hash"),
                    "cadena_para_codigo_qr": response.get("cadena_para_codigo_qr"),
                    "aceptada_por_sunat": response.get("aceptada_por_sunat", False),
                })
                
                pdf_generator = InvoicePDFGenerator(pdf_data)
                pdf_content = pdf_generator.generate_sync()
                
                pdf_path = batch_dir / f"factura_F001_{numero}.pdf"
                with open(pdf_path, "wb") as f:
                    f.write(pdf_content)
                
                result["pdf_path"] = str(pdf_path)
                print(f"✅ Factura {numero} exitosa - {duration}ms")
            
        except Exception as e:
            result["error"] = str(e)
            self.results["other_errors"] += 1
            if self.config.verbose:
                print(f"❌ Factura {numero}: {str(e)}")
        
        finally:
            self.results["total"] += 1
            self.results["details"].append(result)
        
        return result
        
    async def run_stress_test(self) -> Dict[str, Any]:
        """
        Ejecuta prueba de estrés con la configuración actual.
        """
        print("\n" + "="*70)
        print(f"🧪 PRUEBA DE ESTRÉS - {self.config.count} FACTURAS")
        print("="*70)
        print(f"\n📊 Configuración:")
        print(f"   Verbose: {self.config.verbose}")
        print(f"   Check logs: {self.config.check_logs}")
        print(f"   Concurrencia: {self.config.concurrency}")
        print(f"   Timeouts: connect={self.config.connect_timeout}s, read={self.config.read_timeout}s")
        
        # ✅ Crear directorio base para este batch
        batch_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.batch_dir = Path(self.config.output_base) / f"batch_{batch_timestamp}"
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        
        numeros = range(self.config.start_numero, self.config.start_numero + self.config.count)
        batches = [numeros[i:i+self.config.concurrency] 
                for i in range(0, len(numeros), self.config.concurrency)]
        
        self.start_time = time.time()
        
        for batch_num, batch in enumerate(batches):
            if self.config.verbose:
                print(f"\n📦 Lote {batch_num + 1}/{len(batches)}: {batch[0]}-{batch[-1]}")
            
            tasks = [self.send_invoice(num) for num in batch]
            await asyncio.gather(*tasks)
        
        total_time = time.time() - self.start_time
        
        self._show_summary(total_time)
        self._save_results(total_time)
        
        # Mostrar resumen detallado
        if self.results["successful"] > 0:
            print(f"\n✅ Facturas exitosas: {self.results['successful']}")
        if self.results["duplicate"] > 0:
            print(f"⚠️ Facturas duplicadas: {self.results['duplicate']}")
        if self.results["other_errors"] > 0:
            print(f"❌ Otros errores: {self.results['other_errors']}")
        
        return self.results
    
    def _show_summary(self, total_time: float):
        """Muestra resumen de la prueba."""
        print("\n" + "="*70)
        print("📊 RESUMEN DE PRUEBA DE ESTRÉS")
        print("="*70)
        print(f"\n📈 Estadísticas:")
        print(f"   Total facturas: {self.results['total']}")
        print(f"   ✅ Exitosas: {self.results['successful']}")
        print(f"   ❌ Fallidas: {self.results['failed']}")
        print(f"   ├─ Duplicados: {self.results['duplicate']}")
        print(f"   └─ Otros errores: {self.results['other_errors']}")
        print(f"\n⏱️  Tiempo total: {total_time:.2f}s")
        if self.results['total'] > 0:
            print(f"   Promedio por factura: {total_time/self.results['total']:.2f}s")
            print(f"   Facturas por segundo: {self.results['total']/total_time:.2f}")
        print(f"   Concurrencia: {self.config.concurrency}")
    
    def _save_results(self, total_time: float):
        """Guarda resultados en archivo JSON."""
        # ✅ Usar el mismo batch_dir que para las respuestas
        filename = f"stress_report_{self.config.start_numero}_{self.config.count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.batch_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "config": {
                    "start_numero": self.config.start_numero,
                    "count": self.config.count,
                    "concurrency": self.config.concurrency,
                    "verbose": self.config.verbose,
                    "check_logs": self.config.check_logs
                },
                "summary": {
                    "total": self.results["total"],
                    "successful": self.results["successful"],
                    "failed": self.results["failed"],
                    "duplicate": self.results["duplicate"],
                    "other_errors": self.results["other_errors"],
                    "total_time_seconds": total_time
                },
                "details": self.results["details"]
            }, f, indent=2, default=str)
        
        print(f"\n📄 Reporte guardado en: {filepath}")
        
# Función principal unificada
async def main():
    """Punto de entrada unificado para pruebas."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Servicio de pruebas NubeFact')
    parser.add_argument('--mode', choices=['dev', 'prod', 'stress'], default='dev',
                       help='Modo de ejecución')
    parser.add_argument('--start', type=int, default=91500, help='Número inicial')
    parser.add_argument('--count', type=int, default=50, help='Cantidad de facturas')
    parser.add_argument('--concurrency', type=int, default=10, help='Concurrencia')
    args = parser.parse_args()
    
    # Seleccionar configuración
    if args.mode == 'dev':
        config = DevelopmentConfig(
            start_numero=args.start,
            count=args.count,
            concurrency=args.concurrency
        )
    elif args.mode == 'prod':
        config = ProductionConfig(
            start_numero=args.start,
            count=args.count,
            concurrency=args.concurrency
        )
    else:  # stress
        config = StressTestConfig(
            start_numero=args.start,
            count=args.count,
            concurrency=args.concurrency
        )
    
    service = NubefactTestService(config)
    results = await service.run_stress_test()
    
    if results["successful"] == results["total"]:
        print(f"\n✅ PRUEBA COMPLETADA EXITOSAMENTE")
        return 0
    else:
        print(f"\n⚠️ PRUEBA COMPLETADA CON FALLOS")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))