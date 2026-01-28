# billing/management/commands/generate_end_of_month_report.py
from django.core.management.base import BaseCommand
import csv
from datetime import date, datetime
import calendar
from billing.models import AccountMove, Partner, Company
from django.db.models import Q


class Command(BaseCommand):
    help = "Generar reporte CSV de facturas con pago a fin de mes"

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--year", type=int, default=datetime.now().year, help="Año para el reporte"
        )
        parser.add_argument(
            "--month", type=int, help="Mes específico para el reporte (1-12)"
        )
        parser.add_argument(
            "--output",
            type=str,
            default="reporte_facturas_fin_mes.csv",
            help="Nombre del archivo de salida",
        )

    def handle(self, *args, **options):
        self.stdout.write("📊 Generando reporte de facturas con pago a fin de mes...")

        company_id = options.get("company_id")
        report_year = options.get("year")
        report_month = options.get("month")
        output_file = options.get("output")

        # Filtrar facturas
        filters = Q(
            invoice_payment_term__lines__option="end_of_month",
            invoice_date__year=report_year,
        )

        if company_id:
            filters &= Q(company_id=company_id)

        if report_month:
            filters &= Q(invoice_date__month=report_month)

        invoices = (
            AccountMove.objects.filter(filters)
            .select_related("partner", "company", "invoice_payment_term")
            .order_by("invoice_date")
        )

        self.stdout.write(f"🔍 Encontradas {invoices.count()} facturas para el reporte")

        if not invoices.exists():
            self.stdout.write(
                self.style.WARNING("⚠️  No hay facturas para generar el reporte")
            )
            return

        # Preparar datos para CSV
        headers = [
            "Compañía",
            "Cliente",
            "Tipo Doc",
            "N° Documento",
            "Factura",
            "Fecha Emisión",
            "Fecha Vencimiento",
            "Días",
            "Pago Fin Mes",
            "Hotfix Aplicado",
            "Monto Total",
            "Estado",
        ]

        rows = []

        for invoice in invoices:
            # Determinar si se aplicó hotfix
            hotfix_aplicado = self._determine_if_hotfix_applied(invoice)

            # Calcular días entre emisión y vencimiento
            dias = (
                (invoice.invoice_date_due - invoice.invoice_date).days
                if invoice.invoice_date_due
                else None
            )

            # Información del cliente
            pago_fin_mes = (
                "SÍ" if invoice.partner.invoice_end_of_month_payment else "NO"
            )

            rows.append(
                {
                    "Compañía": invoice.company.partner.name,
                    "Cliente": invoice.partner.name,
                    "Tipo Doc": invoice.partner.document_type.upper(),
                    "N° Documento": invoice.partner.num_document or "N/A",
                    "Factura": invoice.invoice_number or f"#{invoice.id}",
                    "Fecha Emisión": invoice.invoice_date.strftime("%d/%m/%Y"),
                    "Fecha Vencimiento": (
                        invoice.invoice_date_due.strftime("%d/%m/%Y")
                        if invoice.invoice_date_due
                        else "N/A"
                    ),
                    "Días": str(dias) if dias else "N/A",
                    "Pago Fin Mes": pago_fin_mes,
                    "Hotfix Aplicado": "SÍ" if hotfix_aplicado else "NO",
                    "Monto Total": f"${invoice.amount_total:.2f}",
                    "Estado": (
                        invoice.get_state_display()
                        if hasattr(invoice, "get_state_display")
                        else invoice.state
                    ),
                }
            )

        # Escribir CSV
        try:
            with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter="|")
                writer.writeheader()
                writer.writerows(rows)

            self.stdout.write(
                self.style.SUCCESS(f"✅ Reporte generado exitosamente: {output_file}")
            )
            self.stdout.write(f"   📄 Filas escritas: {len(rows)}")
            self.stdout.write(
                f"   📅 Periodo: {report_year}"
                + (f"-{report_month:02d}" if report_month else "")
            )

            # Estadísticas adicionales
            self._generate_statistics(invoices, report_year, report_month)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error generando reporte: {str(e)}"))

    def _determine_if_hotfix_applied(self, invoice):
        """Determinar si se aplicó el hotfix 30/28 días"""
        if not invoice.invoice_date or not invoice.invoice_date_due:
            return False

        # Si el cliente no tiene pago fin de mes, no hay hotfix
        if not invoice.partner.invoice_end_of_month_payment:
            return False

        # Calcular fecha esperada sin hotfix
        mes = invoice.invoice_date.month
        dia_esperado = 28 if mes == 2 else 30

        try:
            fecha_esperada = invoice.invoice_date.replace(day=dia_esperado)
        except ValueError:
            # Mes con menos días
            _, ultimo_dia = calendar.monthrange(invoice.invoice_date.year, mes)
            fecha_esperada = invoice.invoice_date.replace(day=ultimo_dia)

        # Si la fecha real es diferente, se aplicó hotfix
        return invoice.invoice_date_due != fecha_esperada

    def _generate_statistics(self, invoices, year, month):
        """Generar estadísticas del reporte"""
        self.stdout.write("\n📈 ESTADÍSTICAS DEL REPORTE:")
        self.stdout.write("=" * 50)

        total_facturas = invoices.count()
        con_hotfix = sum(
            1 for inv in invoices if self._determine_if_hotfix_applied(inv)
        )
        con_pago_fin_mes = sum(
            1 for inv in invoices if inv.partner.invoice_end_of_month_payment
        )

        self.stdout.write(f"   • Total facturas: {total_facturas}")
        self.stdout.write(
            f"   • Con pago fin de mes: {con_pago_fin_mes} ({(con_pago_fin_mes / total_facturas * 100):.1f}%)"
        )
        self.stdout.write(
            f"   • Con hotfix aplicado: {con_hotfix} ({(con_hotfix / total_facturas * 100):.1f}%)"
        )

        # Estadísticas por mes
        if not month:
            meses_stats = {}
            for invoice in invoices:
                mes = invoice.invoice_date.month
                if mes not in meses_stats:
                    meses_stats[mes] = {"total": 0, "hotfix": 0}

                meses_stats[mes]["total"] += 1
                if self._determine_if_hotfix_applied(invoice):
                    meses_stats[mes]["hotfix"] += 1

            nombres_meses = [
                "Ene",
                "Feb",
                "Mar",
                "Abr",
                "May",
                "Jun",
                "Jul",
                "Ago",
                "Sep",
                "Oct",
                "Nov",
                "Dic",
            ]

            self.stdout.write("\n   📅 DISTRIBUCIÓN POR MES:")
            for mes_num in sorted(meses_stats.keys()):
                stats = meses_stats[mes_num]
                nombre_mes = nombres_meses[mes_num - 1]
                porcentaje = (
                    (stats["hotfix"] / stats["total"] * 100)
                    if stats["total"] > 0
                    else 0
                )
                self.stdout.write(
                    f"      • {nombre_mes}: {stats['total']} facturas, {stats['hotfix']} hotfix ({porcentaje:.1f}%)"
                )

        # Montos totales
        monto_total = sum(inv.amount_total for inv in invoices)
        monto_promedio = monto_total / total_facturas if total_facturas > 0 else 0

        self.stdout.write(f"\n   💰 MONETARIO:")
        self.stdout.write(f"      • Monto total facturado: ${monto_total:,.2f}")
        self.stdout.write(f"      • Monto promedio por factura: ${monto_promedio:,.2f}")
