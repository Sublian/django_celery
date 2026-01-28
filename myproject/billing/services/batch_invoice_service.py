# billing/services/batch_invoice_service.py (versión simplificada)
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from decimal import Decimal
from .sequence_service import get_next_invoice_reference, get_document_type
from ..models import (
    SaleSubscription,
    AccountMove,
    AccountMoveLine,
    InvoiceSerie,
    Product,
    Tax,
    Company,
    Currency,
    Journal,
    Partner,
    Sequence,
    AccountPaymentTerm,
)

logger = logging.getLogger(__name__)


class BatchInvoiceService:
    """
    Servicio simplificado para generar facturas en lote
    """

    def __init__(self, company_id=None, dry_run=False):
        self.company_id = company_id
        self.dry_run = dry_run
        self.today = timezone.now().date()
        self.stats = {
            "processed": 0,
            "created": 0,
            "errors": 0,
            "skipped": 0,
            "details": [],
        }

    def generate_batch_invoices(self, target_date=None, subscription_ids=None):
        """
        Genera facturas en lote para suscripciones recurrentes
        """
        target_date = target_date or self.today

        if self.dry_run:
            print(f"🔍 MODO SIMULACIÓN - Facturas a generar para {target_date}")
        else:
            print(f"🚀 Generando facturas para {target_date}")

        try:
            # Obtener suscripciones elegibles
            subscriptions = self._get_eligible_subscriptions(
                target_date, subscription_ids
            )
            print(f"📊 Encontradas {len(subscriptions)} suscripciones elegibles")

            # Procesar cada suscripción
            for subscription in subscriptions:
                self._process_subscription_invoice(subscription, target_date)

            print(f"✅ Proceso completado: {self.stats}")
            return self.stats

        except Exception as e:
            print(f"❌ Error en generación de facturas: {str(e)}")
            self.stats["errors"] += 1
            return self.stats

    def _get_eligible_subscriptions(self, target_date, subscription_ids=None):
        """
        Obtiene suscripciones elegibles para facturación
        """
        base_query = SaleSubscription.objects.filter(
            Q(state="active") | Q(state="in_renewal"),
            is_active=True,
            next_invoice_date__lte=target_date,
        )

        if self.company_id:
            base_query = base_query.filter(company_id=self.company_id)

        if subscription_ids:
            base_query = base_query.filter(id__in=subscription_ids)

        print(f"🔍 Obteniendo suscripciones elegibles para {target_date} ")
        print(
            f"   🏢 Compañía ID: {self.company_id if self.company_id else 'Todas'}"
            f" | IDs específicas: {subscription_ids if subscription_ids else 'Ninguna'}"
            f" | Total encontradas: {base_query.count()}"
            f" | Fecha objetivo: {target_date}"
        )

        return base_query.select_related("partner", "company").prefetch_related("lines")

    def _process_subscription_invoice(self, subscription, target_date):
        """
        Procesa la generación de factura para una suscripción individual
        """
        self.stats["processed"] += 1

        try:
            # Verificar si ya existe factura para este período
            if self._invoice_exists_for_period(subscription, target_date):
                self.stats["skipped"] += 1
                self.stats["details"].append(
                    f"Factura ya existe para {subscription.code}"
                )
                return

            if self.dry_run:
                self.stats["details"].append(
                    f"SIMULACIÓN: Factura para {subscription.code}"
                )
                return

            with transaction.atomic():
                # Crear factura
                invoice = self._create_invoice_from_subscription(
                    subscription, target_date
                )

                # Crear líneas de factura
                self._create_invoice_lines(invoice, subscription)

                # Calcular totales
                self._calculate_invoice_totals(invoice)

                # Actualizar suscripción
                self._update_subscription_after_invoice(
                    subscription, invoice, target_date
                )

                self.stats["created"] += 1
                self.stats["details"].append(f"Factura creada para {subscription.code}")

        except Exception as e:
            logger.error(f"<> Error procesando suscripción {subscription.id}: {str(e)}")
            self.stats["errors"] += 1
            self.stats["details"].append(f"Error en {subscription.code}: {str(e)}")

    def _invoice_exists_for_period(self, subscription, target_date):
        """
        Verifica si ya existe una factura para el período
        """
        return AccountMove.objects.filter(
            subscription=subscription,
            invoice_date__year=target_date.year,
            invoice_date__month=target_date.month,
            state__in=["draft", "posted"],
        ).exists()

    def _calculate_emission_date(self, subscription, target_date):
        """
        Calcula fecha de emisión según reglas:
        - Máximo entre fecha_inicio_contrato y fecha_actual
        - Si es recurrente y aprobada: primer día del siguiente mes
        """
        # Fecha base: máximo entre fecha_inicio y fecha_actual
        emission_date = max(subscription.date_start, target_date)

        # Si es recurrente y está aprobada, usar primer día del siguiente mes
        if subscription.is_recurring and subscription.is_approved:
            # Si no es el primer día del mes, ir al primer día del siguiente mes
            if emission_date.day > 1:
                emission_date = emission_date.replace(day=1) + relativedelta(months=1)
            else:
                emission_date = emission_date.replace(day=1)

        return emission_date

    def _calculate_due_date(self, emission_date, subscription):
        """
        Calcula fecha de vencimiento usando términos de pago o lógica por defecto
        """
        # Intentar obtener término de pago de la plantilla o usar por defecto
        payment_term = self._get_payment_term_for_subscription(subscription)

        if payment_term:
            return self._calculate_due_date_from_payment_term(
                emission_date, payment_term
            )
        else:
            # Lógica por defecto: día 30 del mes siguiente
            return self._calculate_default_due_date(emission_date)

    def _get_payment_term_for_subscription(self, subscription):
        """
        Obtiene el término de pago para la suscripción
        (Por ahora usamos el primero disponible, luego se puede personalizar)
        """
        try:
            return AccountPaymentTerm.objects.filter(
                company=subscription.company, is_active=True
            ).first()
        except AccountPaymentTerm.DoesNotExist:
            return None

    def _calculate_due_date_from_payment_term(self, emission_date, payment_term):
        """
        Calcula fecha de vencimiento basada en términos de pago
        """
        # Obtener la primera línea del término de pago
        term_line = payment_term.lines.first()

        if not term_line:
            return self._calculate_default_due_date(emission_date)

        if term_line.option == "day_after_invoice_date":
            return emission_date + timedelta(days=term_line.days)

        elif term_line.option == "day_following_month":
            # Día específico del mes siguiente
            next_month = emission_date + relativedelta(months=1)
            try:
                return next_month.replace(day=term_line.day_of_the_month)
            except ValueError:
                # Si el día no existe en el mes, usar último día
                return next_month + relativedelta(day=31)

        elif term_line.option == "after_invoice_month":
            # Después del mes de factura (ej: +45 días)
            return emission_date + timedelta(days=term_line.days)

        else:
            return self._calculate_default_due_date(emission_date)

    def _calculate_default_due_date(self, emission_date):
        """
        Lógica por defecto: día 30 del mes siguiente
        """
        next_month = emission_date + relativedelta(months=1)

        try:
            # Intentar día 30 del mes siguiente
            due_date = next_month.replace(day=30)
        except ValueError:
            # Si el mes no tiene día 30, usar último día del mes
            due_date = next_month + relativedelta(day=31)

        # Validar que vencimiento > emisión
        if due_date <= emission_date:
            due_date = self._calculate_default_due_date(
                emission_date + timedelta(days=1)
            )

        return due_date

    def _create_invoice_from_subscription(self, subscription, target_date):
        """Crear factura o boleta según el tipo de partner"""

        try:
            # CORRECCIÓN: Usar función corregida
            reference = get_next_invoice_reference(
                subscription.company, subscription.partner
            )

        except Exception as e:
            logger.error(f"<> Error generando referencia: {str(e)}")

        document_type = get_document_type(subscription.partner)
        invoice_serie = self._get_invoice_serie(subscription.company, document_type)

        if not invoice_serie:
            invoice_serie = self._create_fallback_serie(
                subscription.company, document_type
            )

        # Crear documento
        invoice = AccountMove.objects.create(
            partner=subscription.partner,
            subscription=subscription,
            company=subscription.company,
            currency=subscription.company.currency or Currency.objects.first(),
            journal=invoice_serie.journal,
            type="out_invoice",
            state="draft",
            invoice_date=target_date,
            invoice_date_due=self._calculate_due_date(
                target_date, subscription
            ),  # CORREGIDO
            serie=invoice_serie,
            invoice_number=reference,
            ref=subscription.code,
            narration=f"{'Factura' if document_type == 'invoice' else 'Boleta'} recurrente - {subscription.description or 'Suscripción'}",
            billing_type="subscription",
            document_type=subscription.partner.document_type or "dni",
        )

        doc_type_name = "Factura" if document_type == "invoice" else "Boleta"
        logger.info(f"📄 {doc_type_name} {reference} creada para {subscription.code}")
        return invoice

    def _get_invoice_serie(self, company, document_type):
        """Obtener serie según tipo de documento"""
        series_code = "F001" if document_type == "invoice" else "B001"

        try:
            serie = InvoiceSerie.objects.filter(
                company=company,
                is_active=True,
                series=series_code,  # Buscar exactamente F001 o B001
            ).first()

            if not serie:
                logger.warning(
                    f"No se encontró serie {series_code} para {company.name}"
                )

            return serie

        except Exception as e:
            logger.error(f"Error obteniendo serie: {str(e)}")
            return None

    def _create_fallback_serie(self, company, document_type):
        """Crear serie de fallback si no existe"""
        from ..models import Journal, Sequence

        series_code = "F001" if document_type == "invoice" else "B001"
        sequence_code = f"account.move.{document_type}.{company.id}"

        # Buscar secuencia existente primero
        sequence = Sequence.objects.filter(code=sequence_code, company=company).first()

        if not sequence:
            # Crear secuencia si no existe
            sequence = Sequence.objects.create(
                code=sequence_code,
                company=company,
                name=f"Secuencia {series_code} - {company.name}",
                prefix=f"{series_code}-",
                number_next=1,
                number_increment=1,
                padding=8,
                active=True,
            )
            logger.info(f"📝 Secuencia creada: {sequence_code} para {company.name}")

        # Buscar diario existente
        journal_code = f"VNT{'F' if document_type == 'invoice' else 'B'}_{company.id}"
        journal = Journal.objects.filter(code=journal_code, company=company).first()

        if not journal:
            # Crear diario si no existe
            journal_type_name = "Facturas" if document_type == "invoice" else "Boletas"
            journal = Journal.objects.create(
                code=journal_code,
                company=company,
                name=f"Diario Ventas {journal_type_name} - {company.name}",
                type="sale",
            )
            logger.info(f"📔 Diario creado: {journal_code} para {company.name}")

        # Crear serie
        serie, created = InvoiceSerie.objects.get_or_create(
            series=series_code,
            company=company,
            defaults={
                "name": f"Serie {series_code} - {company.name}",
                "journal": journal,
                "sequence": sequence,
                "is_active": True,
            },
        )

        if created:
            logger.info(
                f"📄 Serie de fallback creada: {series_code} para {company.name}"
            )
        else:
            logger.info(
                f"📄 Serie existente encontrada: {series_code} para {company.name}"
            )

        return serie

    def _create_invoice_lines(self, invoice, subscription):
        """
        Crea las líneas de factura desde las líneas de suscripción
        """
        for sub_line in subscription.lines.all():
            # Calcular precio unitario con descuento
            price_unit = sub_line.price_unit * (1 - sub_line.discount / 100)

            # Crear línea de factura
            invoice_line = AccountMoveLine.objects.create(
                move=invoice,
                product=sub_line.product,
                quantity=sub_line.quantity,
                price_unit=price_unit,
                discount=sub_line.discount,
                subtotal=sub_line.quantity * price_unit,
            )

            # Agregar impuestos
            if sub_line.tax_ids.exists():
                invoice_line.tax.set(sub_line.tax_ids.all())

    def _calculate_invoice_totals(self, invoice):
        """
        Calcula los totales de la factura
        """
        lines = invoice.lines.all()

        for line in lines:
            # Calcular subtotal
            line.subtotal = line.quantity * line.price_unit * (1 - line.discount / 100)

            # Calcular impuestos (simplificado)
            tax_amount = Decimal("0")
            for tax in line.tax.all():
                if tax.amount_type == "percent":
                    tax_amount += line.subtotal * (tax.amount / 100)

            line.igv_amount = tax_amount
            line.total = line.subtotal + tax_amount
            line.save()

        # Calcular totales de la factura
        invoice.amount_tax = sum(line.igv_amount for line in lines)
        invoice.amount_total = sum(line.total for line in lines)
        invoice.save()

    def _update_subscription_after_invoice(self, subscription, invoice, target_date):
        """
        Actualiza la suscripción después de generar factura - VERSIÓN MEJORADA
        """
        subscription.recurring_invoice_count += 1
        subscription.invoices_generated += 1
        subscription.total_invoiced += invoice.amount_total

        # Calcular próxima fecha de facturación usando la plantilla
        if subscription.contract_template:
            next_invoice_date = subscription.contract_template.get_next_invoice_date(
                target_date
            )
        else:
            # Por defecto: 30 días después
            next_invoice_date = target_date + timedelta(days=30)

        subscription.next_invoice_date = next_invoice_date
        subscription.save()


