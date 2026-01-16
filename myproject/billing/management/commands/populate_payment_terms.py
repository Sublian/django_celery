# billing/management/commands/populate_payment_terms.py
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import AccountPaymentTerm, AccountPaymentTermLine, Company
from decimal import Decimal


class Command(BaseCommand):
    help = "Poblar términos de pago para las compañías"

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="ID de compañía específica")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Forzar recreación de términos existentes",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se crearía sin ejecutar cambios",
        )

    def handle(self, *args, **options):
        self.stdout.write("💰 Poblando términos de pago...")

        company_id = options.get("company_id")
        force = options.get("force")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 MODO SIMULACIÓN: No se harán cambios reales")
            )

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        self.stdout.write(f"🏢 Compañías encontradas: {companies.count()}")

        total_created = 0
        total_lines = 0

        with transaction.atomic():
            if dry_run:
                transaction.set_rollback(True)  # No guardar cambios en modo simulación

            for company in companies:
                self.stdout.write(f"\n📋 Procesando: {company.partner.name}")

                stats = self._create_payment_terms_for_company(company, force, dry_run)
                total_created += stats["terms"]
                total_lines += stats["lines"]

        # Resumen
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("📊 RESUMEN DE TÉRMINOS DE PAGO")
        self.stdout.write("=" * 50)
        self.stdout.write(f"   ✅ Términos creados/actualizados: {total_created}")
        self.stdout.write(f"   📝 Líneas de término creadas: {total_lines}")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Términos de pago poblados exitosamente!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "\n🔍 SIMULACIÓN COMPLETADA: Revise los cambios propuestos"
                )
            )

    def _create_payment_terms_for_company(self, company, force=False, dry_run=False):
        """Crear términos de pago para una compañía"""
        terms_created = 0
        lines_created = 0

        # Definir todos los términos de pago a crear
        payment_terms_definitions = [
            {
                "code": f"IMMEDIATE_{company.id}",
                "name": f"Pago Inmediato - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 1,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total al momento de la facturación",
            },
            {
                "code": f"NET_7_{company.id}",
                "name": f"Neto 7 Días - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 7,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total a 7 días de la factura",
            },
            {
                "code": f"NET_15_{company.id}",
                "name": f"Neto 15 Días - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 15,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total a 15 días de la factura",
            },
            {
                "code": f"NET_30_{company.id}",
                "name": f"Neto 30 Días - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 30,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total a 30 días de la factura",
            },
            {
                "code": f"NET_60_{company.id}",
                "name": f"Neto 60 Días - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 60,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total a 60 días de la factura",
            },
            {
                "code": f"NET_90_{company.id}",
                "name": f"Neto 90 Días - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 90,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago total a 90 días de la factura",
            },
            {
                "code": f"15_NEXT_MONTH_{company.id}",
                "name": f"Día 15 Mes Siguiente - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "day_of_the_month": 15,
                        "option": "day_following_month",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago el día 15 del mes siguiente",
            },
            {
                "code": f"END_MONTH_{company.id}",
                "name": f"Fin de Mes - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 0,
                        "option": "end_of_month",
                        "value": "balance",
                        "value_amount": Decimal("100.00"),
                    }
                ],
                "description": "Pago al final del mes actual",
            },
            {
                "code": f"50_50_{company.id}",
                "name": f"50% Adelanto, 50% Neto 30 - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 0,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("50.00"),
                        "note": "Adelanto 50%",
                    },
                    {
                        "sequence": 20,
                        "days": 30,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("50.00"),
                        "note": "Saldo 50% a 30 días",
                    },
                ],
                "description": "50% adelanto, 50% a 30 días",
            },
            {
                "code": f"30_70_{company.id}",
                "name": f"30% Adelanto, 70% Contra Entrega - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 0,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("30.00"),
                        "note": "Adelanto 30%",
                    },
                    {
                        "sequence": 20,
                        "days": 0,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("70.00"),
                        "note": "70% contra entrega",
                    },
                ],
                "description": "30% adelanto, 70% contra entrega",
            },
            {
                "code": f"33_33_34_{company.id}",
                "name": f"Tres Pagos - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 0,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("33.33"),
                        "note": "Primer pago 33.33%",
                    },
                    {
                        "sequence": 20,
                        "days": 30,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("33.33"),
                        "note": "Segundo pago 33.33% a 30 días",
                    },
                    {
                        "sequence": 30,
                        "days": 60,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("33.34"),
                        "note": "Tercer pago 33.34% a 60 días",
                    },
                ],
                "description": "Tres pagos: 33.33% inicial, 33.33% a 30 días, 33.34% a 60 días",
            },
            {
                "code": f"PROGRESSIVE_{company.id}",
                "name": f"Pago Progresivo - {company.partner.name}",
                "lines": [
                    {
                        "sequence": 10,
                        "days": 0,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("25.00"),
                        "note": "25% al inicio",
                    },
                    {
                        "sequence": 20,
                        "days": 30,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("25.00"),
                        "note": "25% a 30 días",
                    },
                    {
                        "sequence": 30,
                        "days": 60,
                        "option": "day_after_invoice_date",
                        "value": "percent",
                        "value_amount": Decimal("25.00"),
                        "note": "25% a 60 días",
                    },
                    {
                        "sequence": 40,
                        "days": 90,
                        "option": "day_after_invoice_date",
                        "value": "balance",
                        "value_amount": Decimal("25.00"),
                        "note": "25% final a 90 días",
                    },
                ],
                "description": "Pagos progresivos cada 30 días",
            },
        ]

        for term_def in payment_terms_definitions:
            try:
                term_data = {
                    "code": term_def["code"],
                    "name": term_def["name"],
                    "company": company,
                    "is_active": True,
                }

                if force:
                    # Forzar creación/actualización
                    if not dry_run:
                        term, created = AccountPaymentTerm.objects.update_or_create(
                            code=term_def["code"], company=company, defaults=term_data
                        )
                    else:
                        # En modo simulación, solo verificar
                        exists = AccountPaymentTerm.objects.filter(
                            code=term_def["code"], company=company
                        ).exists()
                        term = None
                        created = not exists
                else:
                    # Solo crear si no existe
                    if not dry_run:
                        term, created = AccountPaymentTerm.objects.get_or_create(
                            code=term_def["code"], company=company, defaults=term_data
                        )
                    else:
                        exists = AccountPaymentTerm.objects.filter(
                            code=term_def["code"], company=company
                        ).exists()
                        term = None
                        created = not exists

                if created:
                    terms_created += 1
                    self.stdout.write(f"   ✅ Término: {term_def['name']}")

                    # Crear líneas del término
                    if not dry_run and term:
                        for line_def in term_def["lines"]:
                            line_data = {
                                "payment_term": term,
                                "sequence": line_def["sequence"],
                                "option": line_def["option"],
                                "value": line_def["value"],
                                "value_amount": line_def["value_amount"],
                            }

                            if "days" in line_def:
                                line_data["days"] = line_def["days"]
                            if "day_of_the_month" in line_def:
                                line_data["day_of_the_month"] = line_def[
                                    "day_of_the_month"
                                ]
                            if "note" in line_def:
                                line_data["note"] = line_def["note"]

                            AccountPaymentTermLine.objects.create(**line_data)
                            lines_created += 1

                    # En modo simulación, contar las líneas que se crearían
                    if dry_run:
                        lines_created += len(term_def["lines"])
                        line_count = len(term_def["lines"])
                        plural = "s" if line_count > 1 else ""
                        self.stdout.write(f"      📝 (+{line_count} línea{plural})")

                elif force and not dry_run:
                    # Actualizar término existente
                    self.stdout.write(f"   🔄 Actualizado: {term_def['name']}")
                    terms_created += 1

                    # Actualizar líneas (eliminar existentes y crear nuevas)
                    if term:
                        # Eliminar líneas existentes
                        term.lines.all().delete()

                        # Crear nuevas líneas
                        for line_def in term_def["lines"]:
                            line_data = {
                                "payment_term": term,
                                "sequence": line_def["sequence"],
                                "option": line_def["option"],
                                "value": line_def["value"],
                                "value_amount": line_def["value_amount"],
                            }

                            if "days" in line_def:
                                line_data["days"] = line_def["days"]
                            if "day_of_the_month" in line_def:
                                line_data["day_of_the_month"] = line_def[
                                    "day_of_the_month"
                                ]
                            if "note" in line_def:
                                line_data["note"] = line_def["note"]

                            AccountPaymentTermLine.objects.create(**line_data)
                            lines_created += 1

                else:
                    # Término ya existe (sin force)
                    self.stdout.write(f"   ℹ️ Ya existe: {term_def['name']}")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Error creando {term_def['name']}: {str(e)}"
                    )
                )

        return {"terms": terms_created, "lines": lines_created}
