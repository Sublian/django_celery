# billing/management/commands/purge_test_data.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import (
    SaleSubscription, SaleSubscriptionLine, 
    ContractTemplate, Product, Tax,
    InvoiceSerie, Journal, Sequence
)

class Command(BaseCommand):
    help = 'Eliminar datos de prueba generados por los scripts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Eliminar todos los datos de prueba (incluyendo productos e impuestos)'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🗑️  Iniciando purga de datos de prueba...')
        
        delete_all = options.get('all', False)
        
        with transaction.atomic():
            # 1. Eliminar suscripciones y líneas de prueba
            subscriptions_deleted = self.delete_test_subscriptions()
            
            # 2. Eliminar plantillas de contrato de prueba
            templates_deleted = self.delete_test_contract_templates()
            
            if delete_all:
                # 3. Eliminar productos e impuestos de prueba
                products_deleted = self.delete_test_products()
                taxes_deleted = self.delete_test_taxes()
                
                # 4. Eliminar series, diarios y secuencias de prueba
                series_deleted = self.delete_test_invoice_series()
                journals_deleted = self.delete_test_journals()
                sequences_deleted = self.delete_test_sequences()
            else:
                products_deleted = taxes_deleted = series_deleted = journals_deleted = sequences_deleted = 0
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Purga completada:\n'
                    f'   • Suscripciones eliminadas: {subscriptions_deleted}\n'
                    f'   • Plantillas eliminadas: {templates_deleted}\n'
                    f'   • Productos eliminados: {products_deleted}\n'
                    f'   • Impuestos eliminados: {taxes_deleted}\n'
                    f'   • Series eliminadas: {series_deleted}\n'
                    f'   • Diarios eliminados: {journals_deleted}\n'
                    f'   • Secuencias eliminadas: {sequences_deleted}'
                )
            )
    
    def delete_test_subscriptions(self):
        """Eliminar suscripciones de prueba"""
        # Identificar suscripciones de prueba por el patrón en el código
        test_subscriptions = SaleSubscription.objects.filter(
            code__startswith='SUB'
        )
        count = test_subscriptions.count()
        
        # Eliminar líneas primero (por la FK)
        SaleSubscriptionLine.objects.filter(
            subscription__in=test_subscriptions
        ).delete()
        
        # Luego eliminar suscripciones
        test_subscriptions.delete()
        
        self.stdout.write(f'   📊 Suscripciones de prueba eliminadas: {count}')
        return count
    
    def delete_test_contract_templates(self):
        """Eliminar plantillas de contrato de prueba"""
        # Identificar plantillas de prueba por el patrón en el código
        test_templates = ContractTemplate.objects.filter(
            code__regex=r'^(15D|1M|2M|3M|4M|6M|1A)_\d+$'  # Patrón: CODIGO_ID
        )
        count = test_templates.count()
        test_templates.delete()
        
        self.stdout.write(f'   📄 Plantillas de prueba eliminadas: {count}')
        return count
    
    def delete_test_products(self):
        """Eliminar productos de prueba"""
        test_products = Product.objects.filter(
            defaultcode__in=['S00140', 'S00141', 'S00142', 'S00143', 'CON_000074']
        )
        count = test_products.count()
        test_products.delete()
        
        self.stdout.write(f'   📦 Productos de prueba eliminados: {count}')
        return count
    
    def delete_test_taxes(self):
        """Eliminar impuestos de prueba"""
        test_taxes = Tax.objects.filter(
            sequence__regex=r'^tax_(igv|exp)_\d+$'
        )
        count = test_taxes.count()
        test_taxes.delete()
        
        self.stdout.write(f'   💰 Impuestos de prueba eliminados: {count}')
        return count
    
    def delete_test_invoice_series(self):
        """Eliminar series de facturación de prueba"""
        test_series = InvoiceSerie.objects.filter(
            name__contains='Serie'
        )
        count = test_series.count()
        test_series.delete()
        
        self.stdout.write(f'   🧾 Series de prueba eliminadas: {count}')
        return count
    
    def delete_test_journals(self):
        """Eliminar diarios de prueba"""
        test_journals = Journal.objects.filter(
            code__regex=r'^(INV|TKT)\d+$'
        )
        count = test_journals.count()
        test_journals.delete()
        
        self.stdout.write(f'   📒 Diarios de prueba eliminados: {count}')
        return count
    
    def delete_test_sequences(self):
        """Eliminar secuencias de prueba"""
        test_sequences = Sequence.objects.filter(
            code__regex=r'^sale\.(invoice|ticket)\.\d+$'
        )
        count = test_sequences.count()
        test_sequences.delete()
        
        self.stdout.write(f'   🔢 Secuencias de prueba eliminadas: {count}')
        return count