# billing/management/commands/implement_sequences.py
from django.core.management.base import BaseCommand
from billing.models import Sequence, Company, AccountMove


class Command(BaseCommand):
    help = "Implementar sistema de secuencias para facturas existentes"

    def handle(self, *args, **options):
        self.stdout.write("🔢 Implementando sistema de secuencias...")

        companies = Company.objects.all()
        option = ["invoice", "ticket"]
        for company in companies:
            self.stdout.write(f"🏢 Procesando: {company}")

            for doc_type in option:
                # Crear secuencia para facturas si no existe
                sequence, created = Sequence.objects.get_or_create(
                    code=f"account.move.{doc_type}.{company.id}",
                    company=company,
                )

                # Sincronizar con facturas existentes
                last_invoice = (
                    AccountMove.objects.filter(
                        company=company, invoice_number__isnull=False
                    )
                    .exclude(invoice_number="")
                    .order_by("-id")
                    .first()
                )

                if last_invoice:
                    self.stdout.write(
                        f"   📄 Última {'factura' if doc_type == 'invoice' else 'boleta'}: {last_invoice.invoice_number}"
                    )

                if created:
                    self.stdout.write(f"   ✅ Secuencia creada: {sequence.prefix}...")
                else:
                    self.stdout.write(
                        f"   🔄 Secuencia ya existe: {sequence.prefix}..."
                    )
