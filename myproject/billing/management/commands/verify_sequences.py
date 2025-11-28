# billing/management/commands/verify_sequences.py
from django.core.management.base import BaseCommand
from billing.models import Sequence, Company, InvoiceSerie

class Command(BaseCommand):
    help = 'Verificar y crear secuencias faltantes'
    
    def handle(self, *args, **options):
        self.stdout.write('🔍 Verificando secuencias...')
        
        companies = Company.objects.all()
        
        for company in companies:
            self.stdout.write(f"🏢 Verificando: {company}")
            
            # Verificar secuencias para facturas y boletas
            for doc_type in ['invoice', 'ticket']:
                sequence_code = f'account.move.{doc_type}.{company.id}'
                prefix = 'F001-' if doc_type == 'invoice' else 'B001-'
                name = f'Secuencia {"Facturas" if doc_type == "invoice" else "Boletas"} - {company}'
                
                sequence, created = Sequence.objects.get_or_create(
                    code=sequence_code,
                    company=company,
                    defaults={
                        'name': name,
                        'prefix': prefix,
                        'number_next': 1,
                        'number_increment': 1,
                        'padding': 8,
                        'active': True
                    }
                )
                
                if created:
                    self.stdout.write(f"   ✅ Secuencia creada: {sequence_code}")
                else:
                    self.stdout.write(f"   🔄 Secuencia existe: {sequence_code}")
            
            # Verificar series
            for series_code in ['F001', 'B001']:
                serie_exists = InvoiceSerie.objects.filter(
                    company=company,
                    series=series_code
                ).exists()
                
                if serie_exists:
                    self.stdout.write(f"   🔄 Serie existe: {series_code}")
                else:
                    self.stdout.write(f"   ❌ Serie faltante: {series_code}")