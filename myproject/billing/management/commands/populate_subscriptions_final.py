# billing/management/commands/populate_subscriptions_final.py
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
    help = 'Crear suscripciones de prueba usando plantillas existentes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Número de suscripciones a crear por compañía (default: 5)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Creando suscripciones de prueba...')
        
        subscription_count = options.get('count', 5)
        self.create_test_subscriptions(subscription_count)
        
        self.stdout.write(
            self.style.SUCCESS('✅ Suscripciones de prueba creadas exitosamente!')
        )
    
    def create_test_subscriptions(self, max_per_company):
        """Crear suscripciones usando solo plantillas existentes"""
        
        companies = Company.objects.all()
        products = Product.objects.filter(is_active=True)
        taxes = Tax.objects.filter(is_active=True, type_tax_use='sale')
        
        total_created = 0
        
        for company in companies:
            self.stdout.write(f"📋 Procesando compañía: {company}")
            
            # Verificar que existan plantillas para esta compañía
            company_templates = ContractTemplate.objects.filter(company=company, active=True)
            if not company_templates.exists():
                self.stdout.write(f"❌ No hay plantillas activas para: {company}")
                continue
            
            # Obtener clientes de esta compañía
            company_partners = Partner.objects.filter(
                companies=company, 
                is_customer=True, 
                is_active=True
            )[:max_per_company]
            
            if not company_partners.exists():
                self.stdout.write(f"⚠️ No hay clientes para: {company}")
                continue
            
            created_for_company = 0
            
            for partner in company_partners:
                if created_for_company >= max_per_company:
                    break
                
                try:
                    # Usar plantilla existente aleatoria
                    template = random.choice(list(company_templates))
                    
                    # Crear código único simple (sin secuencia por ahora)
                    subscription_code = f"SUB{company.id:02d}{partner.id:05d}{total_created:03d}"
                    
                    subscription = self._create_subscription(
                        partner, company, template, products, taxes, subscription_code
                    )
                    
                    if subscription:
                        total_created += 1
                        created_for_company += 1
                        self.stdout.write(f"✅ {subscription.code} - {template.name}")
                        
                except Exception as e:
                    self.stdout.write(f"❌ Error creando suscripción para {partner.name}: {str(e)}")
                    import traceback
                    self.stdout.write(traceback.format_exc())
            
            self.stdout.write(f"   📊 Creadas para {company}: {created_for_company}")
        
        self.stdout.write(f"\n🎯 Total suscripciones creadas: {total_created}")
    
    def _create_subscription(self, partner, company, template, products, taxes, subscription_code):
        """Crear una suscripción individual"""
        
        # Fechas basadas en la plantilla
        date_start = timezone.now().date() - timedelta(days=random.randint(0, 60))
        date_end = self._calculate_end_date(date_start, template)
        next_invoice_date = self._calculate_next_invoice_date(date_start, template)
        
        # CORRECCIÓN: Usar formato consistente SUB{company_id}-{partner_id}{sequential}
        # Ejemplo: SUB01-020006, SUB02-010013
        subscription_code = f"SUB{company.id:02d}-{partner.id:06d}"
        
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
            code=subscription_code,
            description=f"{template.name} - {partner.display_name or partner.name}",
            uuid=f"sub-{company.id}-{partner.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            health='normal',
            to_renew=True,
            next_invoice_date=next_invoice_date,
            invoicing_interval=template.recurring_rule_type
        )
        
        # Crear líneas de suscripción
        total_monthly = self._create_subscription_lines(subscription, products, taxes)
        
        # Calcular total del contrato
        total_contract = self._calculate_total_contract(total_monthly, template, date_start, date_end)
        
        # Actualizar totales
        subscription.recurring_monthly = total_monthly
        subscription.recurring_total = total_contract
        subscription.save()
        
        return subscription
    
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
        today = timezone.now().date()
        
        if template.recurring_rule_type == 'daily':
            next_date = today + timedelta(days=template.recurring_interval)
        elif template.recurring_rule_type == 'weekly':
            next_date = today + timedelta(weeks=template.recurring_interval)
        elif template.recurring_rule_type == 'monthly':
            next_date = today + relativedelta(months=template.recurring_interval)
            # Asegurar que el día existe en el próximo mes
            try:
                next_date = next_date.replace(day=min(today.day, 28))
            except ValueError:
                next_date = next_date.replace(day=28)
        elif template.recurring_rule_type == 'yearly':
            next_date = today + relativedelta(years=template.recurring_interval)
        else:
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
            days_duration = (end_date - start_date).days
            billing_cycles = max(1, days_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        elif template.recurring_rule_type == 'weekly':
            weeks_duration = (end_date - start_date).days // 7
            billing_cycles = max(1, weeks_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        else:
            return monthly_total * months_duration