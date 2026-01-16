# billing/management/commands/reorganize_sequences.py - VERSIÓN MEJORADA
from django.core.management.base import BaseCommand
from billing.models import Sequence, Company, AccountMove, SaleSubscription
from django.db.models import Max


class Command(BaseCommand):
    help = "Reorganizar y sincronizar secuencias"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-existing",
            action="store_true",
            help="Sincronizar con números existentes",
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Reorganizando y sincronizando secuencias...")

        sync_existing = options.get("sync_existing", False)
        companies = Company.objects.all()

        for company in companies:
            self.stdout.write(f"\n🏢 Procesando compañía: {company}")

            # Secuencias para AccountMove (Facturas/Boletas)
            invoice_sequence = self._create_or_update_sequence(
                company=company,
                code=f"account.move.invoice.{company.id}",
                name=f"Secuencia Facturas - {company}",
                prefix="F001-",
                number_next=1,
                padding=8,
            )

            ticket_sequence = self._create_or_update_sequence(
                company=company,
                code=f"account.move.ticket.{company.id}",
                name=f"Secuencia Boletas - {company}",
                prefix="B001-",
                number_next=1,
                padding=8,
            )

            # Secuencia para SaleSubscription
            subscription_sequence = self._create_or_update_sequence(
                company=company,
                code=f"sale.subscription.{company.id}",
                name=f"Secuencia Suscripciones - {company}",
                prefix=f"SUB{company.id:02d}-",
                number_next=1,
                padding=6,
            )

            # Sincronizar con datos existentes si se solicita
            if sync_existing:
                self._sync_sequence_with_existing(invoice_sequence, "F001")
                self._sync_sequence_with_existing(ticket_sequence, "B001")
                self._sync_subscription_sequence(subscription_sequence, company)

            self.stdout.write(f"   ✅ Secuencias reorganizadas para {company}")

        self.stdout.write(
            self.style.SUCCESS("\n✅ Todas las secuencias reorganizadas exitosamente!")
        )

    def _create_or_update_sequence(
        self, company, code, name, prefix, number_next, padding
    ):
        """Crear o actualizar secuencia"""
        sequence, created = Sequence.objects.get_or_create(
            code=code,
            company=company,
            defaults={
                "name": name,
                "prefix": prefix,
                "number_next": number_next,
                "number_increment": 1,
                "padding": padding,
                "active": True,
                "implementation": "standard",
            },
        )

        if not created:
            # Actualizar configuración si es necesario
            update_needed = False
            if sequence.name != name:
                sequence.name = name
                update_needed = True
            if sequence.prefix != prefix:
                sequence.prefix = prefix
                update_needed = True
            if sequence.padding != padding:
                sequence.padding = padding
                update_needed = True

            if update_needed:
                sequence.save()
                self.stdout.write(f"      • {name} [actualizada]")
            else:
                self.stdout.write(f"      • {name} [ya existe]")
        else:
            self.stdout.write(f"      • {name} [creada]")

        return sequence

    def _sync_sequence_with_existing(self, sequence, series_prefix):
        """Sincronizar secuencia con facturas/boletas existentes"""
        try:
            # Buscar el máximo número usado en facturas/boletas existentes
            from billing.models import AccountMove

            existing_docs = AccountMove.objects.filter(
                company=sequence.company, invoice_number__startswith=series_prefix
            ).exclude(invoice_number="")

            if existing_docs.exists():
                # Extraer números y encontrar el máximo
                max_number = 0
                for doc in existing_docs:
                    try:
                        # Extraer número después del prefijo
                        number_part = doc.invoice_number.replace(
                            series_prefix + "-", ""
                        )
                        number = int(number_part.lstrip("0") or 0)
                        max_number = max(max_number, number)
                    except (ValueError, AttributeError):
                        continue

                if max_number > 0:
                    # Establecer próximo número como máximo + 1
                    sequence.number_next = max_number + 1
                    sequence.save()
                    self.stdout.write(
                        f"      🔄 Sincronizado: {sequence.name} → próximo: {sequence.number_next}"
                    )

        except Exception as e:
            self.stdout.write(f"      ⚠️ Error sincronizando {sequence.name}: {str(e)}")

    def _sync_subscription_sequence(self, sequence, company):
        """Sincronizar secuencia de suscripciones con existentes"""
        try:
            existing_subs = SaleSubscription.objects.filter(
                company=company, code__isnull=False
            )

            if existing_subs.exists():
                max_number = 0
                for sub in existing_subs:
                    try:
                        if sub.code and sub.code.startswith(sequence.prefix):
                            number_part = sub.code.replace(sequence.prefix, "")
                            number = int(number_part.lstrip("0") or 0)
                            max_number = max(max_number, number)
                    except (ValueError, AttributeError):
                        continue

                if max_number > 0:
                    sequence.number_next = max_number + 1
                    sequence.save()
                    self.stdout.write(
                        f"      🔄 Sincronizado: {sequence.name} → próximo: {sequence.number_next}"
                    )

        except Exception as e:
            self.stdout.write(f"      ⚠️ Error sincronizando {sequence.name}: {str(e)}")
