# billing/services/batch_invoice_service.py
import logging
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, F, ExpressionWrapper, DecimalField
from decimal import Decimal

from ..models import (
    SaleSubscription, 
    AccountMove, 
    AccountMoveLine,
    InvoiceSerie,
    Product,
    Tax,
    Company,
    Currency,
    Journal,
    Partner,
    ContractTemplate,
    Sequence
)

logger = logging.getLogger(__name__)

class BatchInvoiceService:
    """
    Servicio para generar facturas en lote para suscripciones recurrentes
    """
    
    def __init__(self, company_id=None):
        self.company_id = company_id
        self.today = timezone.now().date()
        self.stats = {
            'processed': 0,
            'created': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def generate_batch_invoices(self, target_date=None, subscription_ids=None):
        """
        Genera facturas en lote para suscripciones que requieren facturación
        
        Args:
            target_date (date): Fecha objetivo para facturación (default: hoy)
            subscription_ids (list): IDs específicos de suscripciones (opcional)
        
        Returns:
            dict: Estadísticas del proceso
        """
        target_date = target_date or self.today
        logger.info(f"Iniciando generación de facturas en lote para {target_date}")
        
        try:
            # Obtener suscripciones elegibles
            subscriptions = self._get_eligible_subscriptions(target_date, subscription_ids)
            logger.info(f"Encontradas {len(subscriptions)} suscripciones elegibles")
            
            # Procesar cada suscripción
            for subscription in subscriptions:
                self._process_subscription_invoice(subscription, target_date)
            
            logger.info(f"Proceso completado: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Error en generación de facturas en lote: {str(e)}")
            self.stats['errors'] += 1
            return self.stats
    
    def _get_eligible_subscriptions(self, target_date, subscription_ids=None):
        """
        Obtiene suscripciones elegibles para facturación
        """
        base_query = SaleSubscription.objects.filter(
            Q(state='active') | Q(state='in_renewal'),
            is_active=True,
            next_invoice_date__lte=target_date,
            company_id=self.company_id
        ).select_related(
            'partner',
            'company',
            'contract_template'
        ).prefetch_related(
            'lines',
            'lines__product',
            'lines__tax_ids'
        )
        
        if subscription_ids:
            base_query = base_query.filter(id__in=subscription_ids)
        
        return base_query
    
    def _process_subscription_invoice(self, subscription, target_date):
        """
        Procesa la generación de factura para una suscripción individual
        """
        self.stats['processed'] += 1
        
        try:
            with transaction.atomic():
                # Verificar si ya existe factura para este período
                if self._invoice_exists_for_period(subscription, target_date):
                    logger.info(f"Factura ya existe para subscripción {subscription.id} en {target_date}")
                    self.stats['skipped'] += 1
                    return
                
                # Crear factura
                invoice = self._create_invoice_from_subscription(subscription, target_date)
                
                # Crear líneas de factura
                self._create_invoice_lines(invoice, subscription)
                
                # Calcular totales
                self._calculate_invoice_totals(invoice)
                
                # Actualizar suscripción
                self._update_subscription_after_invoice(subscription, invoice, target_date)
                
                self.stats['created'] += 1
                logger.info(f"Factura {invoice.id} creada para suscripción {subscription.id}")
                
        except Exception as e:
            logger.error(f"Error procesando suscripción {subscription.id}: {str(e)}")
            self.stats['errors'] += 1
    
    def _invoice_exists_for_period(self, subscription, target_date):
        """
        Verifica si ya existe una factura para el período
        """
        return AccountMove.objects.filter(
            subscription=subscription,
            invoice_date__year=target_date.year,
            invoice_date__month=target_date.month,
            state__in=['draft', 'posted']
        ).exists()
    
    def _create_invoice_from_subscription(self, subscription, target_date):
        """
        Crea la cabecera de la factura desde la suscripción
        """
        # Obtener serie de facturación
        invoice_serie = self._get_invoice_serie(subscription.company)
        
        # Obtener siguiente número de referencia
        reference = invoice_serie.get_next_reference() if invoice_serie.sequence else None
        
        # Crear factura
        invoice = AccountMove.objects.create(
            partner=subscription.partner,
            subscription=subscription,
            company=subscription.company,
            currency=subscription.company.currency or Currency.objects.first(),
            journal=self._get_default_journal(subscription.company),
            type='out_invoice',
            state='draft',
            invoice_date=target_date,
            invoice_date_due=self._calculate_due_date(target_date, subscription),
            serie=invoice_serie,
            invoice_number=reference,
            ref=f"SUB-{subscription.code or subscription.id}-{target_date.strftime('%Y%m')}",
            narration=f"Factura recurrente - {subscription.description or 'Suscripción'}",
            billing_type='subscription'
        )
        
        return invoice
    
    def _get_invoice_serie(self, company):
        """
        Obtiene la serie de facturación para la compañía
        """
        try:
            return InvoiceSerie.objects.filter(
                company=company,
                is_active=True,
                journal__type='sale'
            ).first()
        except InvoiceSerie.DoesNotExist:
            logger.error(f"No se encontró serie de facturación para compañía {company.id}")
            raise
    
    def _get_default_journal(self, company):
        """
        Obtiene el diario por defecto para ventas
        """
        try:
            return Journal.objects.filter(
                company=company,
                type='sale',
                is_active=True
            ).first()
        except Journal.DoesNotExist:
            logger.error(f"No se encontró diario de ventas para compañía {company.id}")
            raise
    
    def _calculate_due_date(self, invoice_date, subscription):
        """
        Calcula la fecha de vencimiento basada en términos de pago
        """
        # Por defecto, 30 días después
                # Calcular próxima fecha de facturación
        if subscription.contract_template:
            return  subscription.contract_template.get_next_invoice_date(invoice_date)
            
        # Lógica por defecto: mensual
        return invoice_date + timedelta(days=30)
    
    def _create_invoice_lines(self, invoice, subscription):
        """
        Crea las líneas de factura desde las líneas de suscripción
        """
        for sub_line in subscription.lines.all():
            # Calcular precio unitario con descuento
            price_unit = sub_line.price_unit * (1 - sub_line.discount / 100)
            
            # Crear línea de factura
            invoice_line = AccountMoveLine.objects.create(
                move=invoice,
                product=sub_line.product,
                quantity=sub_line.quantity,
                price_unit=price_unit,
                discount=sub_line.discount,
                subtotal=sub_line.quantity * price_unit
            )
            
            # Agregar impuestos
            if sub_line.tax_ids.exists():
                invoice_line.tax.set(sub_line.tax_ids.all())
    
    def _calculate_invoice_totals(self, invoice):
        """
        Calcula los totales de la factura
        """
        # Recalcular líneas primero
        lines = invoice.lines.all()
        
        for line in lines:
            # Calcular subtotal
            line.subtotal = line.quantity * line.price_unit * (1 - line.discount / 100)
            
            # Calcular impuestos (simplificado)
            tax_amount = Decimal('0')
            for tax in line.tax.all():
                if tax.amount_type == 'percent':
                    tax_amount += line.subtotal * (tax.amount / 100)
            
            line.igv_amount = tax_amount
            line.total = line.subtotal + tax_amount
            line.save()
        
        # Calcular totales de la factura
        invoice.amount_tax = sum(line.igv_amount for line in lines)
        invoice.amount_total = sum(line.total for line in lines)
        invoice.save()
    
    def _update_subscription_after_invoice(self, subscription, invoice, target_date):
        """
        Actualiza la suscripción después de generar factura
        """
        # Actualizar contadores
        subscription.recurring_invoice_count += 1
        subscription.invoices_generated += 1
        subscription.total_invoiced += invoice.amount_total
        
        # Calcular próxima fecha de facturación
        if subscription.contract_template:
            subscription.next_invoice_date = (
                subscription.contract_template.get_next_invoice_date(target_date)
            )
        else:
            # Lógica por defecto: mensual
            subscription.next_invoice_date = target_date + timedelta(days=30)
        
        # Actualizar estado si es necesario
        if (subscription.contract_template and 
            subscription.contract_template.recurring_rule_boundary == 'limited' and
            subscription.recurring_invoice_count >= subscription.contract_template.recurring_rule_count):
            subscription.state = 'closed'
        
        subscription.save()
    
    def get_pending_subscriptions_count(self, target_date=None):
        """
        Obtiene el número de suscripciones pendientes de facturación
        """
        target_date = target_date or self.today
        return self._get_eligible_subscriptions(target_date).count()
    
    def validate_subscription_invoiceability(self, subscription_id):
        """
        Valida si una suscripción puede ser facturada
        """
        try:
            subscription = SaleSubscription.objects.get(id=subscription_id)
            
            validation_result = {
                'can_invoice': False,
                'reasons': [],
                'next_invoice_date': subscription.next_invoice_date
            }
            
            # Validaciones
            if subscription.state not in ['active', 'in_renewal']:
                validation_result['reasons'].append('Suscripción no activa')
            
            if not subscription.is_active:
                validation_result['reasons'].append('Suscripción inactiva')
            
            if not subscription.lines.exists():
                validation_result['reasons'].append('No tiene líneas de suscripción')
            
            if subscription.next_invoice_date and subscription.next_invoice_date > self.today:
                validation_result['reasons'].append('Fecha de facturación futura')
            
            validation_result['can_invoice'] = len(validation_result['reasons']) == 0
            return validation_result
            
        except SaleSubscription.DoesNotExist:
            return {'can_invoice': False, 'reasons': ['Suscripción no encontrada']}

# Función de conveniencia para uso directo
def generate_batch_invoices(company_id=None, target_date=None, subscription_ids=None):
    """
    Función de conveniencia para generar facturas en lote
    """
    service = BatchInvoiceService(company_id)
    return service.generate_batch_invoices(target_date, subscription_ids)

def get_pending_invoices_count(company_id=None, target_date=None):
    """
    Función de conveniencia para obtener conteo de pendientes
    """
    service = BatchInvoiceService(company_id)
    return service.get_pending_subscriptions_count(target_date)