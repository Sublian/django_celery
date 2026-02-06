# apps/invoices/services.py
import os
import asyncio
from django.conf import settings
from django.core.files.base import ContentFile
from shared.utils.file_manager import DocumentFileManager
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from api_service.services.nubefact.client import NubefactClient


class InvoiceService:
    """Servicio para manejo de facturas"""

    def __init__(self):
        self.nubefact_client = NubefactClient()
        # self.pdf_generator = None
        self.file_manager = DocumentFileManager(document_type="invoices")

    async def create_invoice(self, invoice_data, generate_pdf=True, save_to_disk=True):
        """Crea una factura completa (envía a Nubefact y genera PDF)"""
        try:
            # 1. Enviar a Nubefact
            nubefact_response = await self.nubefact_client.send_invoice(invoice_data)

            if not nubefact_response.get("success"):
                raise Exception(f"Error Nubefact: {nubefact_response.get('errors')}")

            # 2. Actualizar datos con respuesta de Nubefact
            invoice_data.update(
                {
                    "codigo_unico": nubefact_response.get("codigo_hash"),
                    "qr_url": nubefact_response.get("cadena_para_codigo_qr"),
                    "xml_url": nubefact_response.get("enlace_del_xml"),
                    "enlace_del_pdf": nubefact_response.get("enlace_del_pdf"),
                    "sunat_response": nubefact_response,
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

            # 4. Guardar en disco si se solicita
            storage_result = None
            if save_to_disk and pdf_content:
                storage_result = self.file_manager.save_pdf(pdf_content, invoice_data)

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
