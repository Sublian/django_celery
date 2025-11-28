# billing/services/invoice_processing_service.py
from decimal import Decimal
import logging
from django.db import transaction
from django.utils import timezone
from ..models import AccountMove

logger = logging.getLogger(__name__)

class InvoiceProcessingService:
    """
    Servicio para procesar facturas (postear, cancelar, etc.)
    """
    
    def __init__(self, company_id=None):
        self.company_id = company_id
    
    def post_draft_invoices(self, invoice_ids=None):
        """
        Cambiar facturas de draft a posted
        """
        invoices = AccountMove.objects.filter(state='draft')
        
        if self.company_id:
            invoices = invoices.filter(company_id=self.company_id)
        
        if invoice_ids:
            invoices = invoices.filter(id__in=invoice_ids)
        
        posted_count = 0
        failed_count = 0
        
        for invoice in invoices:
            # Validar antes de postear
            validation = self._calculate_invoice_with_debug(invoice)
            
            if validation['is_consistent']:
                try:
                    with transaction.atomic():
                        invoice.state = 'posted'
                        invoice.save()
                        posted_count += 1
                        logger.info(f"📄 Factura {invoice.invoice_number} posteada")
                        
                except Exception as e:
                    logger.error(f"❌ Error posteando factura {invoice.id}: {str(e)}")
                    failed_count += 1
            else:
                logger.warning(
                    f"⚠️ Factura {invoice.invoice_number} no posteada - "
                    f"Inconsistencia: ${validation['discrepancy']:.4f}"
                )
                failed_count += 1
        
        return {
            'posted': posted_count,
            'failed': failed_count,
            'total_processed': posted_count + failed_count
        }
    
    def fix_invoice_totals(self, invoice_ids=None):
        """
        Corregir automáticamente los totales de facturas inconsistentes
        """
        invoices = AccountMove.objects.filter(state='draft')
        
        if self.company_id:
            invoices = invoices.filter(company_id=self.company_id)
        
        if invoice_ids:
            invoices = invoices.filter(id__in=invoice_ids)
        
        fixed_count = 0
        
        for invoice in invoices:
            validation = self._calculate_invoice_with_debug(invoice)
            
            if not validation['is_consistent']:
                # Corregir totales
                invoice.amount_total = validation['theoretical_total']
                
                # Recalcular impuestos totales
                total_tax = Decimal('0')
                for line_detail in validation['line_details']:
                    total_tax += Decimal(str(line_detail['tax_amount']))
                
                invoice.amount_tax = total_tax
                invoice.save()
                
                fixed_count += 1
                logger.info(
                    f"🔧 Factura {invoice.invoice_number} corregida: "
                    f"${invoice.amount_total:.2f} (antes: ${validation['actual_total']:.2f})"
                )
        
        return fixed_count
    
    def validate_invoice_totals(self, invoice_ids=None):
        """
        Validar que los totales de las facturas sean consistentes
        """
        invoices = AccountMove.objects.filter(state='draft')
        
        if self.company_id:
            invoices = invoices.filter(company_id=self.company_id)
        
        if invoice_ids:
            invoices = invoices.filter(id__in=invoice_ids)
        
        validation_results = []
        
        for invoice in invoices.select_related('subscription').prefetch_related('lines'):
            debug_info = self._calculate_invoice_with_debug(invoice)
            
            validation_results.append({
                'invoice': invoice.invoice_number,
                'theoretical_total': debug_info['theoretical_total'],
                'actual_total': invoice.amount_total,
                'discrepancy': debug_info['discrepancy'],
                'is_consistent': debug_info['is_consistent'],
                'subscription': invoice.subscription.code if invoice.subscription else None,
                'debug_info': debug_info['line_details']
            })

        return validation_results
    
    def _calculate_invoice_with_debug(self, invoice):
        """
        Calcular totales con información de debug
        """
        theoretical_total = Decimal('0')
        line_details = []
        
        for line in invoice.lines.all():
            # Calcular subtotal sin impuestos
            subtotal = line.quantity * line.price_unit * (1 - line.discount / 100)
            
            # Calcular impuestos
            tax_amount = Decimal('0')
            tax_details = []
            for tax in line.tax.all():
                if tax.amount_type == 'percent':
                    tax_calc = subtotal * (tax.amount / 100)
                    tax_amount += tax_calc
                    tax_details.append(f"{tax.name}: {tax.amount}% = ${tax_calc:.2f}")
            
            line_total = subtotal + tax_amount
            theoretical_total += line_total
            
            line_details.append({
                'product': line.product.name,
                'quantity': float(line.quantity),
                'price_unit': float(line.price_unit),
                'discount': float(line.discount),
                'subtotal': float(subtotal),
                'taxes': tax_details,
                'tax_amount': float(tax_amount),
                'line_total': float(line_total)
            })
        
        discrepancy = abs(invoice.amount_total - theoretical_total)
        is_consistent = discrepancy < Decimal('0.01')  # Tolerancia de 1 céntimo
        
        return {
            'theoretical_total': theoretical_total,
            'discrepancy': discrepancy,
            'is_consistent': is_consistent,
            'line_details': line_details
        }
        
        
        