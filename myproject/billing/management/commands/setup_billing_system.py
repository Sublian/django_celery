# billing/management/commands/setup_billing_system.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction


class Command(BaseCommand):
    help = "Configuración completa del sistema de facturación"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-existing", action="store_true", help="Saltar datos que ya existen"
        )
        parser.add_argument(
            "--subscription-count",
            type=int,
            default=5,
            help="Número de suscripciones por compañía (default: 5)",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            "🚀 INICIANDO CONFIGURACIÓN COMPLETA DEL SISTEMA DE FACTURACIÓN\n"
        )

        skip_existing = options.get("skip_existing", False)
        subscription_count = options.get("subscription_count", 5)

        steps = [
            ("reorganize_sequences", "🔄 Reorganizando secuencias..."),
            ("populate_initial_data", "📦 Poblando datos iniciales..."),
            ("populate_payment_terms", "💰 Poblando términos de pago..."),
            ("populate_customers", "👥 Poblando clientes..."),
            (
                "populate_subscriptions",
                f"📋 Poblando suscripciones ({subscription_count} por compañía)...",
            ),
        ]

        try:
            with transaction.atomic():
                for command, message in steps:
                    self.stdout.write(f"\n{message}")

                    if command == "populate_subscriptions":
                        call_command(command, count=subscription_count)
                    else:
                        call_command(command)

                # Verificaciones finales
                self._run_final_checks()

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error durante la configuración: {str(e)}")
            )
            raise

        self.stdout.write(self.style.SUCCESS("\n🎉 CONFIGURACIÓN COMPLETA EXITOSA!"))

    def _run_final_checks(self):
        """Ejecutar verificaciones finales"""
        self.stdout.write("\n🔍 EJECUTANDO VERIFICACIONES FINALES...")

        verification_commands = [
            ("verify_sequences", "Verificando secuencias..."),
            ("check_document_types", "Verificando tipos de documento..."),
            ("check_relationships", "Verificando relaciones..."),
        ]

        for command, message in verification_commands:
            self.stdout.write(f"   {message}")
            try:
                call_command(command)
            except Exception as e:
                self.stdout.write(f"   ⚠️ Advertencia en {command}: {str(e)}")
