# billing/management/commands/populate_initial_sequence.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Sequence, Company, Journal, InvoiceSerie, AccountMove
import logging

logger = logging.getLogger(__name__)

# comando sugerido a usar
# python manage.py populate_initial_sequence --link-existing


class Command(BaseCommand):
    help = (
        "Crear estructura completa de secuencias, diarios y series - VERSIÓN MEJORADA"
    )

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--fix-duplicates",
            action="store_true",
            help="Corregir secuencias duplicadas",
        )
        parser.add_argument(
            "--link-existing",
            action="store_true",
            help="Vincular secuencias existentes con series y diarios",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se haría sin ejecutar cambios",
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Configurando estructura de secuencias - VERSIÓN MEJORADA")

        company_id = options.get("company_id")
        fix_duplicates = options.get("fix_duplicates")
        link_existing = options.get("link_existing")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULACIÓN: No se harán cambios reales")
            )

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        if not companies.exists():
            self.stdout.write(self.style.ERROR("❌ No hay compañías configuradas"))
            return

        # Primero: Corregir duplicados si se solicita
        if fix_duplicates:
            self._fix_duplicate_sequences(companies, dry_run)

        # Segundo: Vincular existentes si se solicita
        if link_existing:
            self._link_existing_structures(companies, dry_run)

        # Tercero: Crear/actualizar estructura
        with transaction.atomic():
            if dry_run:
                # En modo simulación, no usamos transacción real
                self._simulate_configuration(companies)
            else:
                self._execute_configuration(companies)

    def _fix_duplicate_sequences(self, companies, dry_run=False):
        """Corregir secuencias duplicadas"""

        self.stdout.write("\n🔧 Corrigiendo secuencias duplicadas...")

        for company in companies:
            self.stdout.write(f"   📋 Procesando: {company.partner.name}")

            # Encontrar secuencias duplicadas por tipo
            sequences = Sequence.objects.filter(company=company, active=True)

            # Grupo por tipo
            sequence_types = {}
            for seq in sequences:
                # Extraer tipo del código
                parts = seq.code.split(".")
                if len(parts) >= 3:
                    doc_type = parts[2]  # invoice, ticket, credit_note, etc.
                    if doc_type not in sequence_types:
                        sequence_types[doc_type] = []
                    sequence_types[doc_type].append(seq)

            # Corregir duplicados
            for doc_type, seq_list in sequence_types.items():
                if len(seq_list) > 1:
                    self.stdout.write(
                        f"      ⚠️  Duplicados encontrados para {doc_type}: {len(seq_list)} secuencias"
                    )

                    # Mantener la más reciente o la que esté vinculada
                    seq_list.sort(key=lambda x: x.updated_at, reverse=True)

                    # Verificar cuáles están en uso
                    used_sequences = []
                    for seq in seq_list:
                        if InvoiceSerie.objects.filter(sequence=seq).exists():
                            used_sequences.append(seq)

                    if used_sequences:
                        # Mantener las que están en uso
                        keep_ids = [seq.id for seq in used_sequences]
                        deactivate_ids = [
                            seq.id for seq in seq_list if seq.id not in keep_ids
                        ]
                    else:
                        # Mantener la más reciente
                        keep_ids = [seq_list[0].id]
                        deactivate_ids = [seq.id for seq in seq_list[1:]]

                    # Desactivar duplicados
                    if deactivate_ids:
                        if not dry_run:
                            Sequence.objects.filter(id__in=deactivate_ids).update(
                                active=False
                            )

                        for seq_id in deactivate_ids:
                            seq = Sequence.objects.get(id=seq_id)
                            self.stdout.write(
                                f"         ❌ Desactivando: {seq.code} (ID: {seq.id})"
                            )

    def _link_existing_structures(self, companies, dry_run=False):
        """Vincular secuencias, diarios y series existentes"""

        self.stdout.write("\n🔗 Vinculando estructuras existentes...")

        for company in companies:
            self.stdout.write(f"   📋 Procesando: {company.partner.name}")

            # 1. Vincular secuencias con series
            sequences = Sequence.objects.filter(company=company, active=True)
            for seq in sequences:
                # Determinar tipo de documento basado en el código
                doc_type = self._get_document_type_from_code(seq.code)

                if doc_type:
                    # Buscar serie correspondiente
                    series_code = self._get_series_code_from_sequence(seq)
                    if series_code:
                        serie = InvoiceSerie.objects.filter(
                            company=company, series=series_code
                        ).first()

                        if serie and not serie.sequence:
                            if not dry_run:
                                serie.sequence = seq
                                serie.save()

                            self.stdout.write(
                                f"      🔗 Vinculando: {seq.code} → {serie.series}"
                            )

            # 2. Vincular series con diarios
            series = InvoiceSerie.objects.filter(company=company, is_active=True)
            for serie in series:
                if not serie.journal:
                    # Determinar diario basado en tipo de documento
                    journal_code = self._get_journal_code_from_serie(serie)
                    if journal_code:
                        journal = Journal.objects.filter(
                            company=company, code=journal_code
                        ).first()

                        if journal:
                            if not dry_run:
                                serie.journal = journal
                                serie.save()

                            self.stdout.write(
                                f"      🔗 Vinculando: {serie.series} → {journal.code}"
                            )

    def _execute_configuration(self, companies):
        """Ejecutar configuración completa"""

        total_created = {"sequences": 0, "journals": 0, "series": 0}
        total_updated = {"sequences": 0, "journals": 0, "series": 0}

        for company in companies:
            self.stdout.write(f"\n📋 Configurando: {company.partner.name}")

            # 1. Crear/actualizar secuencias (solo las esenciales)
            seq_stats = self._ensure_essential_sequences(company)
            total_created["sequences"] += seq_stats["created"]
            total_updated["sequences"] += seq_stats["updated"]

            # 2. Crear/actualizar diarios
            journal_stats = self._ensure_essential_journals(company)
            total_created["journals"] += journal_stats["created"]
            total_updated["journals"] += journal_stats["updated"]

            # 3. Crear/actualizar series
            series_stats = self._ensure_essential_series(company)
            total_created["series"] += series_stats["created"]
            total_updated["series"] += series_stats["updated"]

            # 4. Sincronizar con facturas existentes
            self._sync_with_existing_invoices(company)

        # Mostrar resumen
        self._show_summary(total_created, total_updated)

    def _simulate_configuration(self, companies):
        """Simular configuración (modo dry-run)"""

        self.stdout.write("\n🔍 SIMULACIÓN: Esto es lo que se haría:")

        for company in companies:
            self.stdout.write(f"\n📋 Para {company.partner.name}:")

            # Secuencias necesarias
            self.stdout.write("  📄 Secuencias a crear/verificar:")
            essential_codes = [
                f"account.move.invoice.{company.id}",
                f"account.move.ticket.{company.id}",
                f"sale.subscription.{company.id}",
            ]

            for code in essential_codes:
                exists = Sequence.objects.filter(code=code, company=company).exists()
                status = "✅ Ya existe" if exists else "➕ Se crearía"
                self.stdout.write(f"    • {code}: {status}")

            # Diarios necesarios
            self.stdout.write("  📒 Diarios a crear/verificar:")
            journal_codes = ["INV", "TKT", "PUR", "BNK", "CASH"]
            for code in journal_codes:
                exists = Journal.objects.filter(
                    code=f"{code}{company.id}", company=company
                ).exists()
                status = "✅ Ya existe" if exists else "➕ Se crearía"
                self.stdout.write(f"    • {code}: {status}")

            # Series necesarias
            self.stdout.write("  🏷️ Series a crear/verificar:")
            series_data = [
                ("F001", "Factura Electrónica"),
                ("B001", "Boleta Electrónica"),
            ]
            for series_code, name in series_data:
                exists = InvoiceSerie.objects.filter(
                    series=series_code, company=company
                ).exists()
                status = "✅ Ya existe" if exists else "➕ Se crearía"
                self.stdout.write(f"    • {series_code} ({name}): {status}")

    def _ensure_essential_sequences(self, company):
        """Asegurar que existan las secuencias esenciales"""

        created = 0
        updated = 0

        essential_sequences = [
            {
                "code": f"account.move.invoice.{company.id}",
                "name": f"Facturas Electrónicas - {company.partner.name}",
                "prefix": "F001-",
                "padding": 8,
                "number_next": 1,
            },
            {
                "code": f"account.move.ticket.{company.id}",
                "name": f"Boletas Electrónicas - {company.partner.name}",
                "prefix": "B001-",
                "padding": 8,
                "number_next": 1,
            },
            {
                "code": f"sale.subscription.{company.id}",
                "name": f"Suscripciones - {company.partner.name}",
                "prefix": f"SUB{company.id}-",
                "padding": 8,
                "number_next": 1,
            },
        ]

        for seq_data in essential_sequences:
            code = seq_data.pop("code")

            sequence, created_flag = Sequence.objects.get_or_create(
                code=code,
                company=company,
                defaults={
                    **seq_data,
                    "suffix": "",
                    "number_increment": 1,
                    "implementation": "standard",
                    "active": True,
                },
            )

            if created_flag:
                created += 1
                self.stdout.write(f"      ✅ Secuencia creada: {sequence.name}")
            else:
                # Actualizar si es necesario
                updated_flag = False
                if sequence.prefix != seq_data["prefix"]:
                    sequence.prefix = seq_data["prefix"]
                    updated_flag = True
                if sequence.padding != seq_data["padding"]:
                    sequence.padding = seq_data["padding"]
                    updated_flag = True

                if updated_flag:
                    sequence.save()
                    updated += 1
                    self.stdout.write(
                        f"      🔄 Secuencia actualizada: {sequence.name}"
                    )

        return {"created": created, "updated": updated}

    def _ensure_essential_journals(self, company):
        """Asegurar que existan los diarios esenciales"""

        created = 0
        updated = 0

        # Obtener secuencias para diarios
        invoice_sequence = Sequence.objects.filter(
            code=f"account.move.invoice.{company.id}", company=company
        ).first()

        ticket_sequence = Sequence.objects.filter(
            code=f"account.move.ticket.{company.id}", company=company
        ).first()

        essential_journals = [
            {
                "code": f"INV{company.id}",
                "name": f"Facturas de Venta - {company.partner.name}",
                "type": "sale",
                "sequence_code": (
                    f"sale.invoice.{company.id}" if invoice_sequence else None
                ),
            },
            {
                "code": f"TKT{company.id}",
                "name": f"Boletas de Venta - {company.partner.name}",
                "type": "sale",
                "sequence_code": (
                    f"sale.ticket.{company.id}" if ticket_sequence else None
                ),
            },
            {
                "code": f"PUR{company.id}",
                "name": f"Compras - {company.partner.name}",
                "type": "purchase",
                "sequence_code": f"purchase.{company.id}",
            },
            {
                "code": f"BNK{company.id}",
                "name": f"Bancos - {company.partner.name}",
                "type": "bank",
                "sequence_code": f"bank.{company.id}",
            },
            {
                "code": f"CASH{company.id}",
                "name": f"Efectivo - {company.partner.name}",
                "type": "cash",
                "sequence_code": f"cash.{company.id}",
            },
        ]

        for journal_data in essential_journals:
            sequence_code = journal_data.pop("sequence_code")

            journal, created_flag = Journal.objects.get_or_create(
                code=journal_data["code"],
                company=company,
                defaults={**journal_data, "is_active": True, "sequence": sequence_code},
            )

            if created_flag:
                created += 1
                self.stdout.write(f"      ✅ Diario creado: {journal.name}")
            else:
                # Actualizar si es necesario
                updated_flag = False
                if journal.is_active != True:
                    journal.is_active = True
                    updated_flag = True
                if journal.sequence != sequence_code and sequence_code:
                    journal.sequence = sequence_code
                    updated_flag = True

                if updated_flag:
                    journal.save()
                    updated += 1
                    self.stdout.write(f"      🔄 Diario actualizado: {journal.name}")

        return {"created": created, "updated": updated}

    def _ensure_essential_series(self, company):
        """Asegurar que existan las series esenciales"""

        created = 0
        updated = 0

        # Obtener secuencias y diarios
        invoice_sequence = Sequence.objects.filter(
            code=f"account.move.invoice.{company.id}", company=company
        ).first()

        ticket_sequence = Sequence.objects.filter(
            code=f"account.move.ticket.{company.id}", company=company
        ).first()

        invoice_journal = Journal.objects.filter(code="INV1", company=company).first()

        ticket_journal = Journal.objects.filter(code="TKT1", company=company).first()

        essential_series = []

        if invoice_sequence and invoice_journal:
            essential_series.append(
                {
                    "series": "F001",
                    "name": f"Serie Factura Electrónica - {company.partner.name}",
                    "sequence": invoice_sequence,
                    "journal": invoice_journal,
                    "document_type": "invoice",
                }
            )

        if ticket_sequence and ticket_journal:
            essential_series.append(
                {
                    "series": "B001",
                    "name": f"Serie Boleta Electrónica - {company.partner.name}",
                    "sequence": ticket_sequence,
                    "journal": ticket_journal,
                    "document_type": "ticket",
                }
            )

        for serie_data in essential_series:
            document_type = serie_data.pop("document_type")

            serie, created_flag = InvoiceSerie.objects.get_or_create(
                series=serie_data["series"],
                company=company,
                defaults={
                    **serie_data,
                    "is_active": True,
                    "manual": False,
                    "is_electronic": True,
                },
            )

            if created_flag:
                created += 1
                self.stdout.write(f"      ✅ Serie creada: {serie.name}")
            else:
                # Actualizar si es necesario
                updated_flag = False
                if not serie.sequence and serie_data.get("sequence"):
                    serie.sequence = serie_data["sequence"]
                    updated_flag = True
                if not serie.journal and serie_data.get("journal"):
                    serie.journal = serie_data["journal"]
                    updated_flag = True
                if serie.is_active != True:
                    serie.is_active = True
                    updated_flag = True

                if updated_flag:
                    serie.save()
                    updated += 1
                    self.stdout.write(f"      🔄 Serie actualizada: {serie.name}")

        return {"created": created, "updated": updated}

    def _sync_with_existing_invoices(self, company):
        """Sincronizar secuencias con facturas existentes"""

        self.stdout.write(f"      🔄 Sincronizando con facturas existentes...")

        try:
            from billing.services.sequence_service import SequenceService

            service = SequenceService()
            synced = service.sync_all_sequences(company.id)

            if synced > 0:
                self.stdout.write(f"         ✅ {synced} secuencias sincronizadas")
        except Exception as e:
            self.stdout.write(f"         ⚠️  Error sincronizando: {str(e)}")

    def _show_summary(self, created, updated):
        """Mostrar resumen de la ejecución"""

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("📊 RESUMEN DE CONFIGURACIÓN")
        self.stdout.write("=" * 50)

        for item_type in ["sequences", "journals", "series"]:
            item_name = {
                "sequences": "Secuencias",
                "journals": "Diarios",
                "series": "Series",
            }[item_type]

            self.stdout.write(
                f"   {item_name}: "
                f"✅ {created[item_type]} creadas | "
                f"🔄 {updated[item_type]} actualizadas"
            )

        self.stdout.write("\n🎯 RECOMENDACIONES:")
        self.stdout.write(
            "   1. Verificar configuración: python manage.py verify_sequences"
        )
        self.stdout.write(
            "   2. Validar consistencia: python manage.py manage_sequences --validate"
        )
        self.stdout.write(
            "   3. Sincronizar secuencias: python manage.py manage_sequences --sync"
        )

    # Métodos auxiliares
    def _get_document_type_from_code(self, code):
        """Extraer tipo de documento del código de secuencia"""

        parts = code.split(".")
        if len(parts) >= 3:
            if parts[1] == "move":
                return parts[2]  # invoice, ticket, credit_note, etc.
        return None

    def _get_series_code_from_sequence(self, sequence):
        """Obtener código de serie basado en el prefijo de secuencia"""

        if sequence.prefix:
            # Ejemplo: 'F001-' -> 'F001'
            return sequence.prefix.rstrip("-")
        return None

    def _get_journal_code_from_serie(self, serie):
        """Obtener código de diario basado en la serie"""
        if serie.series.startswith("F"):
            return "INV1"
        elif serie.series.startswith("B"):
            return "TKT1"
        return None
