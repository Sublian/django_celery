# billing/management/commands/process_invoices.py
from django.core.management.base import BaseCommand
from billing.services.invoice_processing_service import InvoiceProcessingService
from billing.models import AccountMove


class Command(BaseCommand):
    help = "Procesar facturas (postear, validar, etc.)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--post", action="store_true", help="Postear facturas en estado draft"
        )
        parser.add_argument(
            "--validate", action="store_true", help="Validar consistencia de totales"
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Corregir automáticamente totales inconsistentes",
        )
        parser.add_argument("--company", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--verbose", action="store_true", help="Mostrar detalles de debug"
        )

    def handle(self, *args, **options):
        service = InvoiceProcessingService(company_id=options.get("company"))
        verbose = options.get("verbose")

        if options.get("validate"):
            self._validate_invoices(service, verbose)
        elif options.get("fix"):
            self._fix_invoices(service)
        elif options.get("post"):
            self._post_invoices(service)
        else:
            self._show_invoice_status(service)

    def _validate_invoices(self, service, verbose):
        """Validar consistencia de facturas"""
        self.stdout.write("🔍 Validando consistencia de facturas...")

        results = service.validate_invoice_totals()

        consistent_count = sum(1 for r in results if r["is_consistent"])
        inconsistent_count = len(results) - consistent_count

        self.stdout.write(
            f"📊 Resultados: {consistent_count} consistentes, {inconsistent_count} inconsistentes"
        )

        for result in results:
            status = "✅" if result["is_consistent"] else "❌"
            self.stdout.write(
                f"   {status} {result['invoice']}: "
                f"Teórico: ${result['theoretical_total']:.2f}, "
                f"Actual: ${result['actual_total']:.2f}, "
                f"Diferencia: ${result['discrepancy']:.4f}"
            )
            # Mostrar debug detallado para inconsistentes
            if not result["is_consistent"] and verbose:
                self.stdout.write("      📋 Detalles de líneas:")
                for line_detail in result["debug_info"]:
                    self.stdout.write(
                        f"        • {line_detail['product']}: "
                        f"{line_detail['quantity']} x ${line_detail['price_unit']:.2f} "
                        f"(-{line_detail['discount']}%) = ${line_detail['subtotal']:.2f}"
                    )
                    if line_detail["taxes"]:
                        for tax in line_detail["taxes"]:
                            self.stdout.write(f"          {tax}")
                    self.stdout.write(
                        f"          TOTAL LÍNEA: ${line_detail['line_total']:.2f}"
                    )

    def _post_invoices(self, service):
        """Postear facturas"""
        self.stdout.write("📤 Posteando facturas (con validación)...")

        result = service.post_draft_invoices()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {result['posted']} facturas posteadas, "
                f"{result['failed']} fallidas (validación)"
            )
        )

    def _fix_invoices(self, service):
        """Corregir totales inconsistentes"""
        self.stdout.write("🔧 Corrigiendo totales de facturas...")

        fixed_count = service.fix_invoice_totals()

        self.stdout.write(self.style.SUCCESS(f"✅ {fixed_count} facturas corregidas"))

    def _show_invoice_status(self, service):
        """Mostrar estado de facturas"""
        invoices = AccountMove.objects.all()
        if service.company_id:
            invoices = invoices.filter(company_id=service.company_id)

        self.stdout.write("📄 Estado de facturas:")

        for state in ["draft", "posted", "canceled"]:
            count = invoices.filter(state=state).count()
            self.stdout.write(f"   • {state.upper()}: {count}")
