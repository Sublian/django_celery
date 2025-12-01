# billing/management/commands/test_end_of_month_invoices.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import date, timedelta
from decimal import Decimal
import random
import calendar
from billing.models import (
    AccountMove, Partner, Company,
    Journal, InvoiceSerie, AccountPaymentTerm,
    Product, Tax
)
from billing.services.sequence_service import SequenceService


class Command(BaseCommand):
    help = 'Probar la funcionalidad de pago a fin de mes con diferentes escenarios'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de compañía específica'
        )
        parser.add_argument(
            '--create-invoices',
            action='store_true',
            help='Crear facturas de prueba'
        )
        parser.add_argument(
            '--test-scenarios',
            action='store_true',
            help='Ejecutar escenarios de prueba predefinidos'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2025,
            help='Año para las pruebas'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🧪 Probando funcionalidad de pago a fin de mes...')
        
        company_id = options.get('company_id')
        create_invoices = options.get('create_invoices')
        test_scenarios = options.get('test_scenarios')
        test_year = options.get('year')
        
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)
        
        if test_scenarios:
            self._run_test_scenarios(companies, test_year)
        elif create_invoices:
            self._create_test_invoices(companies)
        else:
            self._show_current_configuration(companies)
    
    def _show_current_configuration(self, companies):
        """Mostrar configuración actual de clientes"""
        for company in companies:
            self.stdout.write(f'\n📋 Compañía: {company.partner.name}')
            
            # Clientes con pago a fin de mes
            end_of_month_clients = Partner.objects.filter(
                companies=company,
                invoice_end_of_month_payment=True,
                is_customer=True
            ).count()
            
            total_clients = Partner.objects.filter(
                companies=company,
                is_customer=True
            ).count()
            
            self.stdout.write(f'   👥 Clientes con pago fin de mes: {end_of_month_clients}/{total_clients} ({(end_of_month_clients/total_clients*100 if total_clients > 0 else 0):.1f}%)')
            
            # Mostrar algunos clientes como ejemplo
            sample_clients = Partner.objects.filter(
                companies=company,
                invoice_end_of_month_payment=True,
                is_customer=True
            )[:3]
            
            for client in sample_clients:
                term_info = f" - Término: {client.payment_term.name}" if client.payment_term else ""
                self.stdout.write(f'      • {client.name}{term_info}')
            
            # Facturas con término fin de mes
            end_of_month_invoices = AccountMove.objects.filter(
                company=company,
                invoice_payment_term__lines__option='end_of_month'
            ).count()
            
            total_invoices = AccountMove.objects.filter(
                company=company,
                type='out_invoice'
            ).count()
            
            self.stdout.write(f'   🧾 Facturas con término fin de mes: {end_of_month_invoices}/{total_invoices}')
    
    def _run_test_scenarios(self, companies, test_year):
        """Ejecutar escenarios de prueba predefinidos"""
        test_cases = [
            # (mes, día, descripción, espera_hotfix)
            (1, 31, "Último día de Enero (31)", True),
            (2, 28, "28 de Febrero", True),
            (2, 29, "29 de Febrero (bisiesto)", True if calendar.isleap(test_year) else False),
            (3, 31, "Último día de Marzo (31)", True),
            (4, 30, "Último día de Abril (30)", True),
            (5, 15, "15 de Mayo (día normal)", False),
            (6, 30, "30 de Junio", True),
            (7, 31, "Último día de Julio (31)", True),
            (8, 31, "Último día de Agosto (31)", True),
            (9, 30, "Último día de Septiembre (30)", True),
            (10, 31, "Último día de Octubre (31)", True),
            (11, 30, "Último día de Noviembre (30)", True),
            (12, 31, "Último día de Diciembre (31)", True),
        ]
        
        self.stdout.write(f'\n🔬 ESCENARIOS DE PRUEBA - Año {test_year}')
        self.stdout.write('='*70)
        
        headers = ['Caso', 'Fecha Emisión', 'Descripción', 'Hotfix Esperado', 'Vencimiento Calculado', '✓/✗']
        header_line = ' | '.join(headers)
        self.stdout.write(header_line)
        self.stdout.write('-' * len(header_line))
        
        for company in companies:
            self.stdout.write(f'\n📋 Compañía: {company.partner.name}')
            
            # Obtener un cliente de prueba
            test_client = Partner.objects.filter(
                companies=company,
                is_customer=True
            ).first()
            
            if not test_client:
                self.stdout.write('   ⚠️  No hay clientes para probar')
                continue
            
            # Configurar cliente para prueba
            test_client.invoice_end_of_month_payment = True
            test_client.save()
            
            for i, (mes, dia, desc, espera_hotfix) in enumerate(test_cases, 1):
                try:
                    # Crear fecha de prueba
                    test_date = date(test_year, mes, dia)
                    
                    # Calcular vencimiento esperado
                    invoice = AccountMove(
                        partner=test_client,
                        company=company,
                        invoice_date=test_date
                    )
                    
                    # Simular que tiene término fin de mes
                    invoice.invoice_payment_term = AccountPaymentTerm.objects.filter(
                        company=company,
                        lines__option='end_of_month'
                    ).first()
                    
                    # Calcular fecha
                    due_date = invoice.calculate_due_date()
                    
                    # Determinar si se aplicó hotfix
                    dia_esperado = 28 if mes == 2 else 30
                    fecha_esperada_sin_hotfix = test_date.replace(day=dia_esperado)
                    
                    # Ajustar para meses con menos días
                    try:
                        fecha_esperada_sin_hotfix = test_date.replace(day=dia_esperado)
                    except ValueError:
                        _, ultimo_dia = calendar.monthrange(test_year, mes)
                        fecha_esperada_sin_hotfix = test_date.replace(day=ultimo_dia)
                    
                    hotfix_aplicado = due_date != fecha_esperada_sin_hotfix
                    
                    # Verificar resultado
                    resultado = "✓" if hotfix_aplicado == espera_hotfix else "✗"
                    
                    # Imprimir fila
                    fila = [
                        str(i),
                        test_date.strftime('%d/%m/%Y'),
                        desc,
                        "SÍ" if espera_hotfix else "NO",
                        due_date.strftime('%d/%m/%Y') if due_date else "ERROR",
                        resultado
                    ]
                    
                    self.stdout.write(' | '.join(fila))
                    
                except Exception as e:
                    self.stdout.write(f'   ❌ Error en caso {i}: {str(e)}')
    
    def _create_test_invoices(self, companies):
        """Crear facturas de prueba para validar la funcionalidad"""
        total_created = 0
        
        with transaction.atomic():
            for company in companies:
                self.stdout.write(f'\n📋 Compañía: {company.partner.name}')
                
                # Obtener datos necesarios
                service = SequenceService()
                
                # Clientes con diferentes configuraciones
                clients_with_end_of_month = Partner.objects.filter(
                    companies=company,
                    invoice_end_of_month_payment=True,
                    is_customer=True
                )[:2]
                
                clients_without_end_of_month = Partner.objects.filter(
                    companies=company,
                    invoice_end_of_month_payment=False,
                    is_customer=True
                )[:2]
                
                journals = Journal.objects.filter(company=company, is_active=True)
                series = InvoiceSerie.objects.filter(company=company, is_active=True)
                
                # Términos de pago
                end_of_month_term = AccountPaymentTerm.objects.filter(
                    company=company,
                    lines__option='end_of_month'
                ).first()
                
                regular_term = AccountPaymentTerm.objects.filter(
                    company=company,
                    lines__option='day_after_invoice_date'
                ).first()
                
                # Crear facturas para clientes CON pago fin de mes
                self.stdout.write('   🏦 Clientes CON pago fin de mes:')
                for client in clients_with_end_of_month:
                    try:
                        invoice = self._create_test_invoice(
                            client, company, service, journals, series,
                            end_of_month_term if end_of_month_term else regular_term
                        )
                        
                        if invoice:
                            total_created += 1
                            self.stdout.write(f'      ✅ {client.name}: {invoice.invoice_number}')
                            self.stdout.write(f'          Emisión: {invoice.invoice_date.strftime("%d/%m/%Y")}')
                            self.stdout.write(f'          Vence: {invoice.invoice_date_due.strftime("%d/%m/%Y") if invoice.invoice_date_due else "N/A"}')
                            self.stdout.write(f'          Días: {(invoice.invoice_date_due - invoice.invoice_date).days if invoice.invoice_date_due else "N/A"}')
                    except Exception as e:
                        self.stdout.write(f'      ❌ Error: {str(e)}')
                
                # Crear facturas para clientes SIN pago fin de mes
                self.stdout.write('   👤 Clientes SIN pago fin de mes:')
                for client in clients_without_end_of_month:
                    try:
                        invoice = self._create_test_invoice(
                            client, company, service, journals, series,
                            regular_term
                        )
                        
                        if invoice:
                            total_created += 1
                            self.stdout.write(f'      ✅ {client.name}: {invoice.invoice_number}')
                            self.stdout.write(f'          Emisión: {invoice.invoice_date.strftime("%d/%m/%Y")}')
                            self.stdout.write(f'          Vence: {invoice.invoice_date_due.strftime("%d/%m/%Y") if invoice.invoice_date_due else "N/A"}')
                    except Exception as e:
                        self.stdout.write(f'      ❌ Error: {str(e)}')
        
        self.stdout.write(f'\n🎯 Total facturas de prueba creadas: {total_created}')
        self.stdout.write(self.style.SUCCESS('✅ Pruebas completadas exitosamente!'))
    
    def _create_test_invoice(self, client, company, service, journals, series, payment_term):
        """Crear una factura de prueba individual"""
        # Determinar tipo de documento
        if client.document_type == 'ruc' and client.num_document and len(client.num_document) == 11:
            document_type = 'invoice'
            serie = series.filter(series__startswith='F').first()
        else:
            document_type = 'ticket'
            serie = series.filter(series__startswith='B').first()
        
        if not serie:
            return None
        
        # Obtener journal
        journal = journals.filter(
            code__contains='INV' if document_type == 'invoice' else 'TKT'
        ).first() or journals.first()
        
        # Generar referencia
        reference = service.generate_next_reference(
            'account.move',
            company,
            document_type
        )
        
        # Fecha de emisión (últimos 30 días)
        invoice_date = timezone.now().date() - timedelta(days=random.randint(0, 30))
        
        # Crear factura
        invoice = AccountMove.objects.create(
            invoice_number=reference,
            partner=client,
            journal=journal,
            company=company,
            currency=company.currency,
            type='out_invoice',
            ref=reference,
            name=f"Factura Prueba {reference}",
            invoice_date=invoice_date,
            serie=serie,
            invoice_payment_term=payment_term,
            state='posted',
            amount_total=Decimal('1000.00'),
            amount_tax=Decimal('180.00')
        )
        
        return invoice