# billing/management/commands/configure_end_of_month_clients.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Partner, AccountPaymentTerm, Company


class Command(BaseCommand):
    help = "Configurar clientes con pago de factura a fin de mes"

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--enable-all",
            action="store_true",
            help="Habilitar pago fin de mes para todos los clientes",
        )
        parser.add_argument(
            "--disable-all",
            action="store_true",
            help="Deshabilitar pago fin de mes para todos los clientes",
        )
        parser.add_argument(
            "--set-term",
            action="store_true",
            help='Asignar término "Fin de Mes" a clientes configurados',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se haría sin ejecutar cambios",
        )

    def handle(self, *args, **options):
        self.stdout.write("⚙️ Configurando clientes con pago a fin de mes...")

        company_id = options.get("company_id")
        enable_all = options.get("enable_all")
        disable_all = options.get("disable_all")
        set_term = options.get("set_term")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULACIÓN: No se harán cambios reales")
            )

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        total_updated = 0
        total_terms_assigned = 0

        with transaction.atomic():
            if dry_run:
                transaction.set_rollback(True)

            for company in companies:
                self.stdout.write(f"\n📋 Compañía: {company.partner.name}")

                # Obtener término "Fin de Mes" para esta compañía
                end_of_month_term = self._get_end_of_month_term(company)
                if not end_of_month_term:
                    self.stdout.write(
                        f'   ⚠️  No se encontró término "Fin de Mes" para {company.partner.name}'
                    )
                    continue

                # Filtrar clientes
                partners = Partner.objects.filter(
                    companies=company, is_customer=True, is_active=True
                )

                # Aplicar configuraciones
                if enable_all:
                    updated = self._enable_all_partners(
                        partners, end_of_month_term if set_term else None, dry_run
                    )
                    total_updated += updated

                elif disable_all:
                    updated = self._disable_all_partners(partners, dry_run)
                    total_updated += updated

                else:
                    # Configuración inteligente basada en lógica de negocio
                    updated, terms_assigned = self._configure_intelligent(
                        partners, end_of_month_term, set_term, dry_run
                    )
                    total_updated += updated
                    total_terms_assigned += terms_assigned

        # Mostrar resumen
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 RESUMEN DE CONFIGURACIÓN")
        self.stdout.write("=" * 60)

        self.stdout.write(f"   👥 Clientes actualizados: {total_updated}")
        if set_term:
            self.stdout.write(f"   🏷️ Términos asignados: {total_terms_assigned}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Configuración completada exitosamente!")
            )

    def _get_end_of_month_term(self, company):
        """Obtener término de pago "Fin de Mes" para una compañía"""
        # Buscar por código
        term = AccountPaymentTerm.objects.filter(
            company=company, code__contains="END_MONTH"
        ).first()

        if term:
            return term

        # Buscar por nombre
        term = AccountPaymentTerm.objects.filter(
            company=company, name__icontains="fin de mes"
        ).first()

        return term

    def _enable_all_partners(self, partners, term=None, dry_run=False):
        """Habilitar pago fin de mes para todos los clientes"""
        count = 0

        for partner in partners:
            if not dry_run:
                partner.invoice_end_of_month_payment = True

                if term:
                    partner.payment_term = term

                partner.save()

            count += 1
            if count <= 5:
                self.stdout.write(f"   ✅ {partner.name}: Pago fin de mes HABILITADO")
                if term:
                    self.stdout.write(f"        • Término asignado: {term.name}")

        if count > 5:
            self.stdout.write(f"   ... y {count - 5} clientes más")

        return count

    def _disable_all_partners(self, partners, dry_run=False):
        """Deshabilitar pago fin de mes para todos los clientes"""
        count = 0

        for partner in partners:
            if not dry_run:
                partner.invoice_end_of_month_payment = False
                partner.save()

            count += 1
            if count <= 5:
                self.stdout.write(
                    f"   ⚠️  {partner.name}: Pago fin de mes DESHABILITADO"
                )

        if count > 5:
            self.stdout.write(f"   ... y {count - 5} clientes más")

        return count

    def _configure_intelligent(
        self, partners, end_of_month_term, set_term=False, dry_run=False
    ):
        """Configuración inteligente basada en tipo de cliente"""
        updated = 0
        terms_assigned = 0

        # Clasificar clientes
        corporate_clients = []  # Empresas con RUC
        individual_clients = []  # Personas naturales

        for partner in partners:
            if (
                partner.document_type == "ruc"
                and partner.num_document
                and len(partner.num_document) == 11
            ):
                corporate_clients.append(partner)
            else:
                individual_clients.append(partner)

        # Regla: Empresas (RUC) tienden a pagar a fin de mes
        self.stdout.write(f"   🏢 Empresas (RUC): {len(corporate_clients)} clientes")

        for partner in corporate_clients:
            if not dry_run:
                partner.invoice_end_of_month_payment = True

                if set_term and not partner.payment_term:
                    partner.payment_term = end_of_month_term
                    terms_assigned += 1

                partner.save()

            updated += 1
            if updated <= 3:
                status = (
                    "HABILITADO"
                    if partner.invoice_end_of_month_payment
                    else "deshabilitado"
                )
                self.stdout.write(f"      • {partner.name}: Pago fin de mes {status}")

        # Regla: Personas naturales NO pagan a fin de mes (por defecto)
        self.stdout.write(
            f"   👤 Personas naturales: {len(individual_clients)} clientes"
        )

        for partner in individual_clients:
            if not dry_run:
                partner.invoice_end_of_month_payment = False
                partner.save()

            updated += 1
            if updated - len(corporate_clients) <= 3:
                self.stdout.write(
                    f"      • {partner.name}: Pago fin de mes DESHABILITADO (por defecto)"
                )

        return updated, terms_assigned
