# myproject/billing/utils/file_manager.py
import os
from datetime import datetime, timedelta
from django.conf import settings
import json
import hashlib
from pathlib import Path


class DocumentFileManager:
    """Gestor de archivos para documentos"""

    def __init__(self, document_type="invoices"):
        self.document_type = document_type
        self.base_dir = settings.DOCUMENT_STORAGE["BASE_DIR"]
        self.structure = settings.DOCUMENT_STORAGE["STRUCTURE"]

    def get_storage_path(self, filename=None, subfolder="", create_if_not_exists=True):
        """Obtiene la ruta de almacenamiento para un documento"""
        now = datetime.now()

        # Obtener template de path para el tipo de documento
        path_template = self.structure.get(
            self.document_type, self.structure["invoices"]
        )

        # Reemplazar variables
        path = path_template.format(
            year=now.strftime("%Y"),
            month=now.strftime("%m"),
            date=now.strftime("%Y%m%d"),
        )

        # Agregar subcarpeta si existe
        if subfolder:
            path = os.path.join(path, subfolder)

        full_path = os.path.join(self.base_dir, path)

        # Crear directorios si no existen
        if create_if_not_exists:
            os.makedirs(full_path, exist_ok=True)

        # Si se proporciona nombre de archivo, devolver ruta completa
        if filename:
            return os.path.join(full_path, filename)

        return full_path

    def save_pdf(self, pdf_content, invoice_data, filename=None):
        """Guarda un PDF y sus metadatos"""
        try:
            # Generar nombre de archivo si no se proporciona
            if not filename:
                serie = invoice_data.get("serie", "F001")
                numero = invoice_data.get("numero", "000000")
                filename = f"{serie}-{numero}.pdf"

            # Obtener ruta de almacenamiento
            pdf_path = self.get_storage_path(filename)

            # Guardar PDF
            with open(pdf_path, "wb") as pdf_file:
                pdf_file.write(pdf_content)

            # Guardar metadatos
            metadata = self._generate_metadata(invoice_data, pdf_path)
            self.save_metadata(metadata, filename)

            # Guardar registro en base de datos si es necesario
            self._save_to_database(invoice_data, pdf_path)

            return {
                "success": True,
                "pdf_path": pdf_path,
                "filename": filename,
                "metadata": metadata,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_metadata(self, metadata, filename):
        """Guarda metadatos en JSON"""
        metadata_filename = f"{os.path.splitext(filename)[0]}_metadata.json"
        metadata_path = self.get_storage_path(metadata_filename, subfolder="metadata")

        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=2, ensure_ascii=False)

        return metadata_path

    def _generate_metadata(self, invoice_data, pdf_path):
        """Genera metadatos del documento"""
        # Calcular hash del archivo
        file_hash = self._calculate_file_hash(pdf_path)

        metadata = {
            "document_info": {
                "type": self.document_type,
                "serie": invoice_data.get("serie"),
                "numero": invoice_data.get("numero"),
                "issue_date": invoice_data.get("fecha_de_emision"),
                "total": invoice_data.get("total"),
                "currency": invoice_data.get("moneda"),
                "unique_code": invoice_data.get("codigo_unico", ""),
            },
            "client_info": {
                "document_type": invoice_data.get("cliente_tipo_de_documento"),
                "document_number": invoice_data.get("cliente_numero_de_documento"),
                "name": invoice_data.get("cliente_denominacion"),
            },
            "file_info": {
                "filename": os.path.basename(pdf_path),
                "path": pdf_path,
                "size_bytes": os.path.getsize(pdf_path),
                "created_at": datetime.now().isoformat(),
                "file_hash": file_hash,
                "mime_type": "application/pdf",
            },
            "system_info": {
                "generated_by": "billing_module",
                "template_used": invoice_data.get("template", "default"),
                "version": "1.0",
            },
        }

        return metadata

    def _calculate_file_hash(self, file_path):
        """Calcula hash SHA-256 del archivo"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _save_to_database(self, invoice_data, pdf_path):
        """Guarda referencia en base de datos (si tienes modelos)"""
        # Esto es opcional - depende si tienes modelos para documentos
        try:
            from .models import (
                InvoiceDocument,
            )  # Importar aquí para evitar circular imports

            InvoiceDocument.objects.create(
                serie=invoice_data.get("serie"),
                numero=invoice_data.get("numero"),
                file_path=pdf_path,
                client_document=invoice_data.get("cliente_numero_de_documento"),
                total_amount=invoice_data.get("total"),
                issue_date=invoice_data.get("fecha_de_emision"),
                storage_type=self.document_type,
            )
        except ImportError:
            # No hay modelos definidos aún
            pass

    def get_document_url(self, file_path):
        """Genera URL para acceder al documento (si sirves archivos estáticos)"""
        # Convertir path absoluto a relativo para URL
        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        return f"{settings.MEDIA_URL}{relative_path}"

    def cleanup_old_files(self, document_type=None):
        """Limpia archivos antiguos según política de retención"""
        doc_type = document_type or self.document_type
        retention_days = settings.DOCUMENT_STORAGE["RETENTION_DAYS"].get(doc_type, 365)

        cutoff_date = datetime.now() - timedelta(days=retention_days)

        # Implementar lógica para borrar archivos antiguos
        # (Cuidado: Esto borra archivos permanentemente)
        pass
