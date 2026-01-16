# billing/management/commands/check_document_types.py
from django.core.management.base import BaseCommand
from billing.services.sequence_service import get_document_type
from billing.models import Partner, SaleSubscription, AccountMove


class Command(BaseCommand):
    help = "Verificar tipos de documento y documentos generados"

    def handle(self, *args, **options):
        self.stdout.write("📋 Verificando tipos de documento...")

        # Verificar partners y sus tipos
        customers = Partner.objects.filter(is_customer=True, is_active=True)

        self.stdout.write("\n👥 Clientes y tipos de documento:")
        for customer in customers[:10]:  # Primeros 10
            doc_type = get_document_type(customer)
            self.stdout.write(
                f"   • {customer.name}: "
                f"{customer.document_type} {customer.num_document} → "
                f"{'FACTURA' if doc_type == 'invoice' else 'BOLETA'}"
            )

        # Verificar suscripciones
        subscriptions = SaleSubscription.objects.select_related("partner", "company")
        self.stdout.write(f"\n📊 Total suscripciones: {subscriptions.count()}")

        # Verificar documentos generados
        invoices = AccountMove.objects.filter(type="out_invoice")
        self.stdout.write(f"\n📄 Documentos generados:")
        self.stdout.write(f"   • Facturas/Boletas: {invoices.count()}")

        # Agrupar por serie
        from django.db.models import Count

        by_series = invoices.values("serie__series", "serie__name").annotate(
            count=Count("id")
        )

        for item in by_series:
            self.stdout.write(
                f"   • Serie {item['serie__series']}: {item['count']} documentos"
            )
