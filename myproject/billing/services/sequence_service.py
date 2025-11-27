# billing/services/sequence_service.py
import logging
import re
from django.db import transaction
from django.db.models import Q
from ..models import Sequence, InvoiceSerie, AccountMove, Company, SaleSubscription

logger = logging.getLogger(__name__)

class SequenceService:
    """
    Servicio para manejar secuencias de documentos
    """
    
    def __init__(self, company_id=None):
        self.company_id = company_id
    
    def get_sequence(self, sequence_type, company, document_type=None):
        """
        Obtiene la secuencia apropiada basada en tipo y compañía
        
        Args:
            sequence_type: 'account.move' o 'sale.subscription'
            company: Instancia de Company
            document_type: Para account.move: 'invoice' o 'ticket'
        """
        if sequence_type == 'account.move':
            if document_type not in ['invoice', 'ticket']:
                raise ValueError("Para account.move, document_type debe ser 'invoice' o 'ticket'")
            
            sequence_code = f'account.move.{document_type}.{company.id}'
            
        elif sequence_type == 'sale.subscription':
            sequence_code = f'sale.subscription.{company.id}'
            
        else:
            raise ValueError("sequence_type debe ser 'account.move' o 'sale.subscription'")
        
        try:
            sequence = Sequence.objects.get(
                code=sequence_code,
                company=company,
                active=True
            )
            return sequence
        except Sequence.DoesNotExist:
            logger.error(f"Secuencia no encontrada: {sequence_code} para compañía {company}")
            raise
        
    def generate_next_reference(self, sequence_type, company, document_type=None):
        """
        Genera la próxima referencia
        """
        sequence = self.get_sequence(sequence_type, company, document_type)
        
        with transaction.atomic():
            next_reference = sequence.next_by_code()
            
            logger.info(f"📄 Referencia generada: {next_reference} "
                       f"(Tipo: {sequence_type}, Secuencia: {sequence.code})")
            
            return next_reference
    
    def generate_subscription_code(self, company):
        """Genera código único para suscripción"""
        return self.generate_next_reference('sale.subscription', company)
    
    def generate_invoice_reference(self, company, partner):
        """Genera referencia para factura/boleta basado en partner"""
        document_type = self._determine_document_type(partner)
        return self.generate_next_reference('account.move', company, document_type)
    
    def _determine_document_type(self, partner):
        """Determina si es factura o boleta basado en el partner"""
        if (partner.document_type == 'ruc' and 
            partner.num_document and 
            len(partner.num_document) == 11):
            return 'invoice'  # Factura para RUC
        else:
            return 'ticket'   # Boleta para otros documentos
    
    def sync_all_sequences(self, company_id=None):
        """
        Sincroniza todas las secuencias con las facturas existentes
        """
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)
        
        synced_count = 0
        for sequence in sequences:
            if sequence.sync_with_existing_invoices():
                synced_count += 1
                logger.info(f"🔄 Secuencia sincronizada: {sequence.code} -> {sequence.number_next}")
        
        return synced_count
    
    def validate_sequence_consistency(self, company_id=None):
        """
        Valida la consistencia de las secuencias vs facturas existentes
        """
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)
        
        inconsistencies = []
        
        for sequence in sequences:
            last_used = sequence.get_last_used_number()
            if last_used is not None and sequence.number_next <= last_used:
                inconsistencies.append({
                    'sequence': sequence.code,
                    'current_next': sequence.number_next,
                    'last_used': last_used,
                    'difference': last_used - sequence.number_next
                })
        
        return inconsistencies

# Funciones de conveniencia
def get_next_invoice_reference(company, document_type='factura'):
    """Obtiene la próxima referencia para factura"""
    service = SequenceService()
    return service.generate_next_reference(company, document_type)

def get_next_subscription_code(company):
    """Obtiene próximo código de suscripción"""
    service = SequenceService()
    return service.generate_subscription_code(company)

def sync_sequences(company_id=None):
    """Sincroniza todas las secuencias"""
    service = SequenceService()
    return service.sync_all_sequences(company_id)

def validate_sequences(company_id=None):
    """Valida consistencia de secuencias"""
    service = SequenceService()
    return service.validate_sequence_consistency(company_id)