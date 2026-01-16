# billing/management/commands/populate_ticket_subscriptions.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from billing.models import (
    SaleSubscription,
    SaleSubscriptionLine,
    Partner,
    Company,
    Product,
    Tax,
    ContractTemplate,
)
from billing.services.sequence_service import get_next_subscription_code
from decimal import Decimal
import random


class Command(BaseCommand):
    help = "Crear suscripciones de prueba para clientes con boletas (no RUC)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=3,
            help="Número de suscripciones a crear por compañía (default: 3)",
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Creando suscripciones para boletas...")

        subscription_count = options.get("count", 3)
        self.create_ticket_subscriptions(subscription_count)

        self.stdout.write(
            self.style.SUCCESS("✅ Suscripciones para boletas creadas exitosamente!")
        )

    def create_ticket_subscriptions(self, max_per_company):
        """Crear suscripciones para clientes que requieren boletas"""

        companies = Company.objects.all()
        products = Product.objects.filter(is_active=True)
        taxes = Tax.objects.filter(is_active=True, type_tax_use="sale")

        # Datos de prueba para clientes con DNI/CE (boletas)
        ticket_customers = [
            {"name": "Ana Martínez", "document_type": "ce", "num_document": "28973456"},
            {
                "name": "Luis Fernández",
                "document_type": "dni",
                "num_document": "46769636",
            },
            {
                "name": "Juan Pérez López",
                "document_type": "dni",
                "num_document": "46789231",
            },
            {
                "name": "María García Soto",
                "document_type": "dni",
                "num_document": "53216789",
            },
            {
                "name": "Carlos Rodríguez",
                "document_type": "ce",
                "num_document": "00539827",
            },
        ]

        total_created = 0

        for company in companies:
            self.stdout.write(f"📋 Procesando compañía: {company}")

            # Verificar plantillas
            company_templates = ContractTemplate.objects.filter(
                company=company, active=True
            )
            if not company_templates.exists():
                self.stdout.write(f"❌ No hay plantillas para: {company}")
                continue

            created_for_company = 0

            for customer_data in ticket_customers[:max_per_company]:
                if created_for_company >= max_per_company:
                    break

                try:
                    # Crear o obtener partner para boleta
                    partner, created = Partner.objects.get_or_create(
                        num_document=customer_data["num_document"],
                        defaults={
                            "name": customer_data["name"],
                            "display_name": customer_data["name"],
                            "document_type": customer_data["document_type"],
                            "is_customer": True,
                            "is_active": True,
                        },
                    )

                    # Asociar partner con compañía
                    partner.companies.add(company)

                    # Usar plantilla existente
                    template = random.choice(list(company_templates))

                    # Crear código único
                    # subscription_code = f"SUB{company.id:02d}-{partner.id:06d}"
                    subscription_code = get_next_subscription_code(company)

                    subscription = self._create_subscription(
                        partner, company, template, products, taxes, subscription_code
                    )

                    if subscription:
                        total_created += 1
                        created_for_company += 1

                        doc_type = (
                            "BOLETA"
                            if customer_data["document_type"] != "ruc"
                            else "FACTURA"
                        )
                        self.stdout.write(
                            f"✅ {subscription.code} - {template.name} - {doc_type}"
                        )

                except Exception as e:
                    self.stdout.write(f"❌ Error creando suscripción: {str(e)}")
                    import traceback

                    self.stdout.write(traceback.format_exc())

            self.stdout.write(f"   📊 Creadas para {company}: {created_for_company}")

        self.stdout.write(
            f"\n🎯 Total suscripciones para boletas creadas: {total_created}"
        )

    def _create_subscription(
        self, partner, company, template, products, taxes, subscription_code
    ):
        """Crear una suscripción individual"""
        from django.utils import timezone
        from datetime import timedelta

        # Fechas basadas en la plantilla
        date_start = timezone.now().date() - timedelta(days=random.randint(0, 30))
        date_end = self._calculate_end_date(date_start, template)
        next_invoice_date = self._calculate_next_invoice_date(date_start, template)

        # Crear suscripción
        subscription = SaleSubscription.objects.create(
            partner=partner,
            company=company,
            contract_template=template,
            date_start=date_start,
            date_end=date_end,
            recurring_total=Decimal("0"),
            recurring_monthly=Decimal("0"),
            state="active",
            code=subscription_code,
            description=f"{template.name} - {partner.display_name or partner.name}",
            uuid=f"sub-{company.id}-{partner.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            health="normal",
            to_renew=True,
            next_invoice_date=next_invoice_date,
            invoicing_interval=template.recurring_rule_type,
        )

        # Crear líneas de suscripción
        total_monthly = self._create_subscription_lines(subscription, products, taxes)

        # Calcular total del contrato
        total_contract = self._calculate_total_contract(
            total_monthly, template, date_start, date_end
        )

        # Actualizar totales
        subscription.recurring_monthly = total_monthly
        subscription.recurring_total = total_contract
        subscription.save()

        return subscription

    def _calculate_end_date(self, start_date, template):
        """Calcular fecha de fin"""
        if template.recurring_rule_boundary == "limited":
            if template.recurring_rule_type == "daily":
                return start_date + timedelta(
                    days=template.recurring_rule_count * template.recurring_interval
                )
            elif template.recurring_rule_type == "weekly":
                return start_date + timedelta(
                    weeks=template.recurring_rule_count * template.recurring_interval
                )
            elif template.recurring_rule_type == "monthly":
                return start_date + relativedelta(
                    months=template.recurring_rule_count * template.recurring_interval
                )
            elif template.recurring_rule_type == "yearly":
                return start_date + relativedelta(
                    years=template.recurring_rule_count * template.recurring_interval
                )
        else:
            return start_date + relativedelta(years=1)

    def _calculate_next_invoice_date(self, start_date, template):
        """Calcular próxima fecha de facturación"""
        today = timezone.now().date()

        if template.recurring_rule_type == "daily":
            return today + timedelta(days=template.recurring_interval)
        elif template.recurring_rule_type == "weekly":
            return today + timedelta(weeks=template.recurring_rule_interval)
        elif template.recurring_rule_type == "monthly":
            next_date = today + relativedelta(months=template.recurring_interval)
            try:
                return next_date.replace(day=min(today.day, 28))
            except ValueError:
                return next_date.replace(day=28)
        elif template.recurring_rule_type == "yearly":
            return today + relativedelta(years=template.recurring_interval)
        else:
            return today + timedelta(days=30)

    def _create_subscription_lines(self, subscription, products, taxes):
        """Crear líneas de suscripción"""
        total_monthly = Decimal("0")
        line_count = random.randint(1, 2)  # Menos líneas para boletas

        for i in range(line_count):
            product = random.choice(list(products))
            quantity = Decimal(str(random.randint(1, 1)))  # Cantidades más pequeñas
            price_unit = random.choice(
                [
                    Decimal("49.90"),
                    Decimal("79.90"),
                    Decimal("99.90"),
                    Decimal("129.90"),
                    Decimal("159.90"),
                ]
            )
            discount = Decimal(str(random.choice([0, 5, 10])))

            line_total = quantity * price_unit * (1 - discount / 100)
            total_monthly += line_total

            line = SaleSubscriptionLine.objects.create(
                subscription=subscription,
                product=product,
                quantity=quantity,
                price_unit=price_unit,
                discount=discount,
            )

            # Asignar impuestos
            if taxes.exists():
                selected_taxes = random.sample(list(taxes), min(1, len(taxes)))
                line.tax_ids.set(selected_taxes)

        return total_monthly

    def _calculate_total_contract(self, monthly_total, template, start_date, end_date):
        """Calcular total del contrato"""
        months_duration = (end_date.year - start_date.year) * 12 + (
            end_date.month - start_date.month
        )
        if months_duration <= 0:
            months_duration = 1

        if template.recurring_rule_type == "daily":
            days_duration = (end_date - start_date).days
            billing_cycles = max(1, days_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        elif template.recurring_rule_type == "weekly":
            weeks_duration = (end_date - start_date).days // 7
            billing_cycles = max(1, weeks_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        else:
            return monthly_total * months_duration
