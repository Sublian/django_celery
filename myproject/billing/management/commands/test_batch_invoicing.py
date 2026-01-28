# billing/management/commands/test_batch_invoicing.py
from django.core.management.base import BaseCommand
from billing.services.batch_invoice_service import (
    generate_batch_invoices,
    validate_subscription_invoiceability,
    get_pending_invoices_count,
)
from billing.services.invoice_processing_service import InvoiceProcessingService
from billing.models import SaleSubscription, AccountMove


class Command(BaseCommand):
    help = "Probar el sistema de facturación por lotes"

    def add_arguments(self, parser):
        parser.add_argument("--company", type=int, help="ID de la compañía específica")
        parser.add_argument(
            "--dry-run", action="store_true", help="Ejecutar en modo simulación"
        )
        parser.add_argument(
            "--run",
            action="store_true",
            help="Ejecutar generación de facturas por lote",
        )
        parser.add_argument(
            "--validate", type=int, help="Validar una suscripción específica por ID"
        )
        parser.add_argument(
            "--list-pending",
            action="store_true",
            help="Listar suscripciones pendientes de facturación",
        )
        # NUEVAS opciones
        parser.add_argument(
            "--post", action="store_true", help="Postear facturas en estado draft"
        )
        parser.add_argument(
            "--status", action="store_true", help="Mostrar estado de facturas"
        )
        parser.add_argument(
            "--consistency-check",
            action="store_true",
            help="Verificar consistencia de totales de facturas",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Corregir automáticamente totales inconsistentes",
        )

    def handle(self, *args, **options):
        validate_id = options.get("validate")
        company_id = options.get("company")

        if validate_id:
            # Validar suscripción específica
            self._validate_subscription(validate_id)
            return

        if company_id:
            service = InvoiceProcessingService(company_id=options.get("company"))

            if options.get("list_pending"):
                # Listar suscripciones pendientes
                self._list_pending_subscriptions(company_id)
                return

            if options.get("run"):
                # Mostrar pendientes y ejecutar generación
                self._run_batch_invoicing(company_id, False)

            if options.get("dry_run"):
                # Mostrar pendientes y ejecutar generación en modo simulación
                self._run_batch_invoicing(company_id, True)

            if options.get("post"):
                # Funcionalidad que revisa consistencia y postea facturas
                self._post_invoices(service)
            elif options.get("consistency_check"):
                # Funcionalidad que valida consistencia de facturas
                self._validate_consistency_invoices(service, verbose=True)
            elif options.get("fix"):
                # Funcionalidad que corrige totales inconsistentes
                self._fix_invoices(service)
            elif options.get("status"):
                # Mostrar estado de facturas
                self._show_invoice_status(service)

    def _validate_subscription(self, subscription_id):
        """Validar una suscripción específica"""
        try:
            result = validate_subscription_invoiceability(subscription_id)
            self.stdout.write(f"🔍 Validación suscripción {subscription_id}:")
            self.stdout.write(f"   Puede facturar: {result['can_invoice']}")
            self.stdout.write(f"   Razones: {', '.join(result['reasons'])}")
            self.stdout.write(
                f"   Total estimado: ${result.get('estimated_total', 0):.2f}"
            )
            self.stdout.write(
                f"   Próxima fecha: {result.get('next_invoice_date', 'N/A')}"
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error validando suscripción: {str(e)}")
            )

    def _list_pending_subscriptions(self, company_id):
        """Listar suscripciones pendientes de facturación"""
        from django.utils import timezone
        from django.db.models import Q

        # Obtener suscripciones elegibles
        subscriptions = SaleSubscription.objects.filter(
            Q(state="active") | Q(state="in_renewal"),
            is_active=True,
            next_invoice_date__lte=timezone.now().date(),
        )

        if company_id:
            subscriptions = subscriptions.filter(company_id=company_id)

        subscriptions = subscriptions.select_related(
            "partner", "company", "contract_template"
        )

        self.stdout.write("📋 Suscripciones pendientes de facturación:")

        for sub in subscriptions:
            self.stdout.write(
                f"   • {sub.code}: {sub.partner.name} "
                f"({sub.company}) - "
                f"Próxima: {sub.next_invoice_date} - "
                f"Plantilla: {sub.contract_template.name if sub.contract_template else 'N/A'}"
            )

        self.stdout.write(f"📊 Total pendientes: {subscriptions.count()}")

    def _run_batch_invoicing(self, company_id, dry_run):
        """Ejecutar generación de facturas por lote"""
        # Mostrar pendientes
        if dry_run:
            self.stdout.write("💡 EJECUTADO EN MODO SIMULACIÓN")

        pending = get_pending_invoices_count(company_id)
        self.stdout.write(f"📊 Facturas pendientes: {pending}")

        if pending > 0:
            # Ejecutar generación
            result = generate_batch_invoices(company_id=company_id, dry_run=dry_run)

            self.stdout.write("📊 RESULTADOS:")
            self.stdout.write(f"   Procesadas: {result['processed']}")
            self.stdout.write(f"   Creadas: {result['created']}")
            self.stdout.write(f"   Errores: {result['errors']}")
            self.stdout.write(f"   Saltadas: {result['skipped']}")

            # Mostrar detalles si hay
            if result.get("details"):
                self.stdout.write("   Detalles:")
                for detail in result["details"][-10:]:  # Últimos 10 detalles
                    self.stdout.write(f"     • {detail}")
        else:
            self.stdout.write("✅ No hay facturas pendientes para generar")

    ######## POSTEAR FACTURAS ########
    def _post_invoices(self, service):
        """Postear facturas"""
        self.stdout.write("📤 Posteando facturas (con validación)...")

        result = service.post_draft_invoices()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {result['posted']} facturas posteadas, "
                f"✖️ {result['failed']} fallidas (validación)"
            )
        )

    def _show_invoice_status(self, service):
        """Mostrar estado de facturas"""
        invoices = AccountMove.objects.all()
        if service.company_id:
            invoices = invoices.filter(company_id=service.company_id)

        self.stdout.write("📄 Estado de facturas:")

        for state in ["draft", "posted", "canceled"]:
            count = invoices.filter(state=state).count()
            self.stdout.write(f"   • {state.upper()}: {count}")

    def _validate_consistency_invoices(self, service, verbose):
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
                f"   {status} {result['invoice']}:      "
                f"Teórico: ${result['theoretical_total']:.2f},      "
                f"Actual: ${result['actual_total']:.2f},    "
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

    def _fix_invoices(self, service):
        """Corregir totales inconsistentes"""
        self.stdout.write("🔧 Corrigiendo totales de facturas...")

        fixed_count = service.fix_invoice_totals()

        self.stdout.write(self.style.SUCCESS(f"✅ {fixed_count} facturas corregidas"))
