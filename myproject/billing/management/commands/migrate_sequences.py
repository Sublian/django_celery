# billing/management/commands/migrate_sequences.py
from django.core.management.base import BaseCommand
from billing.services.sequence_service import sync_sequences
from billing.models import Sequence, AccountMove

class Command(BaseCommand):
    help = 'Migrar secuencias existentes para usar el nuevo sistema'
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Migrando secuencias al nuevo sistema...')
        
        # 1. Sincronizar todas las secuencias
        synced_count = sync_sequences()
        self.stdout.write(f"🔄 {synced_count} secuencias sincronizadas")
        
        # 2. Verificar facturas sin número
        invoices_without_number = AccountMove.objects.filter(
            invoice_number__isnull=True
        ).exclude(state='canceled').count()
        
        if invoices_without_number > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {invoices_without_number} facturas sin número de referencia"
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS('✅ Migración de secuencias completada')
        )