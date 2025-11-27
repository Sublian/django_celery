# billing/management/commands/fix_subscription_codes.py
from django.core.management.base import BaseCommand
from billing.models import SaleSubscription

class Command(BaseCommand):
    help = 'Corregir formatos de código de suscripción existentes'
    
    def handle(self, *args, **options):
        self.stdout.write('🔧 Corrigiendo códigos de suscripción...')
        
        subscriptions = SaleSubscription.objects.all()
        fixed_count = 0
        
        for subscription in subscriptions:
            old_code = subscription.code
            
            # Convertir a nuevo formato: SUB{company_id}-{partner_id}
            if old_code.startswith('SUB') and '-' not in old_code:
                # Formato antiguo: SUB0200001000
                new_code = f"SUB{subscription.company.id:02d}-{subscription.partner.id:06d}"
                subscription.code = new_code
                subscription.save()
                
                fixed_count += 1
                self.stdout.write(f"   🔄 {old_code} → {new_code}")
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {fixed_count} códigos corregidos')
        )