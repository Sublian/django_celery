# billing/management/commands/create_test_invoices.py
from django.core.management.base import BaseCommand
from billing.services.batch_invoice_service import BatchInvoiceService
from billing.models import SaleSubscription


class Command(BaseCommand):
    help = "Crear facturas reales de prueba (NO simulación)"

    def add_arguments(self, parser):
        parser.add_argument("--company", type=int, help="ID de la compañía específica")
        parser.add_argument(
            "--subscription", type=int, help="ID de suscripción específica"
        )

    def handle(self, *args, **options):
        self.stdout.write("🧪 Creando facturas reales de prueba...")

        company_id = options.get("company")
        subscription_id = options.get("subscription")

        # Configurar IDs específicos si se proporcionan
        subscription_ids = None
        if subscription_id:
            subscription_ids = [subscription_id]

        # Ejecutar servicio en modo REAL (no dry_run)
        service = BatchInvoiceService(company_id=company_id, dry_run=False)
        result = service.generate_batch_invoices(
            target_date=None, subscription_ids=subscription_ids
        )

        self.stdout.write("📊 RESULTADOS REALES:")
        self.stdout.write(f"   Procesadas: {result['processed']}")
        self.stdout.write(f"   Creadas: {result['created']}")
        self.stdout.write(f"   Errores: {result['errors']}")
        self.stdout.write(f"   Saltadas: {result['skipped']}")

        # Mostrar detalles de facturas creadas
        if result["created"] > 0:
            self.stdout.write("   📄 Facturas creadas:")
            for detail in result["details"]:
                if "creada" in detail.lower():
                    self.stdout.write(f"     • {detail}")

        if result["errors"] > 0:
            self.stdout.write("   ❌ Errores:")
            for detail in result["details"]:
                if "error" in detail.lower():
                    self.stdout.write(f"     • {detail}")
