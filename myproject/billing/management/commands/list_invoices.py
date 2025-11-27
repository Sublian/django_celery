# billing/management/commands/list_invoices.py
from django.core.management.base import BaseCommand
from billing.models import AccountMove

class Command(BaseCommand):
    help = 'Listar facturas creadas'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help='ID de la compañía específica'
        )
        parser.add_argument(
            '--state',
            type=str,
            default='draft',
            help='Estado de facturas a listar (draft, posted, canceled)'
        )
    
    def handle(self, *args, **options):
        company_id = options.get('company')
        state = options.get('state')
        
        invoices = AccountMove.objects.filter(state=state)
        if company_id:
            invoices = invoices.filter(company_id=company_id)
        
        invoices = invoices.select_related('partner', 'company', 'subscription')
        
        self.stdout.write(f"📄 Facturas en estado '{state}':")
        
        for invoice in invoices:
            self.stdout.write(
                f"   • {invoice.invoice_number}: "
                f"{invoice.partner.name} - "
                f"${invoice.amount_total:.2f} - "
                f"{invoice.invoice_date} - "
                f"Suscripción: {invoice.subscription.code if invoice.subscription else 'N/A'}"
            )
        
        self.stdout.write(f"📊 Total: {invoices.count()}")