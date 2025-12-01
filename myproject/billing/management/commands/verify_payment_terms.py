# billing/management/commands/verify_payment_terms.py
from django.core.management.base import BaseCommand
from billing.models import AccountPaymentTerm, AccountPaymentTermLine, Company

class Command(BaseCommand):
    help = 'Verificar integridad de términos de pago'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de compañía específica'
        )
        parser.add_argument(
            '--detail',
            action='store_true',
            help='Mostrar detalle de cada término'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('🔍 Verificando términos de pago...')
        
        company_id = options.get('company_id')
        show_detail = options.get('detail')
        
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)
        
        total_terms = 0
        total_lines = 0
        issues = []
        
        for company in companies:
            self.stdout.write(f'\n📋 Compañía: {company.partner.name}')
            
            terms = AccountPaymentTerm.objects.filter(company=company, is_active=True)
            term_count = terms.count()
            total_terms += term_count
            
            self.stdout.write(f'   📄 Términos activos: {term_count}')
            
            if term_count == 0:
                issues.append({
                    'company': company.partner.name,
                    'issue': 'No tiene términos de pago activos',
                    'severity': 'error'
                })
            
            for term in terms:
                line_count = term.lines.count()
                total_lines += line_count
                
                if line_count == 0:
                    issues.append({
                        'company': company.partner.name,
                        'term': term.name,
                        'issue': 'No tiene líneas configuradas',
                        'severity': 'error'
                    })
                
                # Verificar suma de porcentajes para términos fraccionados
                if any(line.value == 'percent' for line in term.lines.all()):
                    total_percent = sum(
                        line.value_amount 
                        for line in term.lines.all() 
                        if line.value == 'percent'
                    )
                    
                    # Verificar si hay balance line
                    has_balance = any(line.value == 'balance' for line in term.lines.all())
                    
                    if not has_balance and total_percent != 100:
                        issues.append({
                            'company': company.partner.name,
                            'term': term.name,
                            'issue': f'Suma de porcentajes: {total_percent}% (debe ser 100%)',
                            'severity': 'warning'
                        })
                
                # Mostrar detalle si se solicita
                if show_detail:
                    self.stdout.write(f'      • {term.name}:')
                    for line in term.lines.all().order_by('sequence'):
                        line_desc = self._describe_line(line)
                        self.stdout.write(f'         → {line_desc}')
        
        # Mostrar resumen
        self.stdout.write('\n' + '='*50)
        self.stdout.write('📊 RESUMEN DE TÉRMINOS DE PAGO')
        self.stdout.write('='*50)
        self.stdout.write(f'   🏢 Compañías verificadas: {companies.count()}')
        self.stdout.write(f'   📄 Términos activos: {total_terms}')
        self.stdout.write(f'   📝 Líneas totales: {total_lines}')
        self.stdout.write(f'   📈 Promedio líneas/término: {total_lines/max(total_terms, 1):.1f}')
        
        # Mostrar issues
        if issues:
            self.stdout.write('\n' + self.style.WARNING('⚠️  PROBLEMAS ENCONTRADOS:'))
            
            errors = [i for i in issues if i['severity'] == 'error']
            warnings = [i for i in issues if i['severity'] == 'warning']
            
            if errors:
                self.stdout.write(self.style.ERROR('\n❌ ERRORES CRÍTICOS:'))
                for issue in errors:
                    if 'term' in issue:
                        self.stdout.write(f'   • {issue["company"]} - {issue["term"]}: {issue["issue"]}')
                    else:
                        self.stdout.write(f'   • {issue["company"]}: {issue["issue"]}')
            
            if warnings:
                self.stdout.write(self.style.WARNING('\n⚠️  ADVERTENCIAS:'))
                for issue in warnings:
                    self.stdout.write(f'   • {issue["company"]} - {issue["term"]}: {issue["issue"]}')
            
            self.stdout.write(f'\n💡 Recomendaciones:')
            self.stdout.write(f'   1. Ejecute: python manage.py populate_payment_terms --force')
            self.stdout.write(f'   2. Revise términos sin líneas o con porcentajes incorrectos')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Todos los términos de pago están correctos!'))
    
    def _describe_line(self, line):
        """Describir una línea de término de pago en texto legible"""
        parts = []
        
        # Valor
        if line.value == 'percent':
            parts.append(f"{line.value_amount}%")
        elif line.value == 'fixed':
            parts.append(f"${line.value_amount} fijo")
        else:  # balance
            parts.append("saldo")
        
        # Condición de tiempo
        if line.option == 'day_after_invoice_date':
            if line.days == 0:
                parts.append("al contado")
            else:
                parts.append(f"a {line.days} días")
        elif line.option == 'day_following_month':
            parts.append(f"día {line.day_of_the_month} del mes siguiente")
        elif line.option == 'end_of_month':
            parts.append("fin de mes")
        elif line.option == 'days_after_end_of_month':
            parts.append(f"{line.days} días después de fin de mes")
        
        # Nota si existe
        if line.note:
            parts.append(f"({line.note})")
        
        return " ".join(parts)