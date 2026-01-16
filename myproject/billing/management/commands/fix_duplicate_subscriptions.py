# billing/management/commands/fix_duplicate_subscriptions.py
from django.core.management.base import BaseCommand
from billing.models import SaleSubscription
from django.db.models import Count


class Command(BaseCommand):
    help = "Corregir códigos de suscripción duplicados"

    def handle(self, *args, **options):
        self.stdout.write("🔧 Corrigiendo códigos de suscripción duplicados...")

        # Encontrar códigos duplicados
        duplicates = (
            SaleSubscription.objects.values("code")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        fixed_count = 0

        for dup in duplicates:
            code = dup["code"]
            self.stdout.write(
                f"📋 Código duplicado: {code} ({dup['count']} ocurrencias)"
            )

            # Obtener todas las suscripciones con este código
            subscriptions = SaleSubscription.objects.filter(code=code).order_by("id")

            # Mantener el primero, corregir los demás
            first = True
            for subscription in subscriptions:
                if not first:
                    # Generar nuevo código único
                    new_code = f"{code}_{subscription.id}"
                    subscription.code = new_code
                    subscription.save()

                    fixed_count += 1
                    self.stdout.write(f"   🔄 {code} → {new_code}")
                first = False

        self.stdout.write(
            self.style.SUCCESS(f"✅ {fixed_count} códigos duplicados corregidos")
        )
