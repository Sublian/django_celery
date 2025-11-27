# billing/management/commands/reorganize_sequences.py
from django.core.management.base import BaseCommand
from billing.models import Sequence, Company

class Command(BaseCommand):
    help = 'Reorganizar secuencias para usar naming convention correcta'
    
    def handle(self, *args, **options):
        self.stdout.write('🔄 Reorganizando secuencias...')
        
        companies = Company.objects.all()
        
        for company in companies:
            self.stdout.write(f"🏢 Procesando compañía: {company}")
            
            # 1. Secuencias para AccountMove (Facturas/Boletas)
            self._create_or_update_sequence(
                company=company,
                code=f'account.move.invoice.{company.id}',
                name=f'Secuencia Facturas - {company}',
                prefix='F001-',
                number_next=1,
                number_increment=1,
                padding=8
            )
            
            self._create_or_update_sequence(
                company=company,
                code=f'account.move.ticket.{company.id}',
                name=f'Secuencia Boletas - {company}',
                prefix='B001-', 
                number_next=1,
                number_increment=1,
                padding=8
            )
            
            # 2. Secuencia para SaleSubscription
            self._create_or_update_sequence(
                company=company,
                code=f'sale.subscription.{company.id}',
                name=f'Secuencia Suscripciones - {company}',
                prefix=f'SUB{company.id:02d}-',  # SUB01, SUB02, etc.
                number_next=1,
                number_increment=1,
                padding=6  # SUB01000001, SUB01000002, etc.
            )
            
            self.stdout.write(f"   ✅ Secuencias reorganizadas para {company}")
        
        self.stdout.write(
            self.style.SUCCESS('✅ Todas las secuencias reorganizadas exitosamente!')
        )
    
    def _create_or_update_sequence(self, company, code, name, prefix, number_next, number_increment, padding):
        """Crear o actualizar secuencia"""
        sequence, created = Sequence.objects.get_or_create(
            code=code,
            company=company,
            defaults={
                'name': name,
                'prefix': prefix,
                'number_next': number_next,
                'number_increment': number_increment,
                'padding': padding,
                'active': True
            }
        )
        
        if not created:
            # Actualizar si ya existe pero con configuración diferente
            update_fields = []
            if sequence.name != name:
                sequence.name = name
                update_fields.append('name')
            if sequence.prefix != prefix:
                sequence.prefix = prefix
                update_fields.append('prefix')
            if sequence.padding != padding:
                sequence.padding = padding
                update_fields.append('padding')
            
            if update_fields:
                sequence.save(update_fields=update_fields)
        
        action = "creada" if created else "actualizada"
        self.stdout.write(f"      • {name} [{action}]")