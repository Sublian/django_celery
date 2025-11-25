# billing/management/commands/populate_initial_sequence.py

# run in yout terminal: python manage.py populate_initial_sequence

from django.core.management.base import BaseCommand
from billing.models import Sequence, Company, Partner

class Command(BaseCommand):
    help = 'Crear secuencias de prueba para facturas y boletas'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Creando secuencias de prueba...')
        
        # Obtener compañías de los partners 2 y 3
        try:
            partner_2 = Partner.objects.get(id=2)
            partner_3 = Partner.objects.get(id=3)
            
            company_2 = Company.objects.filter(partner=partner_2).first()
            company_3 = Company.objects.filter(partner=partner_3).first()
        except Partner.DoesNotExist:
            self.stdout.write("⚠️ Partners 2 y/o 3 no existen. Usando compañías por defecto.")
            company_2 = Company.objects.first()
            company_3 = Company.objects.last() if Company.objects.count() > 1 else Company.objects.first()

        # Secuencias para compañía 2
        sequences_company_2 = [
            {
                'name': 'Secuencia de Factura Electronica F001-NEXT',
                'code': 'sequence.factura.company2',
                'prefix': 'F001-',
                'number_next': 10000,
                'number_increment': 1,
                'padding': 8,
                'company': company_2
            },
            {
                'name': 'Secuencia de Boleta Electronica B001-NEXT',
                'code': 'sequence.boleta.company2', 
                'prefix': 'B001-',
                'number_next': 1000,
                'number_increment': 1,
                'padding': 8,
                'company': company_2
            }
        ]

        # Secuencias para compañía 3
        sequences_company_3 = [
            {
                'name': 'Secuencia de Factura Electronica F001-FLX TECH',
                'code': 'sequence.factura.company3',
                'prefix': 'F001-',
                'number_next': 50000,
                'number_increment': 1,
                'padding': 8,
                'company': company_3
            },
            {
                'name': 'Secuencia de Boleta Electronica B001-FLX TECH',
                'code': 'sequence.boleta.company3',
                'prefix': 'B001-',
                'number_next': 5000,
                'number_increment': 1,
                'padding': 8,
                'company': company_3
            }
        ]

        all_sequences = sequences_company_2 + sequences_company_3

        for seq_data in all_sequences:
            sequence, created = Sequence.objects.get_or_create(
                code=seq_data['code'],
                defaults=seq_data
            )
            if created:
                self.stdout.write(f"✅ Secuencia creada: {sequence.name}")
            else:
                self.stdout.write(f"⚠️ Secuencia ya existe: {sequence.name}")

        self.stdout.write(
            self.style.SUCCESS('✅ Secuencias creadas exitosamente!')
        )