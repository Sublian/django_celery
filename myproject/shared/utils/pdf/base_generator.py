# apps/shared/utils/pdf/base_generator.py
from abc import ABC, abstractmethod
from django.template.loader import render_to_string
from io import BytesIO
import asyncio
from concurrent.futures import ThreadPoolExecutor


class BasePDFGenerator(ABC):
    """Clase base abstracta para todos los generadores de PDF"""

    def __init__(self, template_name, context=None):
        self.template_name = template_name
        self.context = context or {}

    @abstractmethod
    def get_template_context(self):
        """Método abstracto para obtener contexto específico"""
        pass

    def render_html(self):
        """Renderiza el template HTML con el contexto"""
        context = {**self.context, **self.get_template_context()}
        return render_to_string(self.template_name, context)

    @abstractmethod
    def generate_pdf(self, html_content):
        """Genera el PDF a partir del HTML"""
        pass

    def generate_sync(self):
        """Genera PDF de manera síncrona"""
        html = self.render_html()
        return self.generate_pdf(html)

    async def generate_async(self):
        """Genera PDF de manera asíncrona con weasyprint en un hilo separado"""
        html = self.render_html()
        loop = asyncio.get_event_loop()

        with ThreadPoolExecutor() as pool:
            pdf_bytes = await loop.run_in_executor(
                pool, lambda: self.generate_pdf(html)
            )
        return pdf_bytes
