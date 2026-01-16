# billing/management/commands/manage_sequences.py
from django.core.management.base import BaseCommand
from billing.services.sequence_service import sync_sequences, validate_sequences
from billing.models import Sequence, Company, InvoiceSerie


class Command(BaseCommand):
    help = "Gestionar secuencias de documentos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Sincronizar secuencias con facturas existentes",
        )
        parser.add_argument(
            "--validate", action="store_true", help="Validar consistencia de secuencias"
        )
        parser.add_argument("--company", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--reset",
            type=int,
            metavar="NUMBER",
            help="Resetear secuencia a un número específico",
        )
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Corregir automáticamente las inconsistencias encontradas",
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Mostrar información detallada"
        )

    def handle(self, *args, **options):
        company_id = options.get("company")
        verbose = options.get("verbose")

        # Validar compañía si se especificó
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                self.stdout.write(
                    f"📋 Procesando compañía: {company.partner.name} (ID: {company.id})"
                )
            except Company.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"❌ Compañía con ID {company_id} no encontrada")
                )
                return

        if options.get("sync"):
            self.sync_sequences(company_id, verbose)
        elif options.get("validate"):
            self.validate_sequences(company_id, verbose, options.get("fix"))
        elif options.get("reset"):
            self.reset_sequence(
                company_id, options["reset"], options.get("sequence_id"), verbose
            )
        else:
            self.show_sequences(company_id, verbose)

    def sync_sequences(self, company_id, verbose=False):
        """Sincronizar secuencias"""
        self.stdout.write("🔄 Sincronizando secuencias...")

        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)

        synced_count = 0
        failed_count = 0

        for sequence in sequences:
            try:
                if verbose:
                    self.stdout.write(f"  🔍 Procesando: {sequence.code}")

                last_used = sequence.get_last_used_number()

                if last_used is not None:
                    if sequence.number_next <= last_used:
                        old_value = sequence.number_next
                        new_value = last_used + sequence.number_increment

                        sequence.number_next = new_value
                        sequence.save(update_fields=["number_next", "updated_at"])

                        synced_count += 1

                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"    ✅ {sequence.code}: {old_value} → {new_value}"
                                )
                            )
                    elif verbose:
                        self.stdout.write(
                            f"    ℹ️ {sequence.code}: Ya está sincronizada"
                        )
                elif verbose:
                    self.stdout.write(f"    ℹ️ {sequence.code}: No hay facturas previas")

            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(f"    ❌ Error en {sequence.code}: {str(e)}")
                )

        if synced_count > 0 or failed_count > 0:
            self.stdout.write(f"\n📊 Resumen sincronización:")
            self.stdout.write(f"   ✅ Sincronizadas: {synced_count}")
            self.stdout.write(f"   ❌ Fallidas: {failed_count}")
            self.stdout.write(f"   📄 Total procesadas: {len(sequences)}")

        self.stdout.write(self.style.SUCCESS(f"✅ Sincronización completada"))

    def validate_sequences(self, company_id, verbose=False, fix=False):
        """Validar secuencias"""
        self.stdout.write("🔍 Validando consistencia de secuencias...")

        inconsistencies = validate_sequences(company_id)

        if inconsistencies:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Se encontraron {len(inconsistencies)} inconsistencias:"
                )
            )

            if fix:
                self.stdout.write("🛠️  Corrigiendo inconsistencias...")
                fixed_count = 0

                for inc in inconsistencies:
                    try:
                        sequence = Sequence.objects.get(code=inc["sequence"])
                        if "last_used" in inc and inc["last_used"] is not None:
                            old_value = sequence.number_next
                            new_value = inc["last_used"] + sequence.number_increment

                            sequence.number_next = new_value
                            sequence.save()

                            fixed_count += 1

                            self.stdout.write(
                                f"   🔧 {inc['sequence']}: {old_value} → {new_value}"
                            )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"   ❌ Error corrigiendo {inc['sequence']}: {e}"
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Corregidas: {fixed_count}")
                )

            # Mostrar detalles
            for inc in inconsistencies:
                if "error" in inc:
                    self.stdout.write(
                        f"   ❌ {inc['sequence']}: ERROR - {inc['error']}"
                    )
                else:
                    self.stdout.write(
                        f"   ⚠️  {inc['sequence']}:\n"
                        f"      Próximo: {inc['current_next']}\n"
                        f"      Último usado: {inc['last_used']}\n"
                        f"      Diferencia: {inc['difference']}\n"
                        f"      Estado: {inc['status']}"
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ Todas las secuencias son consistentes")
            )

    def show_sequences(self, company_id, verbose=False):
        """Mostrar estado de secuencias"""
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)

        if not sequences.exists():
            self.stdout.write("ℹ️  No hay secuencias activas")
            return

        self.stdout.write(f"📊 Estado de secuencias ({sequences.count()} encontradas):")

        for seq in sequences.select_related("company"):
            try:
                # Obtener serie asociada si existe
                try:
                    serie = InvoiceSerie.objects.get(sequence=seq)
                    serie_info = f"Serie: {serie.series}"
                except InvoiceSerie.DoesNotExist:
                    serie_info = "Sin serie asociada"

                last_used = seq.get_last_used_number()

                if last_used is None:
                    status = self.style.SUCCESS("✅ OK (sin uso previo)")
                elif seq.number_next > last_used:
                    status = self.style.SUCCESS("✅ OK")
                else:
                    status = self.style.WARNING(
                        f"⚠️  DESINCRONIZADA (+{last_used - seq.number_next})"
                    )

                self.stdout.write(
                    f"\n   📋 {seq.name}\n"
                    f"      Compañía: {seq.company.partner.name}\n"
                    f"      Código: {seq.code}\n"
                    f"      {serie_info}\n"
                    f"      Formato: {seq.prefix}[{str(seq.number_next).zfill(seq.padding)}]{seq.suffix}\n"
                    f"      Próximo: {seq.number_next} (incremento: {seq.number_increment})\n"
                    f"      Último usado: {last_used or 'N/A'}\n"
                    f"      Estado: {status}"
                )

                if verbose and last_used:
                    # Mostrar ejemplos
                    example_current = seq.format_number(seq.number_next)
                    example_last = seq.format_number(last_used)
                    self.stdout.write(f"      Ejemplo actual: {example_current}")
                    self.stdout.write(f"      Ejemplo último: {example_last}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error mostrando {seq.code}: {str(e)}")
                )

    def reset_sequence(self, company_id, new_number, sequence_id=None, verbose=False):
        """Resetear secuencia de forma segura"""
        if new_number < 1:
            self.stdout.write(self.style.ERROR("❌ El número debe ser mayor a 0"))
            return

        sequences = Sequence.objects.filter(active=True)

        if sequence_id:
            sequences = sequences.filter(id=sequence_id)
        elif company_id:
            sequences = sequences.filter(company_id=company_id)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  Se resetearán TODAS las secuencias. Use --sequence-id o --company para ser específico"
                )
            )
            if input("¿Continuar? (s/n): ").lower() != "s":
                return

        if not sequences.exists():
            self.stdout.write("ℹ️  No hay secuencias para resetear")
            return

        self.stdout.write(f"🔄 Reseteando {sequences.count()} secuencia(s)...")

        for seq in sequences:
            try:
                old_number = seq.number_next

                # Verificar que no haya conflictos
                last_used = seq.get_last_used_number()
                if last_used and new_number <= last_used:
                    self.stdout.write(
                        self.style.WARNING(
                            f"   ⚠️  {seq.code}: El número {new_number} es menor o igual al último usado ({last_used})"
                        )
                    )
                    continue

                seq.number_next = new_number
                seq.save()

                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ {seq.code}: {old_number} → {new_number}")
                )

                if verbose:
                    example = seq.format_number(new_number)
                    self.stdout.write(f"      Ejemplo: {example}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"   ❌ Error reseteando {seq.code}: {str(e)}")
                )
