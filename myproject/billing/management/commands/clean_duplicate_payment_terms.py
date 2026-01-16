# billing/management/commands/clean_duplicate_payment_terms.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import AccountPaymentTerm, AccountPaymentTermLine


class Command(BaseCommand):
    help = "Limpiar términos de pago duplicados"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se eliminaría sin hacer cambios",
        )
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run")
        company_id = options.get("company_id")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULACIÓN: No se harán cambios reales")
            )

        self.stdout.write("🧹 Limpiando términos de pago duplicados...")

        # Filtrar por compañía si se especifica
        filters = {}
        if company_id:
            filters["company_id"] = company_id

        # Encontrar términos con mismo nombre en misma compañía
        from django.db.models import Count

        duplicates = (
            AccountPaymentTerm.objects.filter(**filters)
            .values("company_id", "name")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        if not duplicates.exists():
            self.stdout.write(self.style.SUCCESS("✅ No hay términos duplicados!"))
            return

        self.stdout.write(f"⚠️  Encontrados {len(duplicates)} grupos de duplicados")

        deleted_count = 0

        with transaction.atomic():
            if dry_run:
                transaction.set_rollback(True)

            for dup in duplicates:
                self.stdout.write(
                    f'\n🔍 Grupo: "{dup["name"]}" en compañía ID {dup["company_id"]}'
                )

                # Obtener todos los términos duplicados
                terms = AccountPaymentTerm.objects.filter(
                    company_id=dup["company_id"], name=dup["name"]
                ).order_by("-is_active", "-created_at")

                # Mantener el primero (más reciente y activo)
                keep_term = terms.first()

                self.stdout.write(
                    f"   ✅ Se mantiene: {keep_term.code} (ID: {keep_term.id})"
                )

                # Eliminar los demás
                delete_terms = terms.exclude(id=keep_term.id)

                for term in delete_terms:
                    if not dry_run:
                        # Verificar si está siendo usado antes de eliminar
                        from billing.models import AccountMove

                        used_in_invoices = AccountMove.objects.filter(
                            payment_term=term
                        ).exists()

                        if used_in_invoices:
                            self.stdout.write(
                                f"   ⚠️  No se puede eliminar {term.code}: Está en uso en facturas"
                            )
                            # En lugar de eliminar, desactivar
                            term.is_active = False
                            term.save()
                            self.stdout.write(f"   🔄 Desactivado: {term.code}")
                        else:
                            term.delete()
                            deleted_count += 1
                            self.stdout.write(f"   ❌ Eliminado: {term.code}")
                    else:
                        self.stdout.write(
                            f"   ❌ Se eliminaría: {term.code} (ID: {term.id})"
                        )
                        deleted_count += 1

        self.stdout.write(f"\n📊 Total términos a eliminar/desactivar: {deleted_count}")

        if not dry_run:
            self.stdout.write(self.style.SUCCESS("✅ Limpieza completada!"))
