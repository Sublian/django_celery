# billing/management/commands/populate_customers.py
from django.core.management.base import BaseCommand
from billing.models import Partner, Company
from django.utils import timezone
import random


class Command(BaseCommand):
    help = "Poblar clientes de prueba para facturas y boletas"

    def handle(self, *args, **options):
        self.stdout.write("👥 Poblando clientes de prueba...")

        companies = Company.objects.all()

        # Datos de clientes para pruebas
        customers_data = [
            # === CLIENTES CON RUC (FACTURAS) ===
            {
                "name": "AGROLIGHT PERU S.A.C.",
                "document_type": "ruc",
                "num_document": "20552103816",
            },
            {
                "name": "BI GRAND CONFECCIONES S.A.C.",
                "document_type": "ruc",
                "num_document": "20553856451",
            },
            {
                "name": "D'AROMAS E.I.R.L.",
                "document_type": "ruc",
                "num_document": "20480316259",
            },
            {
                "name": "TECNOLOGIA AVANZADA S.A.",
                "document_type": "ruc",
                "num_document": "20123456789",
            },
            {
                "name": "CONSULTORES ASOCIADOS E.I.R.L.",
                "document_type": "ruc",
                "num_document": "20456789012",
            },
            {
                "name": "INVERSIONES DEL NORTE S.A.C.",
                "document_type": "ruc",
                "num_document": "20678901234",
            },
            {
                "name": "SERVICIOS INTEGRALES S.A.",
                "document_type": "ruc",
                "num_document": "20789012345",
            },
            {
                "name": "CONSTRUCCIONES MODERNAS S.A.C.",
                "document_type": "ruc",
                "num_document": "20890123456",
            },
            # === CLIENTES CON DNI (BOLETAS) ===
            {
                "name": "Juan Pérez López",
                "document_type": "dni",
                "num_document": "46789231",
            },
            {
                "name": "María García Soto",
                "document_type": "dni",
                "num_document": "53216789",
            },
            {
                "name": "ALBA CARRION CRISTIAN ERICK",
                "document_type": "dni",
                "num_document": "45650699",
            },
            {
                "name": "ALBAN CHUQUIPOMA MIRIAM JACKELINE",
                "document_type": "dni",
                "num_document": "18195497",
            },
            {
                "name": "AMANQUI CONDORI ASTRID VANESA ELLY",
                "document_type": "dni",
                "num_document": "72664197",
            },
            {
                "name": "AGIP RUBIO RICARDO GERMAN",
                "document_type": "dni",
                "num_document": "27440013",
            },
            {
                "name": "Carlos Rodríguez Mendoza",
                "document_type": "dni",
                "num_document": "12345678",
            },
            {
                "name": "Ana Martínez Silva",
                "document_type": "dni",
                "num_document": "87654321",
            },
            # === CLIENTES CON CE (BOLETAS) ===
            {
                "name": "ARTROSCOPICTRAUMA S.A.C.",
                "document_type": "ce",
                "num_document": "002370805",
            },
            {"name": "John Smith", "document_type": "ce", "num_document": "X1234567"},
            {
                "name": "Maria Rodriguez",
                "document_type": "ce",
                "num_document": "Y9876543",
            },
            {"name": "Carlos Lopez", "document_type": "ce", "num_document": "Z5555555"},
            # === CLIENTES CON OTRO (BOLETAS) ===
            {
                "name": "Sophie Dubois",
                "document_type": "pasaporte",
                "num_document": "P87654321",
            },
            {
                "name": "Hans Mueller",
                "document_type": "pasaporte",
                "num_document": "P12349876",
            },
            {
                "name": "Empresa Extranjera LLC",
                "document_type": "otro",
                "num_document": "EXT123456",
            },
        ]

        total_created = 0

        for company in companies:
            self.stdout.write(f"🏢 Procesando compañía: {company.partner.name}")

            created_for_company = 0

            random_customer_data = random.sample(customers_data, len(customers_data))
            for customer_data in random_customer_data[
                :15
            ]:  # Limitar a 15 clientes por compañía
                try:
                    # Crear o obtener partner
                    partner, created = Partner.objects.get_or_create(
                        num_document=customer_data["num_document"],
                        defaults={
                            "name": customer_data["name"],
                            "display_name": customer_data["name"],
                            "document_type": customer_data["document_type"],
                            "is_customer": True,
                            "is_active": True,
                        },
                    )

                    # Asociar partner con compañía (si no está ya asociado)
                    if company not in partner.companies.all():
                        partner.companies.add(company)
                        created_for_company += 1

                        doc_type = (
                            "FACTURA"
                            if customer_data["document_type"] == "ruc"
                            else "BOLETA"
                        )
                        self.stdout.write(f"   ✅ {customer_data['name']} - {doc_type}")

                except Exception as e:
                    self.stdout.write(
                        f"   ❌ Error con {customer_data['name']}: {str(e)}"
                    )

            total_created += created_for_company
            self.stdout.write(
                f"   📊 Clientes asociados a {company.partner.name}: {created_for_company}"
            )

        self.stdout.write(
            f"\n🎯 Total de asociaciones cliente-compañía creadas: {total_created}"
        )
        self.stdout.write(self.style.SUCCESS("✅ Clientes poblados exitosamente!"))
