# billing/management/commands/set_default_payment_terms.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import (
    Partner,
    ContractTemplate,
    SaleSubscription,
    AccountMove,
    AccountPaymentTerm,
    Company,
)


class Command(BaseCommand):
    help = (
        "Establecer términos de pago por defecto en clientes, contratos y suscripciones"
    )

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se haría sin ejecutar cambios",
        )
        parser.add_argument(
            "--partner-only",
            action="store_true",
            help="Solo actualizar partners (clientes)",
        )

    def handle(self, *args, **options):
        self.stdout.write("💰 Estableciendo términos de pago por defecto...")

        company_id = options.get("company_id")
        dry_run = options.get("dry_run")
        partner_only = options.get("partner_only")

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        updated_counts = {
            "partners": 0,
            "templates": 0,
            "subscriptions": 0,
            "invoices": 0,
        }

        if not companies.exists():
            self.stdout.write(
                self.style.ERROR("❌ No se encontraron compañías para procesar.")
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULACIÓN: No se harán cambios reales")
            )
            for company in companies:
                self.stdout.write(f"\n📋 Procesando: {company.partner.name}")

                # 1. Obtener términos de pago comunes para esta compañía
                payment_terms = AccountPaymentTerm.objects.filter(
                    company=company, is_active=True
                ).order_by("id")

                if not payment_terms.exists():
                    self.stdout.write(
                        f"   ⚠️  No hay términos de pago para {company.partner.name}"
                    )
                    continue

                # Usar el primer término activo como predeterminado
                default_term = payment_terms.first()

                # 2. Actualizar Partners (clientes) sin término de pago
                if not partner_only:
                    self.stdout.write(f"   👥 Actualizando partners...")
                    updated_partners = self._update_partners_payment_terms(
                        company, default_term, dry_run
                    )
                    updated_counts["partners"] += updated_partners

                # 3. Actualizar Plantillas de Contrato
                self.stdout.write(f"   📄 Actualizando plantillas de contrato...")
                updated_templates = self._update_templates_payment_terms(
                    company, default_term, dry_run
                )
                updated_counts["templates"] += updated_templates

                # 4. Actualizar Suscripciones
                self.stdout.write(f"   📋 Actualizando suscripciones...")
                updated_subscriptions = self._update_subscriptions_payment_terms(
                    company, dry_run
                )
                updated_counts["subscriptions"] += updated_subscriptions

                # 5. Actualizar Facturas sin término de pago
                self.stdout.write(f"   🧾 Actualizando facturas...")
                updated_invoices = self._update_invoices_payment_terms(company, dry_run)
                updated_counts["invoices"] += updated_invoices
        else:
            # En modo real, usar transacción
            with transaction.atomic():
                if dry_run:
                    transaction.set_rollback(True)

                for company in companies:
                    self.stdout.write(f"\n📋 Procesando: {company.partner.name}")

                    # 1. Obtener términos de pago comunes para esta compañía
                    payment_terms = AccountPaymentTerm.objects.filter(
                        company=company, is_active=True
                    ).order_by("id")

                    if not payment_terms.exists():
                        self.stdout.write(
                            f"   ⚠️  No hay términos de pago para {company.partner.name}"
                        )
                        continue

                    # Usar el primer término activo como predeterminado
                    default_term = payment_terms.first()

                    # 2. Actualizar Partners (clientes) sin término de pago
                    if not partner_only:
                        self.stdout.write(f"   👥 Actualizando partners...")
                        updated_partners = self._update_partners_payment_terms(
                            company, default_term, dry_run
                        )
                        updated_counts["partners"] += updated_partners

                    # 3. Actualizar Plantillas de Contrato
                    self.stdout.write(f"   📄 Actualizando plantillas de contrato...")
                    updated_templates = self._update_templates_payment_terms(
                        company, default_term, dry_run
                    )
                    updated_counts["templates"] += updated_templates

                    # 4. Actualizar Suscripciones
                    self.stdout.write(f"   📋 Actualizando suscripciones...")
                    updated_subscriptions = self._update_subscriptions_payment_terms(
                        company, dry_run
                    )
                    updated_counts["subscriptions"] += updated_subscriptions

                    # 5. Actualizar Facturas sin término de pago
                    self.stdout.write(f"   🧾 Actualizando facturas...")
                    updated_invoices = self._update_invoices_payment_terms(
                        company, dry_run
                    )
                    updated_counts["invoices"] += updated_invoices

        # Mostrar resumen
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("📊 RESUMEN DE TÉRMINOS DE PAGO ASIGNADOS")
        self.stdout.write("=" * 60)

        for key, count in updated_counts.items():
            item_name = {
                "partners": "Clientes actualizados",
                "templates": "Plantillas actualizadas",
                "subscriptions": "Suscripciones actualizadas",
                "invoices": "Facturas actualizadas",
            }[key]

            self.stdout.write(f"   {item_name}: {count}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Términos de pago establecidos exitosamente!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\n🔍 SIMULACIÓN COMPLETADA: Revise los cambios propuestos"
                )
            )

    def _update_partners_payment_terms(self, company, default_term, dry_run=False):
        """Actualizar términos de pago en partners"""
        try:

            # Solo clientes sin término de pago
            partners = Partner.objects.filter(
                companies=company, is_customer=True, payment_term__isnull=True
            )

            count = 0
            for partner in partners:
                if not dry_run:
                    partner.payment_term = default_term
                    partner.save()

                count += 1
                if count <= 5:  # Mostrar solo los primeros 5
                    self.stdout.write(f"      • {partner.name}: {default_term.name}")
                elif count == 6:
                    self.stdout.write(f"      • ... y {partners.count() - 5} más")

            return count
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"      ❌ Error actualizando partners: {str(e)}")
            )
            return 0

    def _update_templates_payment_terms(self, company, default_term, dry_run=False):
        """Actualizar términos de pago en plantillas de contrato"""
        templates = ContractTemplate.objects.filter(
            company=company, active=True, payment_term__isnull=True
        )

        count = 0
        for template in templates:
            if not dry_run:
                template.payment_term = default_term
                template.save()

            count += 1
            self.stdout.write(f"      • {template.name}: {default_term.name}")

        return count

    def _update_subscriptions_payment_terms(self, company, dry_run=False):
        """Actualizar términos de pago en suscripciones"""
        try:

            subscriptions = SaleSubscription.objects.filter(
                company=company, is_active=True, payment_term__isnull=True
            )

            count = 0
            for subscription in subscriptions:
                # Obtener término de pago según jerarquía
                payment_term = None
                # Primero intentar desde la plantilla de contrato
                if subscription.contract_template and hasattr(
                    subscription.contract_template, "payment_term"
                ):
                    payment_term = subscription.contract_template.payment_term

                # Si no, intentar desde el partner
                if (
                    not payment_term
                    and subscription.partner
                    and hasattr(subscription.partner, "payment_term")
                ):
                    payment_term = subscription.partner.payment_term

                # Si no, usar término por defecto de la compañía
                if not payment_term:
                    default_term = AccountPaymentTerm.objects.filter(
                        company=company, is_active=True
                    ).first()
                    payment_term = default_term

                if payment_term and not dry_run:
                    subscription.payment_term = payment_term
                    subscription.save()

                if payment_term:
                    count += 1
                    if count <= 5:
                        self.stdout.write(
                            f"      • Sub #{subscription.id}: {payment_term.name}"
                        )
                    elif count == 6:
                        self.stdout.write(
                            f"      • ... y {subscriptions.count() - 5} más"
                        )

            return count
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"      ❌ Error actualizando suscripciones: {str(e)}")
            )
            return 0

    def _update_invoices_payment_terms(self, company, dry_run=False):
        """Actualizar términos de pago en facturas"""
        try:

            invoices = AccountMove.objects.filter(
                company=company,
                type="out_invoice",  # Solo facturas de cliente
                invoice_payment_term__isnull=True,
                subscription__isnull=False,  # Solo facturas de suscripción
            )

            count = 0
            for invoice in invoices:
                # Si tiene suscripción, obtener su término de pago
                if invoice.subscription:
                    # Primero ver si la suscripción tiene término de pago
                    payment_term = None

                    # Intentar obtener desde la suscripción (si tiene el campo)
                    if hasattr(invoice.subscription, "payment_term"):
                        payment_term = invoice.subscription.payment_term

                    # Si no, intentar desde la plantilla de contrato
                    if (
                        not payment_term
                        and invoice.subscription.contract_template
                        and hasattr(
                            invoice.subscription.contract_template, "payment_term"
                        )
                    ):
                        payment_term = (
                            invoice.subscription.contract_template.payment_term
                        )

                    # Si no, intentar desde el partner
                    if (
                        not payment_term
                        and invoice.partner
                        and hasattr(invoice.partner, "payment_term")
                    ):
                        payment_term = invoice.partner.payment_term

                    if payment_term and not dry_run:
                        invoice.invoice_payment_term = payment_term

                        # Recalcular fecha de vencimiento (implementar método calculate_due_date)
                        try:
                            due_date = invoice.calculate_due_date()
                            if due_date:
                                invoice.invoice_date_due = due_date
                        except:
                            pass  # Si no existe el método, continuar

                        invoice.save()

                    if payment_term:
                        count += 1
                        if count <= 5:
                            self.stdout.write(
                                f"      • Factura {invoice.invoice_number}: {payment_term.name}"
                            )
                        elif count == 6:
                            self.stdout.write(
                                f"      • ... y {invoices.count() - 5} más"
                            )

            return count
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"      ❌ Error actualizando facturas: {str(e)}")
            )
            return 0
