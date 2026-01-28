# billing/management/commands/populate_invoices_with_payment_terms.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, date
from decimal import Decimal
import random
from billing.models import (
    AccountMove,
    SaleSubscription,
    Partner,
    Company,
    Journal,
    InvoiceSerie,
    AccountPaymentTerm,
    Product,
    Tax,
    Currency,
)
from billing.services.sequence_service import SequenceService


class Command(BaseCommand):
    help = "Crear facturas de prueba con términos de pago realistas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Número de facturas a crear por compañía",
        )
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--subscription-only",
            action="store_true",
            help="Solo crear facturas para suscripciones",
        )

    def handle(self, *args, **options):
        self.stdout.write("🧾 Creando facturas de prueba con términos de pago...")

        count = options.get("count", 10)
        company_id = options.get("company_id")
        subscription_only = options.get("subscription_only")

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        total_invoices = 0

        with transaction.atomic():
            for company in companies:
                self.stdout.write(f"\n📋 Compañía: {company.name}")

                invoices_created = self._create_invoices_for_company(
                    company, count, subscription_only
                )
                total_invoices += invoices_created

        self.stdout.write(f"\n🎯 Total facturas creadas: {total_invoices}")
        self.stdout.write(self.style.SUCCESS("✅ Facturas creadas exitosamente!"))

    def _create_invoices_for_company(self, company, count, subscription_only=False):
        """Crear facturas para una compañía"""
        invoices_created = 0

        # Obtener datos necesarios
        service = SequenceService()
        partners = Partner.objects.filter(
            companies=company, is_customer=True, is_active=True
        )[: count * 2]  # Tomar más partners de los necesarios

        journals = Journal.objects.filter(company=company, is_active=True)
        series = InvoiceSerie.objects.filter(company=company, is_active=True)
        products = Product.objects.filter(is_active=True)[:5]
        taxes = Tax.objects.filter(company=company, is_active=True)
        payment_terms = AccountPaymentTerm.objects.filter(
            company=company, is_active=True
        )

        if not all(
            [partners.exists(), journals.exists(), series.exists(), products.exists()]
        ):
            self.stdout.write(f"   ⚠️  Faltan datos para crear facturas")
            return 0

        # Si hay suscripciones, usarlas
        subscriptions = SaleSubscription.objects.filter(company=company, is_active=True)

        for i in range(min(count, partners.count())):
            try:
                partner = partners[i]

                # Determinar si es factura de suscripción o independiente
                subscription = None
                if subscriptions.exists() and (
                    subscription_only or random.choice([True, False])
                ):
                    subscription = random.choice(list(subscriptions))
                    partner = subscription.partner

                # Determinar tipo de documento (factura o boleta)
                if (
                    partner.document_type == "ruc"
                    and partner.num_document
                    and len(partner.num_document) == 11
                ):
                    document_type = "invoice"
                    serie = series.filter(series__startswith="F").first()
                else:
                    document_type = "ticket"
                    serie = series.filter(series__startswith="B").first()

                if not serie:
                    continue

                # Obtener journal correspondiente
                journal = (
                    journals.filter(
                        code__contains="INV" if document_type == "invoice" else "TKT"
                    ).first()
                    or journals.first()
                )

                # Generar referencia
                reference = service.generate_next_reference(
                    "account.move", company, document_type
                )

                # Determinar término de pago
                payment_term = None
                if subscription:
                    payment_term = subscription.get_payment_term()
                else:
                    # Término de pago del cliente o uno aleatorio
                    payment_term = partner.payment_term or random.choice(
                        list(payment_terms)
                    )

                # Crear factura
                invoice_date = timezone.now().date() - timedelta(
                    days=random.randint(0, 30)
                )

                invoice = AccountMove.objects.create(
                    invoice_number=reference,
                    partner=partner,
                    subscription=subscription,
                    journal=journal,
                    company=company,
                    currency=company.currency,
                    type="out_invoice",
                    ref=reference,
                    name=f"Factura {reference}",
                    invoice_date=invoice_date,
                    serie=serie,
                    invoice_payment_term=payment_term,
                    # La fecha de vencimiento se calculará automáticamente en save()
                    state="draft" if random.choice([True, False]) else "posted",
                    amount_total=Decimal("0"),  # Se actualizará con las líneas
                    amount_tax=Decimal("0"),
                )

                # Crear líneas de factura
                total_amount = self._create_invoice_lines(invoice, products, taxes)

                # Actualizar totales
                invoice.amount_total = total_amount
                invoice.amount_tax = total_amount * Decimal("0.18")  # Simular 18% IGV
                invoice.save()

                invoices_created += 1

                # Mostrar información
                due_info = (
                    f"Vence: {invoice.invoice_date_due}"
                    if invoice.invoice_date_due
                    else "Sin vencimiento"
                )
                self.stdout.write(
                    f"   ✅ {reference}: {partner.name} - ${total_amount:.2f} - {payment_term.name if payment_term else 'Sin término'} - {due_info}"
                )

            except Exception as e:
                self.stdout.write(f"   ❌ Error creando factura: {str(e)}")

        return invoices_created

    def _create_invoice_lines(self, invoice, products, taxes):
        """Crear líneas de factura"""
        total = Decimal("0")
        line_count = random.randint(1, 3)

        for i in range(line_count):
            product = random.choice(list(products))
            quantity = Decimal(str(random.randint(1, 5)))
            price_unit = Decimal(str(random.choice([50, 100, 150, 200, 250])))
            discount = Decimal(str(random.choice([0, 5, 10])))

            line_total = quantity * price_unit * (1 - discount / 100)
            total += line_total

            # Aquí deberías crear AccountMoveLine si ese modelo existe
            # Por ahora, solo calcular totales

        return total
