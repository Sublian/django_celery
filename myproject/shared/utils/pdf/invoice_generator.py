# apps/shared/utils/pdf/invoice_generator.py
from .base_generator import BasePDFGenerator
from django.template.loader import render_to_string
# from xhtml2pdf import pisa
from weasyprint import HTML, CSS
from django.conf import settings
import os
from io import BytesIO
import qrcode
from django.conf import settings
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

class InvoicePDFGenerator(BasePDFGenerator):
    """Generador especializado para facturas electrónicas"""
    
    def __init__(self, invoice_data, template_name=None):
        # Si no se proporciona template_name, usar el de settings
        if template_name is None:
            from django.conf import settings
            template_name = settings.PDF_TEMPLATES.get('invoice', 'billing/factura_electronica.html')
            
        super().__init__(template_name, {'invoice_data': invoice_data})
        self.invoice_data = invoice_data
        self.qr_data = None
    
    def render_html(self):
        """Sobreescribir para asegurar que el contexto tenga company_info"""
        context = {**self.context, **self.get_template_context()}
        
        # Asegurar que company_info esté en el contexto
        if 'company_info' not in context:
            from django.conf import settings
            context['company_info'] = {
                'nombre': getattr(settings, 'COMPANY_NAME', 'Empresa'),
                'ruc': getattr(settings, 'COMPANY_RUC', '00000000000'),
                'direccion': getattr(settings, 'COMPANY_ADDRESS', ''),
                'telefono': getattr(settings, 'COMPANY_PHONE', ''),
                'email': getattr(settings, 'COMPANY_EMAIL', ''),
            }
        
        return render_to_string(self.template_name, context)
    
    def get_template_context(self):
        """Prepara el contexto específico para facturas"""
        # Procesar datos de la factura
        total_descuento = float(self.invoice_data.get('total_descuento', 0))
        total_gravada = float(self.invoice_data.get('total_gravada', 0))
        total_igv = float(self.invoice_data.get('total_igv', 0))
        total = float(self.invoice_data.get('total', 0))
        
        # Obtener items y dividirlos en páginas
        items = self.invoice_data.get('items', [])
        
        # Paginación: dividir items en grupos de 10
        ITEMS_PER_PAGE = 10
        paginated_items = []
        for i in range(0, len(items), ITEMS_PER_PAGE):
            paginated_items.append(items[i:i + ITEMS_PER_PAGE])
        
        # Generar QR si hay datos
        self.qr_data = self._generate_qr_data()
        
        return {
            'serie_numero': f"{self.invoice_data.get('serie')}-{self.invoice_data.get('numero')}",
            'cliente': self.invoice_data.get('cliente_denominacion'),
            'ruc_cliente': self.invoice_data.get('cliente_numero_de_documento'),
            'direccion_cliente': self.invoice_data.get('cliente_direccion'),
            'fecha_emision': self.invoice_data.get('fecha_de_emision'),
            'fecha_vencimiento': self.invoice_data.get('fecha_de_vencimiento'),
            
            # Items paginados
            'paginated_items': paginated_items,  # Lista de listas, cada una con máximo 10 items
            'total_pages': len(paginated_items),  # Número total de páginas de items
            
            
            'moneda': self._get_moneda_display(),
            # 'items': self.invoice_data.get('items', []),
            'items': items,  # Mantener la lista completa para cálculos, pero usar paginated_items en el template
            'totales': {
                'descuento': f"{total_descuento:.2f}",
                'gravada': f"{total_gravada:.2f}",
                'igv': f"{total_igv:.2f}",
                'total': f"{total:.2f}"
            },
            'observaciones': self.invoice_data.get('observaciones', ''),
            'condiciones_pago': self.invoice_data.get('condiciones_de_pago', ''),
            'qr_data': self.qr_data,
            'company_info': self._get_company_info()
        }
    
    def _generate_qr_data(self):
        """Genera datos para el código QR"""
        # Datos para el QR según SUNAT
        qr_info = {
            'ruc_emisor': settings.COMPANY_RUC,  # Configurar en settings
            'tipo_doc': self.invoice_data.get('tipo_de_comprobante'),
            'serie': self.invoice_data.get('serie'),
            'numero': self.invoice_data.get('numero'),
            'monto_total': self.invoice_data.get('total'),
            'fecha_emision': self.invoice_data.get('fecha_de_emision'),
        }
        return json.dumps(qr_info)
    
    def _get_moneda_display(self):
        """Convierte código de moneda a texto"""
        moneda_codes = {'1': 'SOLES', '2': 'DÓLARES'}
        return moneda_codes.get(self.invoice_data.get('moneda', '1'), 'SOLES')
    
    def _get_company_info(self):
        """Obtiene información de la empresa desde settings"""
        return {
            'nombre': settings.COMPANY_NAME,
            'ruc': settings.COMPANY_RUC,
            'direccion': settings.COMPANY_ADDRESS,
            'telefono': settings.COMPANY_PHONE,
            'email': settings.COMPANY_EMAIL,
        }
    
    def generate_pdf(self, html_content):
        """Implementación con WeasyPrint"""
        # 1. Crear objeto HTML con codificación UTF-8
        html_obj = HTML(string=html_content)
        
        # 2. Opcional: Añadir CSS específico para impresión/paginación
        # Ruta a un archivo CSS estático en tu proyecto Django
        css_path = os.path.join(settings.BASE_DIR, 'static', 'css', 'factura.css')
        css = CSS(filename=css_path)
        
        # También puedes combinar múltiples archivos CSS:
        # css2 = CSS(filename=os.path.join(settings.BASE_DIR, 'static', 'css', 'print.css'))
        
        # 3. Generar PDF
        try:
            pdf_bytes = html_obj.write_pdf(stylesheets=[css])    # , css2
            return pdf_bytes
        except Exception as e:
            print(f"[DEBUG] Primeros 500 chars del HTML: {html_content[:500]}...")
            raise Exception(f"Error al generar PDF con WeasyPrint: {str(e)}")