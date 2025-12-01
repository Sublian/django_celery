# billing/management/commands/populate_payment_terms.py
from django.core.management.base import BaseCommand
from billing.models import AccountPaymentTerm, AccountPaymentTermLine, Company
from decimal import Decimal

class Command(BaseCommand):
    help = 'Poblar términos de pago para las compañías'
    
    def handle(self, *args, **options):
        self.stdout.write('💰 Poblando términos de pago...')
        
        companies = Company.objects.all()
        print(f"🏢 Compañías encontradas: {companies.count()}")
        
        for company in companies:
            self.create_payment_terms_for_company(company)
        
        self.stdout.write(self.style.SUCCESS('✅ Términos de pago poblados exitosamente!'))
    
    def create_payment_terms_for_company(self, company):
        """Crear términos de pago para una compañía"""
        
        # Término 1: Contado (30 días)
        term_contado, created = AccountPaymentTerm.objects.get_or_create(
            code=f'CONTADO_{company.id}',
            company=company,
            defaults={
                'name': f'Contado 30 Días - {company.partner.name}',
                'is_active': True
            }
        )
        
        if created:
            AccountPaymentTermLine.objects.create(
                payment_term=term_contado,
                sequence=10,
                days=30,
                option='day_after_invoice_date',
                value='balance',
                value_amount=0
            )
            self.stdout.write(f"   ✅ {term_contado.name}")
        
        # Término 2: Crédito 60 días
        term_credito, created = AccountPaymentTerm.objects.get_or_create(
            code=f'CREDITO_60_{company.id}',
            company=company,
            defaults={
                'name': f'Crédito 60 Días - {company.partner.name}',
                'is_active': True
            }
        )
        
        if created:
            AccountPaymentTermLine.objects.create(
                payment_term=term_credito,
                sequence=10,
                days=60,
                option='day_after_invoice_date',
                value='balance',
                value_amount=0
            )
            self.stdout.write(f"   ✅ {term_credito.name}")
        
        # Término 3: Día 15 del mes siguiente
        term_15, created = AccountPaymentTerm.objects.get_or_create(
            code=f'DIA_15_{company.id}',
            company=company,
            defaults={
                'name': f'Día 15 Mes Siguiente - {company.partner.name}',
                'is_active': True
            }
        )
        
        if created:
            AccountPaymentTermLine.objects.create(
                payment_term=term_15,
                sequence=10,
                day_of_the_month=15,
                option='day_following_month',
                value='balance',
                value_amount=0
            )
            self.stdout.write(f"   ✅ {term_15.name}")