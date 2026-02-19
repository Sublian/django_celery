# apps/invoices/services.py
from datetime import datetime
import os
import asyncio
from asgiref.sync import sync_to_async

from django.conf import settings
from django.core.files.base import ContentFile

from shared.utils.file_manager import DocumentFileManager
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from asgiref.sync import sync_to_async


class InvoiceService:
    """Servicio para manejo de facturas"""

    def __init__(self):
        self.nubefact_service = None
        self.file_manager = DocumentFileManager(document_type="invoices")

    async def _get_nubefact_service(self):
        """Inicializa el servicio NubeFact de forma asíncrona"""
        if self.nubefact_service is None:
            # Usar sync_to_async para llamar al __init__ sincrónico
            self.nubefact_service = await sync_to_async(NubefactServiceAsync)()
        return self.nubefact_service

    async def create_invoice(
        self, invoice_data, generate_pdf=True, save_to_disk=True, caller_info=None
    ):
        """Crea una factura completa (envía a Nubefact y genera PDF)
        Args:
            invoice_data: Datos de la factura
            generate_pdf: Generar PDF local
            save_to_disk: Guardar en disco
            caller_info: Información de quién está llamando (NUEVO)
        """
        try:
            # 0. Obtener servicio NubeFact de forma asíncrona
            nubefact_service = await self._get_nubefact_service()

            # 1. Enviar a Nubefact
            print(
                f"📤 Enviando a NubeFact: {invoice_data.get('serie')}-{invoice_data.get('numero')}"
            )

            if caller_info is None:
                caller_info = self._determine_caller_context()
            print(f"📤 Enviando a NubeFact desde: {caller_info}")

            # Opción A: Agregar como campo especial en el payload
            invoice_data_with_context = invoice_data.copy()
            invoice_data_with_context["_metadata"] = {
                "called_from": caller_info,
                "timestamp": datetime.now().isoformat(),
            }

            nubefact_response = await nubefact_service.generar_comprobante(
                invoice_data_with_context
            )

            if not nubefact_response.get("success"):
                raise Exception(f"Error Nubefact: {nubefact_response.get('errors')}")

            invoice_number = nubefact_response.get("numero")
            codigo_hash = nubefact_response.get("codigo_hash")
            cadena_qr = nubefact_response.get("cadena_para_codigo_qr")
            print(f"✅ Factura {invoice_number} creada en NubeFact")
            print(f"   Hash: {codigo_hash[:30]}...")
            print(f"   QR: {cadena_qr[:30]}...")

            # 2. Actualizar datos con respuesta de Nubefact
            invoice_data.update(
                {
                    "codigo_unico": nubefact_response.get("codigo_hash"),
                    "qr_url": nubefact_response.get("cadena_para_codigo_qr"),
                    "xml_url": nubefact_response.get("enlace_del_xml"),
                    "enlace_del_pdf": nubefact_response.get("enlace_del_pdf"),
                    "sunat_response": nubefact_response,
                    "numero": nubefact_response.get("numero"),
                }
            )

            # 3. Generar PDF local si se solicita
            pdf_content = None
            if generate_pdf:
                # Determinar qué template usar
                template_name = invoice_data.get(
                    "template", settings.PDF_TEMPLATES["invoice"]
                )
                pdf_generator = InvoicePDFGenerator(invoice_data, template_name)
                pdf_content = await pdf_generator.generate_async()
                print(
                    f"✅ PDF generado: {len(pdf_content) if pdf_content else 0} bytes"
                )

            # 4. Guardar en disco si se solicita
            storage_result = None
            if save_to_disk and pdf_content:
                storage_result = self.file_manager.save_pdf(pdf_content, invoice_data)
                print(f"✅ PDF guardado: {storage_result.get('pdf_path', 'N/A')}")

            return {
                "success": True,
                "nubefact_response": nubefact_response,
                "pdf_content": pdf_content if not save_to_disk else None,
                "storage_result": storage_result,
                "invoice_data": invoice_data,
                "download_url": (
                    storage_result.get("pdf_path") if storage_result else None
                ),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_pdf_only(self, invoice_data):
        """Genera solo el PDF sin enviar a Nubefact"""
        generator = InvoicePDFGenerator(invoice_data)
        return generator.generate_sync()

    def _determine_caller_context(self):
        """
        Intenta determinar automáticamente quién está llamando
        revisando el stack de llamadas
        """
        import inspect
        import traceback

        try:
            # Obtener el stack de llamadas
            stack = inspect.stack()

            # Buscar en el stack llamadas interesantes
            for frame_info in stack:
                filename = frame_info.filename
                function = frame_info.function

                # Identificar patrones comunes
                if "invoice_service" in filename:
                    return f"InvoiceService.{function}"
                elif "batch_invoice_service" in filename:
                    return f"BatchInvoiceService.{function}"
                elif "views.py" in filename:
                    # Es una vista de Django
                    return f"View.{function}"
                elif "test_" in filename:
                    # Es una prueba
                    return f"Test.{filename.split('/')[-1]}"

            # Si no encontramos nada específico
            return f"unknown.{stack[2].function if len(stack) > 2 else 'unknown'}"

        except Exception:
            return "unknown.could_not_determine"
