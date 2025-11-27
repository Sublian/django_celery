# billing/management/commands/manage_sequences.py
from django.core.management.base import BaseCommand
from billing.services.sequence_service import sync_sequences, validate_sequences
from billing.models import Sequence, Company

class Command(BaseCommand):
    help = 'Gestionar secuencias de documentos'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Sincronizar secuencias con facturas existentes'
        )
        parser.add_argument(
            '--validate',
            action='store_true', 
            help='Validar consistencia de secuencias'
        )
        parser.add_argument(
            '--company',
            type=int,
            help='ID de compañía específica'
        )
        parser.add_argument(
            '--reset',
            type=int,
            metavar='NUMBER',
            help='Resetear secuencia a un número específico'
        )
    
    def handle(self, *args, **options):
        company_id = options.get('company')
        
        if options.get('sync'):
            self.sync_sequences(company_id)
        elif options.get('validate'):
            self.validate_sequences(company_id)
        elif options.get('reset'):
            self.reset_sequence(company_id, options['reset'])
        else:
            self.show_sequences(company_id)
    
    def sync_sequences(self, company_id):
        """Sincronizar secuencias"""
        self.stdout.write('🔄 Sincronizando secuencias...')
        
        synced_count = sync_sequences(company_id)
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {synced_count} secuencias sincronizadas')
        )
    
    def validate_sequences(self, company_id):
        """Validar secuencias"""
        self.stdout.write('🔍 Validando consistencia de secuencias...')
        
        inconsistencies = validate_sequences(company_id)
        
        if inconsistencies:
            self.stdout.write(self.style.WARNING('⚠️  Se encontraron inconsistencias:'))
            for inc in inconsistencies:
                self.stdout.write(
                    f"   • {inc['sequence']}: "
                    f"Próximo: {inc['current_next']}, "
                    f"Último usado: {inc['last_used']}, "
                    f"Diferencia: {inc['difference']}"
                )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Todas las secuencias son consistentes'))
    
    def show_sequences(self, company_id):
        """Mostrar estado de secuencias"""
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)
        
        self.stdout.write('📊 Estado de secuencias:')
        
        for seq in sequences.select_related('company'):
            last_used = seq.get_last_used_number()
            status = "✅ OK" if last_used is None or seq.number_next > last_used else "⚠️  DESINCORONIZADA"
            
            self.stdout.write(
                f"   • {seq.company}: {seq.name}\n"
                f"     Código: {seq.code}, Prefijo: {seq.prefix}\n"
                f"     Próximo: {seq.number_next}, Incremento: {seq.number_increment}\n"
                f"     Último usado: {last_used or 'N/A'}\n"
                f"     Estado: {status}\n"
            )
    
    def reset_sequence(self, company_id, new_number):
        """Resetear secuencia"""
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)
        
        for seq in sequences:
            old_number = seq.number_next
            seq.number_next = new_number
            seq.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ {seq.code}: {old_number} → {new_number}"
                )
            )