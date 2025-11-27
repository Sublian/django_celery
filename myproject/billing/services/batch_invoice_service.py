# billing/services/batch_invoice_service.py (versión simplificada)
import logging
from datetime import date, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from decimal import Decimal

from ..models import (
    SaleSubscription, AccountMove, AccountMoveLine, InvoiceSerie,
    Product, Tax, Company, Currency, Journal, Partner
)

logger = logging.getLogger(__name__)

class BatchInvoiceService:
    """
    Servicio simplificado para generar facturas en lote
    """
    
    def __init__(self, company_id=None, dry_run=False):
        self.company_id = company_id
        self.dry_run = dry_run
        self.today = timezone.now().date()
        self.stats = {
            'processed': 0,
            'created': 0,
            'errors': 0,
            'skipped': 0,
            'details': []
        }
    
    def generate_batch_invoices(self, target_date=None, subscription_ids=None):
        """
        Genera facturas en lote para suscripciones recurrentes
        """
        target_date = target_date or self.today
        
        if self.dry_run:
            logger.info(f"🔍 MODO SIMULACIÓN - Facturas a generar para {target_date}")
        else:
            logger.info(f"🚀 Generando facturas para {target_date}")
        
        try:
            # Obtener suscripciones elegibles
            subscriptions = self._get_eligible_subscriptions(target_date, subscription_ids)
            logger.info(f"📊 Encontradas {len(subscriptions)} suscripciones elegibles")
            
            # Procesar cada suscripción
            for subscription in subscriptions:
                self._process_subscription_invoice(subscription, target_date)
            
            logger.info(f"✅ Proceso completado: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"❌ Error en generación de facturas: {str(e)}")
            self.stats['errors'] += 1
            return self.stats
    
    def _get_eligible_subscriptions(self, target_date, subscription_ids=None):
        """
        Obtiene suscripciones elegibles para facturación
        """
        base_query = SaleSubscription.objects.filter(
            Q(state='active') | Q(state='in_renewal'),
            is_active=True,
            next_invoice_date__lte=target_date
        )
        
        if self.company_id:
            base_query = base_query.filter(company_id=self.company_id)
        
        if subscription_ids:
            base_query = base_query.filter(id__in=subscription_ids)
            
        print(f"🔍 Obteniendo suscripciones elegibles para {target_date} ")
        print(f"   🏢 Compañía ID: {self.company_id if self.company_id else 'Todas'}"
              f" | IDs específicas: {subscription_ids if subscription_ids else 'Ninguna'}"
              f" | Total encontradas: {base_query.count()}"
              f" | Fecha objetivo: {target_date}")
        
        return base_query.select_related('partner', 'company').prefetch_related('lines')
    
    def _process_subscription_invoice(self, subscription, target_date):
        """
        Procesa la generación de factura para una suscripción individual
        """
        self.stats['processed'] += 1
        
        try:
            # Verificar si ya existe factura para este período
            if self._invoice_exists_for_period(subscription, target_date):
                self.stats['skipped'] += 1
                self.stats['details'].append(f"Factura ya existe para {subscription.code}")
                return
            
            if self.dry_run:
                self.stats['details'].append(f"SIMULACIÓN: Factura para {subscription.code}")
                return
            
            with transaction.atomic():
                # Crear factura
                invoice = self._create_invoice_from_subscription(subscription, target_date)
                
                # Crear líneas de factura
                self._create_invoice_lines(invoice, subscription)
                
                # Calcular totales
                self._calculate_invoice_totals(invoice)
                
                # Actualizar suscripción
                self._update_subscription_after_invoice(subscription, invoice, target_date)
                
                self.stats['created'] += 1
                self.stats['details'].append(f"Factura creada para {subscription.code}")
                
        except Exception as e:
            logger.error(f"Error procesando suscripción {subscription.id}: {str(e)}")
            self.stats['errors'] += 1
            self.stats['details'].append(f"Error en {subscription.code}: {str(e)}")
    
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
        invoice_serie = InvoiceSerie.objects.filter(
            company=subscription.company,
            is_active=True
        ).first()
        
        if not invoice_serie:
            raise ValueError(f"No hay serie de facturación para {subscription.company}")
        
        # Crear referencia simple (sin secuencia por ahora)
        reference = f"F{subscription.company.id:02d}-{subscription.id}-{target_date.strftime('%Y%m')}"
        
        # Crear factura
        invoice = AccountMove.objects.create(
            partner=subscription.partner,
            subscription=subscription,
            company=subscription.company,
            currency=subscription.company.currency or Currency.objects.first(),
            journal=invoice_serie.journal,
            type='out_invoice',
            state='draft',
            invoice_date=target_date,
            invoice_date_due=target_date + timedelta(days=30),
            serie=invoice_serie,
            invoice_number=reference,
            ref=f"{subscription.code}-{target_date.strftime('%Y%m')}",
            narration=f"Factura recurrente - {subscription.description or 'Suscripción'}",
            billing_type='subscription'
        )
        
        return invoice
    
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
        subscription.recurring_invoice_count += 1
        subscription.invoices_generated += 1
        subscription.total_invoiced += invoice.amount_total
        
        # Calcular próxima fecha de facturación
        if subscription.contract_template:
            # Lógica simple por ahora
            subscription.next_invoice_date = target_date + timedelta(days=30)
        else:
            subscription.next_invoice_date = target_date + timedelta(days=30)
        
        subscription.save()

# Funciones de conveniencia
def generate_batch_invoices(company_id=None, target_date=None, subscription_ids=None, dry_run=False):
    service = BatchInvoiceService(company_id, dry_run)
    return service.generate_batch_invoices(target_date, subscription_ids)

def get_pending_invoices_count(company_id=None):
    service = BatchInvoiceService(company_id)
    target_date = service.today
    return service._get_eligible_subscriptions(target_date).count()

def validate_subscription_invoiceability(subscription_id):
    try:
        subscription = SaleSubscription.objects.get(id=subscription_id)
        service = BatchInvoiceService(subscription.company_id)
        
        # Validación simple
        can_invoice = (
            subscription.state in ['active', 'in_renewal'] and
            subscription.is_active and
            subscription.lines.exists() and
            subscription.next_invoice_date <= service.today
        )
        
        reasons = []
        if subscription.state not in ['active', 'in_renewal']:
            reasons.append('Estado no activo')
        if not subscription.is_active:
            reasons.append('Suscripción inactiva')
        if not subscription.lines.exists():
            reasons.append('No tiene líneas')
        if subscription.next_invoice_date > service.today:
            reasons.append('Fecha de facturación futura')
        if can_invoice and not reasons:
            reasons.append('Suscripción puede ser facturada')
        
        estimated_total = Decimal('0')
        if can_invoice and subscription.lines.exists():
            for line in subscription.lines.all():
                line_total = line.quantity * line.price_unit * (1 - line.discount / 100)
                estimated_total += line_total

        return {
            'can_invoice': can_invoice,
            'reasons': reasons,
            'estimated_total': estimated_total,
            'next_invoice_date': subscription.next_invoice_date,
            'subscription_code': subscription.code,
            'partner_name': subscription.partner.name
        }
        
    except SaleSubscription.DoesNotExist:
        return {'can_invoice': False, 'reasons': ['Suscripción no encontrada'], 'estimated_total': Decimal('0')}