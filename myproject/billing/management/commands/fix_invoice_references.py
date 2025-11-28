# billing/management/commands/fix_invoice_references.py
from django.core.management.base import BaseCommand
from billing.models import AccountMove
import re
from datetime import datetime

class Command(BaseCommand):
    help = 'Corregir referencias y números de factura incorrectos'
    
    def handle(self, *args, **options):
        self.stdout.write('🔧 Corrigiendo referencias de facturas...')
        
        invoices = AccountMove.objects.all()
        fixed_refs = 0
        fixed_numbers = 0
        
        for invoice in invoices:
            # CORREGIR referencia (ref)
            old_ref = invoice.ref
            if old_ref and old_ref.startswith('SUB-SUB'):
                # Formato incorrecto: SUB-SUB01-020006-202511
                # Formato correcto: SUB01-0200062511
                parts = old_ref.split('-')
                if len(parts) >= 3:
                    sub_code = parts[1]  # SUB01-020006
                    date_part = parts[2] if len(parts) > 2 else "202511"
                    
                    # Extraer números y fecha
                    numbers = re.findall(r'\d+', sub_code)
                    if numbers:
                        company_id = numbers[0] if len(numbers) > 0 else "01"
                        partner_id = numbers[1] if len(numbers) > 1 else "000000"
                        
                        # Nuevo formato: SUB01-0200062511
                        new_ref = f"SUB{company_id.zfill(2)}-{partner_id.zfill(6)}{date_part[-4:]}"
                        invoice.ref = new_ref
                        fixed_refs += 1
                        self.stdout.write(f"   🔄 REF: {old_ref} → {new_ref}")
            
            # CORREGIR número de factura (invoice_number)
            old_number = invoice.invoice_number
            if old_number and re.match(r'^F\d{2}-\d+-\d+$', old_number):
                # Formato incorrecto: F01-89-202511
                # Formato correcto: F001-000000892511
                parts = old_number.split('-')
                if len(parts) == 3:
                    letter = parts[0][0]  # F o B
                    company_id = parts[0][1:]  # 01
                    doc_number = parts[1]  # 89
                    date_part = parts[2]  # 202511
                    
                    # Nuevo formato: F001-000000892511
                    new_number = f"{letter}001-{doc_number.zfill(8)}{date_part[-4:]}"
                    invoice.invoice_number = new_number
                    fixed_numbers += 1
                    self.stdout.write(f"   🔄 NUM: {old_number} → {new_number}")
            
            invoice.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ {fixed_refs} referencias y {fixed_numbers} números corregidos'
            )
        )