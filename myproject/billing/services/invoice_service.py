# myproject/billing/services/invoice_service.py
"""
Servicio de facturación electrónica unificado.
Integra envío a NubeFact, generación de PDF, logging y notificaciones.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from api_service.services.base.timeout_config import TimeoutConfig
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from shared.utils.file_manager import DocumentFileManager
from api_service.models import ApiCallLog
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class InvoiceService:
    """
    Servicio unificado para facturación electrónica.
    
    Maneja el flujo completo:
    1. Envío a NubeFact (async)
    2. Generación de PDF con QR
    3. Logging automático en ApiCallLog
    4. Gestión de archivos (opcional)
    
    Soporta modo individual y por lotes.
    """
    
    def __init__(self, timeout_config: Optional[TimeoutConfig] = None, verbose: bool = False):
        """
        Inicializa el servicio de facturación.
        
        Args:
            timeout_config: Configuración de timeouts (opcional)
            verbose: Modo verbose para debugging
        """
        self.nubefact_service = NubefactServiceAsync(timeout_config=timeout_config)
        self.nubefact_service.set_logging_mode(verbose=verbose)
        
        self.file_manager = DocumentFileManager(document_type='invoices')
        self.verbose = verbose
        
        # Directorio base para outputs
        self.output_base = Path(settings.MEDIA_ROOT) / "invoices" / "generated"
        self.output_base.mkdir(parents=True, exist_ok=True)
    
    def _log(self, message: str, level: str = "info"):
        """Log condicional según verbose."""
        if self.verbose:
            print(f"📄 [InvoiceService] {message}")
        else:
            getattr(logger, level)(message)
    
    async def process_invoice(
        self, 
        invoice_data: Dict[str, Any], 
        options: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Procesa una factura individual (flujo completo).
        
        Args:
            invoice_data: Datos de la factura (formato NubeFact)
            options: Opciones de procesamiento
                - generate_pdf: bool (generar PDF, default: True)
                - save_to_disk: bool (guardar en disco, default: True)
                - verbose: bool (logging detallado, default: False)
        
        Returns:
            Dict con resultado del procesamiento
        """
        start_time = datetime.now()
        
        # Opciones por defecto
        default_options = {
            "generate_pdf": True,
            "save_to_disk": True,
            "verbose": self.verbose
        }
        options = {**default_options, **(options or {})}
        
        result = {
            "success": False,
            "invoice_number": invoice_data.get("numero"),
            "serie": invoice_data.get("serie"),
            "nubefact_response": None,
            "pdf_path": None,
            "error": None,
            "error_code": None,
            "duration_ms": 0,
            "logs": []
        }
        
        try:
            self._log(f"Procesando factura {invoice_data.get('serie')}-{invoice_data.get('numero')}")
            
            # 1. Enviar a NubeFact
            nubefact_response = await self.nubefact_service.generar_comprobante(
                invoice_data,
                caller_context="invoice_service.process_invoice"
            )
            
            duration = int((datetime.now() - start_time).total_seconds() * 1000)
            result["duration_ms"] = duration
            result["nubefact_response"] = nubefact_response
            
            # 2. Verificar si es error (tiene campo 'codigo')
            if 'codigo' in nubefact_response:
                error_code = nubefact_response.get('codigo')
                error_msg = nubefact_response.get('errors', f'Error código {error_code}')
                
                result["error"] = error_msg
                result["error_code"] = error_code
                result["success"] = False
                
                self._log(f"❌ Error {error_code}: {error_msg}", "error")
                
                # Registrar en logs internos
                result["logs"].append({
                    "type": "error",
                    "code": error_code,
                    "message": error_msg
                })
                
                return result
            
            # 3. Éxito - actualizar datos con respuesta
            invoice_data.update({
                "codigo_hash": nubefact_response.get("codigo_hash"),
                "cadena_para_codigo_qr": nubefact_response.get("cadena_para_codigo_qr"),
                "enlace_del_pdf": nubefact_response.get("enlace_del_pdf"),
                "aceptada_por_sunat": nubefact_response.get("aceptada_por_sunat", False),
                "sunat_response": nubefact_response
            })
            
            result["success"] = True
            self._log(f"✅ Envío exitoso - Hash: {nubefact_response.get('codigo_hash', '')[:20]}...")
            
            # 4. Generar PDF si se solicita
            if options.get("generate_pdf"):
                pdf_path = await self._generate_pdf(invoice_data, options)
                result["pdf_path"] = str(pdf_path) if pdf_path else None
                
                if pdf_path:
                    self._log(f"📄 PDF generado: {pdf_path.name}")
            
            # 5. Guardar en disco si se solicita
            if options.get("save_to_disk") and options.get("generate_pdf"):
                await self._save_to_disk(invoice_data, nubefact_response, result["pdf_path"])
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            result["error"] = error_msg
            result["success"] = False
            
            self._log(f"❌ Excepción: {error_msg}", "error")
            
            return result
    
    async def _generate_pdf(self, invoice_data: Dict[str, Any], options: Dict) -> Optional[Path]:
        """
        Genera PDF con QR para la factura.
        """
        try:
            # Determinar template
            template_name = invoice_data.get(
                'template', 
                settings.PDF_TEMPLATES.get('invoice', 'billing/factura_electronica.html')
            )
            
            # Generar PDF
            pdf_generator = InvoicePDFGenerator(invoice_data, template_name)
            pdf_content = pdf_generator.generate_sync()  # Usar sync por simplicidad
            
            # Crear nombre de archivo
            filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = self.output_base / filename
            
            # Guardar
            with open(filepath, "wb") as f:
                f.write(pdf_content)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            return None
    
    async def _save_to_disk(self, invoice_data: Dict, nubefact_response: Dict, pdf_path: Optional[str]):
        """
        Guarda respuesta y PDF en disco usando file_manager.
        """
        try:
            # Guardar respuesta JSON
            response_filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            await sync_to_async(self.file_manager.save_json)(
                nubefact_response, 
                response_filename, 
                invoice_data
            )
            
            # Guardar PDF si existe
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    pdf_content = f.read()
                
                await sync_to_async(self.file_manager.save_pdf)(
                    pdf_content, 
                    invoice_data
                )
                
        except Exception as e:
            logger.error(f"Error guardando en disco: {e}")
    
    async def check_status(self, numero: str) -> Dict[str, Any]:
        """
        Consulta estado de una factura en NubeFact.
        """
        try:
            # Buscar en logs locales primero
            log = await sync_to_async(
                lambda: ApiCallLog.objects.filter(
                    response_data__contains=f'"{numero}"'
                ).order_by('-created_at').first()
            )()
            
            if log:
                return {
                    "found": True,
                    "status": log.status,
                    "response_code": log.response_code,
                    "created_at": log.created_at,
                    "response_data": log.response_data
                }
            
            # Si no está en logs, consultar a NubeFact
            response = await self.nubefact_service.consultar_comprobante(
                numero,
                caller_context="invoice_service.check_status"
            )
            
            return {
                "found": True,
                "status": "CONSULTED",
                "response": response
            }
            
        except Exception as e:
            return {
                "found": False,
                "error": str(e)
            }
    
    async def close(self):
        """Cierra el servicio y sus recursos."""
        await self.nubefact_service.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Funciones de conveniencia para uso rápido
async def process_single_invoice(
    invoice_data: Dict[str, Any],
    generate_pdf: bool = True,
    save_to_disk: bool = True
) -> Dict[str, Any]:
    """
    Función de conveniencia para procesar una factura individual.
    """
    async with InvoiceService() as service:
        return await service.process_invoice(
            invoice_data,
            options={
                "generate_pdf": generate_pdf,
                "save_to_disk": save_to_disk
            }
        )


def process_single_invoice_sync(
    invoice_data: Dict[str, Any],
    generate_pdf: bool = True,
    save_to_disk: bool = True
) -> Dict[str, Any]:
    """
    Versión síncrona de process_single_invoice.
    """
    return asyncio.run(process_single_invoice(invoice_data, generate_pdf, save_to_disk))