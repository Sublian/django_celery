# billing/management/commands/test_batch_invoicing.py
from django.core.management.base import BaseCommand
from billing.services.batch_invoice_service import (
    generate_batch_invoices, 
    validate_subscription_invoiceability,
    get_pending_invoices_count
)
from billing.models import SaleSubscription

class Command(BaseCommand):
    help = 'Probar el sistema de facturación por lotes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help='ID de la compañía específica'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación'
        )
        parser.add_argument(
            '--validate',
            type=int,
            help='Validar una suscripción específica por ID'
        )
        parser.add_argument(
            '--list-pending',
            action='store_true',
            help='Listar suscripciones pendientes de facturación'
        )
    
    def handle(self, *args, **options):
        company_id = options.get('company')
        dry_run = options.get('dry_run')
        validate_id = options.get('validate')
        list_pending = options.get('list_pending')
        
        if validate_id:
            # Validar suscripción específica
            self._validate_subscription(validate_id)
            return
        
        if list_pending:
            # Listar suscripciones pendientes
            self._list_pending_subscriptions(company_id)
            return
        
        # Mostrar pendientes y ejecutar generación
        self._run_batch_invoicing(company_id, dry_run)
    
    def _validate_subscription(self, subscription_id):
        """Validar una suscripción específica"""
        try:
            result = validate_subscription_invoiceability(subscription_id)
            self.stdout.write(f"🔍 Validación suscripción {subscription_id}:")
            self.stdout.write(f"   Puede facturar: {result['can_invoice']}")
            self.stdout.write(f"   Razones: {', '.join(result['reasons'])}")
            self.stdout.write(f"   Total estimado: ${result.get('estimated_total', 0):.2f}")
            self.stdout.write(f"   Próxima fecha: {result.get('next_invoice_date', 'N/A')}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error validando suscripción: {str(e)}"))
    
    def _list_pending_subscriptions(self, company_id):
        """Listar suscripciones pendientes de facturación"""
        from django.utils import timezone
        from django.db.models import Q
        
        # Obtener suscripciones elegibles
        subscriptions = SaleSubscription.objects.filter(
            Q(state='active') | Q(state='in_renewal'),
            is_active=True,
            next_invoice_date__lte=timezone.now().date()
        )
        
        if company_id:
            subscriptions = subscriptions.filter(company_id=company_id)
        
        subscriptions = subscriptions.select_related('partner', 'company', 'contract_template')
        
        self.stdout.write("📋 Suscripciones pendientes de facturación:")
        
        for sub in subscriptions:
            self.stdout.write(
                f"   • {sub.code}: {sub.partner.name} "
                f"({sub.company}) - "
                f"Próxima: {sub.next_invoice_date} - "
                f"Plantilla: {sub.contract_template.name if sub.contract_template else 'N/A'}"
            )
        
        self.stdout.write(f"📊 Total pendientes: {subscriptions.count()}")
    
    def _run_batch_invoicing(self, company_id, dry_run):
        """Ejecutar generación de facturas por lote"""
        # Mostrar pendientes
        pending = get_pending_invoices_count(company_id)
        self.stdout.write(f"📊 Facturas pendientes: {pending}")
        
        if pending > 0:
            # Ejecutar generación
            result = generate_batch_invoices(
                company_id=company_id,
                dry_run=dry_run
            )
            
            self.stdout.write("📊 RESULTADOS:")
            self.stdout.write(f"   Procesadas: {result['processed']}")
            self.stdout.write(f"   Creadas: {result['created']}")
            self.stdout.write(f"   Errores: {result['errors']}")
            self.stdout.write(f"   Saltadas: {result['skipped']}")
            
            # Mostrar detalles si hay
            if result.get('details'):
                self.stdout.write("   Detalles:")
                for detail in result['details'][-10:]:  # Últimos 10 detalles
                    self.stdout.write(f"     • {detail}")
            
            if dry_run:
                self.stdout.write("💡 EJECUTADO EN MODO SIMULACIÓN")
        else:
            self.stdout.write("✅ No hay facturas pendientes para generar")