# Funciones de conveniencia
def generate_batch_invoices(
    company_id=None, target_date=None, subscription_ids=None, dry_run=False
):
    service = BatchInvoiceService(company_id, dry_run)
    return service.generate_batch_invoices(target_date, subscription_ids)


def get_pending_invoices_count(company_id=None):
    service = BatchInvoiceService(company_id)
    target_date = service.today
    return service._get_eligible_subscriptions(target_date).count()


def validate_subscription_invoiceability(subscription_id):
    try:
        subscription = SaleSubscription.objects.get(id=subscription_id)
        service = BatchInvoiceService(subscription.company_id)

        # Validación simple
        can_invoice = (
            subscription.state in ["active", "in_renewal"]
            and subscription.is_active
            and subscription.lines.exists()
            and subscription.next_invoice_date <= service.today
        )

        reasons = []
        if subscription.state not in ["active", "in_renewal"]:
            reasons.append("Estado no activo")
        if not subscription.is_active:
            reasons.append("Suscripción inactiva")
        if not subscription.lines.exists():
            reasons.append("No tiene líneas")
        if subscription.next_invoice_date > service.today:
            reasons.append("Fecha de facturación futura")
        if can_invoice and not reasons:
            reasons.append("Suscripción puede ser facturada")

        estimated_total = Decimal("0")
        if can_invoice and subscription.lines.exists():
            for line in subscription.lines.all():
                line_total = line.quantity * line.price_unit * (1 - line.discount / 100)
                estimated_total += line_total

        return {
            "can_invoice": can_invoice,
            "reasons": reasons,
            "estimated_total": estimated_total,
            "next_invoice_date": subscription.next_invoice_date,
            "subscription_code": subscription.code,
            "partner_name": subscription.partner.name,
        }

    except SaleSubscription.DoesNotExist:
        return {
            "can_invoice": False,
            "reasons": ["Suscripción no encontrada"],
            "estimated_total": Decimal("0"),
        }


