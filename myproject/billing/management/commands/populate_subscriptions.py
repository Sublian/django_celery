# billing/management/commands/populate_subscriptions.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from billing.models import (
    SaleSubscription, SaleSubscriptionLine, Partner, Company, 
    Product, Tax, ContractTemplate
)
from decimal import Decimal
import random

class Command(BaseCommand):
    help = 'Crear suscripciones de prueba con líneas'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Creando suscripciones de prueba...')
        
        self.create_test_subscriptions()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Suscripciones de prueba creadas exitosamente!')
        )
    
    def create_test_subscriptions(self):
        """Crear suscripciones de prueba con datos realistas"""
        
        # Obtener datos base
        companies = Company.objects.all()
        partners = Partner.objects.filter(is_customer=True, is_active=True)[:10]  # Primeros 10 clientes
        products = Product.objects.filter(is_active=True)
        taxes = Tax.objects.filter(is_active=True, type_tax_use='sale')
        contract_templates = ContractTemplate.objects.filter(active=True)
        
        if not all([companies, partners, products, contract_templates]):
            self.stdout.write(self.style.ERROR('    ❌ Faltan datos base para crear suscripciones'))
            return
        
        subscription_count = 0
        
        for company in companies:
            self.stdout.write(f"📋 Creando suscripciones para: {company}")
            
             # Obtener partners de esta compañía usando la relación ManyToMany
            company_partners = Partner.objects.filter(
                companies=company, 
                is_customer=True, 
                is_active=True
            )[:5]  # Solo primeros 5 clientes de esta compañía
            
            if not company_partners.exists():
                self.stdout.write(f"    ⚠️ No hay clientes para la compañía: {company}")
                continue
            
            # CORRECCIÓN: Plantillas de esta compañía
            company_templates = contract_templates.filter(company=company)
            if not company_templates.exists():
                self.stdout.write(f"    ⚠️ No hay plantillas para la compañía: {company}")
                continue
            
            for partner in company_partners:
                # Seleccionar plantilla aleatoria de esta compañía
                template = random.choice(list(company_templates))
                
                # Fechas realistas
                date_start = self._calculate_start_date()
                date_end = self._calculate_end_date(date_start, template)
                next_invoice_date = self._calculate_next_invoice_date(date_start, template)
                
                # Crear suscripción
                subscription = SaleSubscription.objects.create(
                    partner=partner,
                    company=company,
                    contract_template=template,
                    date_start=date_start,
                    date_end=date_end,
                    recurring_total=Decimal('0'),
                    recurring_monthly=Decimal('0'),
                    state='active',
                    code=f"SUB{company.id:03d}{partner.id:05d}{subscription_count:03d}",
                    description=f"Suscripción {template.name} para {partner.display_name or partner.name}",
                    uuid=f"sub-{company.id}-{partner.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    health='normal',
                    to_renew=True,
                    next_invoice_date=next_invoice_date,
                    invoicing_interval=template.recurring_rule_type
                )
                
                # Crear líneas de suscripción
                total_monthly = self._create_subscription_lines(subscription, products, taxes)
                
                # MEJORA: Calcular totales basados en la duración del contrato
                total_contract = self._calculate_total_contract(total_monthly, template, date_start, date_end)
                
                # Actualizar totales de la suscripción
                subscription.recurring_monthly = total_monthly
                subscription.recurring_total = total_contract
                subscription.save()
                
                subscription_count += 1
                self.stdout.write(
                    f"    ✅ {template.name} - {partner.display_name or partner.name} - "
                    f"${total_monthly:.2f}/mes - "
                    f"Total contrato: ${total_contract:.2f} - "
                    f"Próxima factura: {next_invoice_date}"
                )
        
        self.stdout.write(f"📊 Total suscripciones creadas: {subscription_count}")
    
    def _calculate_start_date(self):
        """Calcular fecha de inicio realista"""
        # Fecha entre hoy y 90 días atrás
        days_ago = random.randint(0, 90)
        return timezone.now().date() - timedelta(days=days_ago)
    
    def _calculate_end_date(self, start_date, template):
        """Calcular fecha de fin basada en la plantilla"""
        if template.recurring_rule_boundary == 'limited':
            # Contrato con duración limitada
            if template.recurring_rule_type == 'daily':
                return start_date + timedelta(days=template.recurring_rule_count * template.recurring_interval)
            elif template.recurring_rule_type == 'weekly':
                return start_date + timedelta(weeks=template.recurring_rule_count * template.recurring_interval)
            elif template.recurring_rule_type == 'monthly':
                return start_date + relativedelta(months=template.recurring_rule_count * template.recurring_interval)
            elif template.recurring_rule_type == 'yearly':
                return start_date + relativedelta(years=template.recurring_rule_count * template.recurring_interval)
        else:
            # Contrato ilimitado - 1 año por defecto
            return start_date + relativedelta(years=1)
    
    def _calculate_next_invoice_date(self, start_date, template):
        """Calcular próxima fecha de facturación basada en la plantilla"""
        # MEJORA: Usar la lógica de la plantilla para calcular la próxima factura
        today = timezone.now().date()
        
        if template.recurring_rule_type == 'daily':
            # Para facturación diaria, próxima factura es mañana
            next_date = today + timedelta(days=template.recurring_interval)
        elif template.recurring_rule_type == 'weekly':
            # Para facturación semanal, calcular próximo día de la semana
            next_date = today + timedelta(weeks=template.recurring_interval)
        elif template.recurring_rule_type == 'monthly':
            # Para facturación mensual, mismo día del próximo mes
            next_date = today + relativedelta(months=template.recurring_interval)
            # Asegurar que el día existe en el próximo mes
            try:
                next_date = next_date.replace(day=min(today.day, 28))
            except ValueError:
                next_date = next_date.replace(day=28)
        elif template.recurring_rule_type == 'yearly':
            # Para facturación anual, mismo día del próximo año
            next_date = today + relativedelta(years=template.recurring_interval)
        else:
            # Por defecto: 30 días
            next_date = today + timedelta(days=30)
        
        return next_date
    
    def _create_subscription_lines(self, subscription, products, taxes):
        """Crear líneas de suscripción y retornar total mensual"""
        total_monthly = Decimal('0')
        line_count = random.randint(1, 3)
        
        for i in range(line_count):
            product = random.choice(list(products))
            quantity = Decimal(str(random.randint(1, 2)))
            price_unit = random.choice([
                Decimal('89.90'), Decimal('129.90'), Decimal('159.90'), 
                Decimal('199.90'), Decimal('249.90'), Decimal('299.90')
            ])
            discount = Decimal(str(random.choice([0, 5, 10, 15])))
            
            line_total = quantity * price_unit * (1 - discount/100)
            total_monthly += line_total
            
            line = SaleSubscriptionLine.objects.create(
                subscription=subscription,
                product=product,
                quantity=quantity,
                price_unit=price_unit,
                discount=discount
            )
            
            # Asignar impuestos
            if taxes.exists():
                selected_taxes = random.sample(list(taxes), min(1, len(taxes)))
                line.tax_ids.set(selected_taxes)
        
        return total_monthly
    
    def _calculate_total_contract(self, monthly_total, template, start_date, end_date):
        """Calcular total del contrato basado en la duración"""
        # Calcular número de meses aproximado del contrato
        months_duration = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        
        if months_duration <= 0:
            months_duration = 1
        
        # Ajustar según el tipo de facturación
        if template.recurring_rule_type == 'daily':
            # Para facturación diaria, estimar 30 días por mes
            days_duration = (end_date - start_date).days
            billing_cycles = max(1, days_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        elif template.recurring_rule_type == 'weekly':
            # Para facturación semanal, calcular número de semanas
            weeks_duration = (end_date - start_date).days // 7
            billing_cycles = max(1, weeks_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        else:
            # Para mensual y anual, usar meses
            return monthly_total * months_duration