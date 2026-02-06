# billing/management/commands/populate_subscriptions.py
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
    AccountPaymentTerm,
)
from billing.services.sequence_service import get_next_subscription_code
from decimal import Decimal
import random


class Command(BaseCommand):
    help = "Crear suscripciones de prueba con líneas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Número de suscripciones a crear por compañía (default: 5)",
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Creando suscripciones de prueba...")

        subscription_count = options.get("count", 10)
        print(f"📊 Creando hasta {subscription_count} suscripciones por compañía")
        self.create_test_subscriptions(subscription_count)

        self.stdout.write(
            self.style.SUCCESS("✅ Suscripciones de prueba creadas exitosamente!")
        )

    def create_test_subscriptions(self, max_per_company):
        """Crear suscripciones de prueba con datos realistas"""

        # Obtener datos base
        companies = Company.objects.all()
        products = Product.objects.filter(is_active=True)
        taxes = Tax.objects.filter(is_active=True, type_tax_use="sale")

        if not all([companies, products, taxes]):
            self.stdout.write(
                self.style.ERROR("    ❌ Faltan datos base para crear suscripciones")
            )
            return

        total_created = 0

        for company in companies:
            self.stdout.write(f"📋 Creando suscripciones para: {company}")

            # Verificar que existan plantillas para esta compañía
            company_templates = ContractTemplate.objects.filter(
                company=company, active=True
            )
            if not company_templates.exists():
                self.stdout.write(f"❌ No hay plantillas activas para: {company}")
                continue

            # Obtener partners de esta compañía usando la relación ManyToMany
            company_partners = Partner.objects.filter(
                company=company, is_customer=True, is_active=True
            )[
                :max_per_company
            ]  # Limitar al máximo por compañía

            if not company_partners.exists():
                self.stdout.write(f"    ⚠️ No hay clientes para la compañía: {company}")
                continue

            created_for_company = 0

            for partner in company_partners:
                if created_for_company >= max_per_company:
                    self.stdout.write(
                        f"    ℹ️ Límite alcanzado para {company}, saltando resto de partners."
                    )
                    break
                try:
                    # Generar código único usando secuencia
                    subscription_code = get_next_subscription_code(company)

                    # Usar plantilla existente aleatoria
                    template = random.choice(list(company_templates))

                    subscription = self._create_subscription(
                        partner, company, template, products, taxes, subscription_code
                    )

                    if subscription:
                        total_created += 1
                        created_for_company += 1
                        self.stdout.write(
                            f"✅ {subscription.code} - {template.name} - {partner.name} - {subscription.recurring_total} {company.currency.symbol}"
                        )

                except Exception as e:
                    self.stdout.write(
                        f"❌ Error creando suscripción para {partner.name}: {str(e)}"
                    )

            self.stdout.write(f"   📊 Creadas para {company}: {created_for_company}")

        self.stdout.write(f"\n🎯 Total suscripciones creadas: {total_created}")

    def _create_subscription(
        self, partner, company, template, products, taxes, subscription_code
    ):
        """Crear una suscripción individual con código secuencial"""

        # Obtener término de pago (jerarquía: template → partner → default)
        payment_term = None
        if template.payment_term:
            payment_term = template.payment_term
        elif partner.payment_term:
            payment_term = partner.payment_term
        else:
            # Buscar término por defecto de la compañía
            default_term = AccountPaymentTerm.objects.filter(
                company=company, is_active=True
            ).first()
            if default_term:
                payment_term = default_term

        date_start = timezone.now().date() - timedelta(days=random.randint(0, 60))
        date_end = self._calculate_end_date(date_start, template)

        # MEJORA: Usar el código generado por la secuencia
        subscription = SaleSubscription.objects.create(
            partner=partner,
            company=company,
            contract_template=template,
            payment_term=payment_term,
            date_start=date_start,
            date_end=date_end,
            recurring_total=Decimal("0"),
            recurring_monthly=Decimal("0"),
            state="active",
            code=subscription_code,  # Usar código secuencial
            description=f"{template.name} - {partner.display_name or partner.name}",
            uuid=f"sub-{company.id}-{partner.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            health="normal",
            to_renew=True,
            next_invoice_date=self._calculate_next_invoice_date(date_start, template),
            invoicing_interval=template.recurring_rule_type,
        )

        # Crear líneas
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

    def _calculate_start_date(self):
        """Calcular fecha de inicio realista"""
        # Fecha entre hoy y 90 días atrás
        days_ago = random.randint(0, 90)
        return timezone.now().date() - timedelta(days=days_ago)

    def _calculate_end_date(self, start_date, template):
        """Calcular fecha de fin basada en la plantilla"""
        if template.recurring_rule_boundary == "limited":
            # Contrato con duración limitada
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
            # Contrato ilimitado - 1 año por defecto
            return start_date + relativedelta(years=1)

    def _calculate_next_invoice_date(self, start_date, template):
        """Calcular próxima fecha de facturación de forma consistente"""
        today = timezone.now().date()

        # Si el contrato empieza en el futuro
        if start_date > today:
            return start_date

        # Calcular basado en la regla de recurrencia
        if template.recurring_rule_type == "daily":
            # Encontrar el próximo ciclo desde hoy
            days_since_start = (today - start_date).days
            cycles_passed = days_since_start // template.recurring_interval
            next_cycle = cycles_passed + 1
            return start_date + timedelta(days=next_cycle * template.recurring_interval)

        elif template.recurring_rule_type == "weekly":
            weeks_since_start = (today - start_date).days // 7
            cycles_passed = weeks_since_start // template.recurring_interval
            next_cycle = cycles_passed + 1
            return start_date + timedelta(
                weeks=next_cycle * template.recurring_interval
            )

        elif template.recurring_rule_type == "monthly":
            # Primer día del mes siguiente
            next_month = today.replace(day=1) + relativedelta(months=1)
            return next_month

        elif template.recurring_rule_type == "yearly":
            return today + relativedelta(years=template.recurring_interval)

        # Por defecto
        return today.replace(day=1) + relativedelta(months=1)

    def _create_subscription_lines(self, subscription, products, taxes):
        """Crear líneas de suscripción y retornar total mensual"""
        total_monthly = Decimal("0")
        line_count = random.randint(1, 3)

        for i in range(line_count):
            product = random.choice(list(products))
            quantity = Decimal(str(random.randint(1, 2)))
            price_unit = random.choice(
                [
                    Decimal("89.90"),
                    Decimal("129.90"),
                    Decimal("159.90"),
                    Decimal("199.90"),
                    Decimal("249.90"),
                    Decimal("299.90"),
                ]
            )
            discount = Decimal(str(random.choice([0, 5, 10, 15])))

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
        """Calcular total del contrato basado en la duración"""
        # Calcular número de meses aproximado del contrato
        months_duration = (end_date.year - start_date.year) * 12 + (
            end_date.month - start_date.month
        )

        if months_duration <= 0:
            months_duration = 1

        # Ajustar según el tipo de facturación
        if template.recurring_rule_type == "daily":
            # Para facturación diaria, estimar 30 días por mes
            days_duration = (end_date - start_date).days
            billing_cycles = max(1, days_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        elif template.recurring_rule_type == "weekly":
            # Para facturación semanal, calcular número de semanas
            weeks_duration = (end_date - start_date).days // 7
            billing_cycles = max(1, weeks_duration // template.recurring_interval)
            return monthly_total * billing_cycles
        else:
            # Para mensual y anual, usar meses
            return monthly_total * months_duration