def check_company_setup(company_id):
    """Verificar que una compañía tenga la configuración necesaria"""
    from ..models import Company, InvoiceSerie

    company = Company.objects.get(id=company_id)

    setup_info = {
        "company": company.name,
        "has_invoice_serie": False,
        "has_ticket_serie": False,
        "series_details": [],
    }

    # Verificar series F001
    invoice_series = InvoiceSerie.objects.filter(
        company=company, series="F001", is_active=True
    )
    for serie in invoice_series:
        setup_info["has_invoice_serie"] = True
        setup_info["series_details"].append(
            {
                "series": serie.series,
                "type": "Factura",
                "journal": serie.journal.name if serie.journal else "No asignado",
                "sequence": serie.sequence.code if serie.sequence else "No asignado",
            }
        )

    # Verificar series B001
    ticket_series = InvoiceSerie.objects.filter(
        company=company, series="B001", is_active=True
    )
    for serie in ticket_series:
        setup_info["has_ticket_serie"] = True
        setup_info["series_details"].append(
            {
                "series": serie.series,
                "type": "Boleta",
                "journal": serie.journal.name if serie.journal else "No asignado",
                "sequence": serie.sequence.code if serie.sequence else "No asignado",
            }
        )

    setup_info["is_configured"] = (
        setup_info["has_invoice_serie"] and setup_info["has_ticket_serie"]
    )

    return setup_info
