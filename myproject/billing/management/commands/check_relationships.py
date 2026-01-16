# billing/management/commands/check_relationships.py
from django.core.management.base import BaseCommand
from billing.models import Company, Partner, SaleSubscription


class Command(BaseCommand):
    help = "Verificar relaciones entre compañías y partners"

    def handle(self, *args, **options):
        self.stdout.write("🔍 Verificando relaciones...")

        companies = Company.objects.all()

        for company in companies:
            self.stdout.write(f"\n🏢 Compañía: {company}")

            # Partners relacionados con esta compañía
            partners_count = Partner.objects.filter(companies=company).count()
            self.stdout.write(f"   👥 Partners asociados: {partners_count}")

            # Mostrar algunos partners
            LIMIT = 10
            partners = Partner.objects.filter(companies=company)[:LIMIT]
            for partner in partners:
                self.stdout.write(
                    f"      • {partner.name} ({partner.document_type}: {partner.num_document})"
                )

            # Suscripciones existentes
            subscriptions_count = SaleSubscription.objects.filter(
                company=company
            ).count()
            self.stdout.write(f"   📊 Suscripciones: {subscriptions_count}")
