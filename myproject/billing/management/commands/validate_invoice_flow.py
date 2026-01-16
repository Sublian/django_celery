# billing/scripts/validate_invoice_flow.py
from billing.services.batch_invoice_service import validate_subscription_invoiceability
from billing.models import SaleSubscription, AccountMove


def validate_complete_flow(company_id=None):
    """Validar el flujo completo de facturación"""

    # 1. Obtener suscripciones elegibles
    from billing.services.batch_invoice_service import BatchInvoiceService

    service = BatchInvoiceService(company_id)
    subscriptions = service._get_eligible_subscriptions(service.today)

    print(f"🔍 Suscripciones elegibles encontradas: {len(subscriptions)}")

    # 2. Validar cada suscripción
    for subscription in subscriptions:
        validation = validate_subscription_invoiceability(subscription.id)
        print(f"\n📋 Suscripción: {subscription.code}")
        print(f"   Puede facturar: {validation['can_invoice']}")
        print(f"   Razones: {', '.join(validation['reasons'])}")
        print(f"   Total estimado: {validation['estimated_total']}")

        # 3. Verificar facturas existentes
        existing_invoices = AccountMove.objects.filter(subscription=subscription)
        print(f"   Facturas existentes: {existing_invoices.count()}")

        for invoice in existing_invoices:
            print(f"     - {invoice.invoice_number}: {invoice.amount_total}")

    return len(subscriptions)
