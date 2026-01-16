# billing/services/sequence_service.py
from datetime import time
import logging
import re
from django.db import OperationalError, transaction
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
        if sequence_type == "account.move":
            if document_type not in ["invoice", "ticket"]:
                raise ValueError(
                    "Para account.move, document_type debe ser 'invoice' o 'ticket'"
                )

            sequence_code = f"account.move.{document_type}.{company.id}"

        elif sequence_type == "sale.subscription":
            sequence_code = f"sale.subscription.{company.id}"

        else:
            raise ValueError(
                "sequence_type debe ser 'account.move' o 'sale.subscription'"
            )

        try:
            sequence = Sequence.objects.get(
                code=sequence_code, company=company, active=True
            )
            return sequence
        except Sequence.DoesNotExist:
            logger.error(
                f"Secuencia no encontrada: {sequence_code} para compañía {company}"
            )
            raise

    def get_document_type(self, partner):
        """
        Determina si es factura o boleta basado en el partner
        """
        # Factura: RUC con 11 dígitos
        # Boleta: DNI, CE, Pasaporte, etc.
        if (
            partner.document_type == "ruc"
            and partner.num_document
            and len(partner.num_document) == 11
        ):
            return "invoice"  # Factura
        else:
            return "ticket"  # Boleta

    def get_sequence_for_partner(self, company, partner):
        """
        Obtiene la secuencia apropiada para un partner
        """
        document_type = self.get_document_type(partner)
        return self.get_sequence("account.move", company, document_type)

    def generate_next_reference(
        self, sequence_type, company, document_type=None, retries=3
    ):
        """Genera la próxima referencia - VERSIÓN CORREGIDA - Versión con reintentos"""
        for attempt in range(retries):
            try:

                sequence = self.get_sequence(sequence_type, company, document_type)
                # logger.info(f"   🔄️ Obtained sequence: {sequence.code} for company {company}")

                # Usamos un bloque atómico con lock explícito
                with transaction.atomic():
                    # Forzamos el lock de la secuencia para evitar duplicados concurrentes
                    locked_sequence = Sequence.objects.select_for_update(
                        nowait=True  # Esto evita deadlocks
                    ).get(id=sequence.id)

                    next_reference = locked_sequence.next_by_code()

                    if self.verify_unique_reference(
                        next_reference, sequence_type, company, document_type
                    ):
                        return next_reference
                    else:
                        logger.warning(
                            f"Referencia duplicada generada: {next_reference}. Reintentando..."
                        )
                        continue  # Reintentar

            except OperationalError as e:
                # Deadlock o timeout, reintentar
                if attempt < retries - 1:
                    logger.warning(f"Intento {attempt + 1} fallado, reintentando...")
                    time.sleep(0.1 * (attempt + 1))  # Backoff exponencial
                else:
                    raise

    def generate_subscription_code(self, company):
        """Genera código único para suscripción - VERSIÓN CORREGIDA"""
        return self.generate_next_reference("sale.subscription", company)

    def generate_invoice_reference(self, company, partner):
        """Genera referencia para factura/boleta basado en partner"""
        document_type = self._determine_document_type(partner)
        logger.info(
            f"   🔄️ Determined document type: {document_type} for partner {partner}"
        )
        return self.generate_next_reference("account.move", company, document_type)

    def _determine_document_type(self, partner):
        """Determina si es factura o boleta basado en el partner"""
        if (
            partner.document_type == "ruc"
            and partner.num_document
            and len(partner.num_document) == 11
        ):
            return "invoice"  # Factura para RUC
        else:
            return "ticket"  # Boleta para otros documentos

    def sync_all_sequences(self, company_id=None):
        """
        Sincroniza todas las secuencias con las facturas existentes
        """
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)

        synced_count = 0
        for sequence in sequences:
            if self._safe_sync_sequence(sequence):
                synced_count += 1

        return synced_count

    def _safe_sync_sequence(self, sequence):
        """Sincroniza una secuencia de forma segura"""
        try:
            last_used = sequence.get_last_used_number()
            logger.info(f"🔄 Secuencia {sequence.code}: último usado {last_used}")

            if last_used is not None:
                # Asegurar que number_next sea mayor que el último usado
                if sequence.number_next <= last_used:
                    sequence.number_next = last_used + sequence.number_increment
                    sequence.save(update_fields=["number_next", "updated_at"])
                    logger.info(
                        f"✅ Secuencia sincronizada: {sequence.code} -> {sequence.number_next}"
                    )
                    return True
        except Exception as e:
            logger.error(f"❌ Error sincronizando secuencia {sequence.code}: {e}")

        return False

    def validate_sequence_consistency(self, company_id=None):
        """
        Valida la consistencia de las secuencias vs facturas existentes
        """
        sequences = Sequence.objects.filter(active=True)
        if company_id:
            sequences = sequences.filter(company_id=company_id)

        inconsistencies = []

        for sequence in sequences:
            try:

                last_used = sequence.get_last_used_number()
                if last_used is not None and sequence.number_next <= last_used:
                    inconsistencies.append(
                        {
                            "sequence": sequence.code,
                            "current_next": sequence.number_next,
                            "last_used": last_used,
                            "difference": last_used - sequence.number_next,
                            "status": "⚠️ REQUIERE SINCRONIZACIÓN",
                        }
                    )
            except Exception as e:
                logger.error(f"❌ Error validando secuencia {sequence.code}: {e}")
                inconsistencies.append(
                    {"sequence": sequence.code, "error": str(e), "status": "❌ ERROR"}
                )

        return inconsistencies

    def verify_unique_reference(
        self, reference, sequence_type, company, document_type=None
    ):
        """
        Verifica que una referencia no esté ya en uso
        """
        if sequence_type == "account.move":
            # Buscar en AccountMove
            exists = AccountMove.objects.filter(
                invoice_number=reference, company=company
            ).exists()

            if exists:
                logger.warning(f"Referencia duplicada encontrada: {reference}")
                return False

        elif sequence_type == "sale.subscription":
            # Buscar en SaleSubscription
            exists = SaleSubscription.objects.filter(
                code=reference, company=company
            ).exists()

            if exists:
                logger.warning(f"Código de suscripción duplicado: {reference}")
                return False

        return True


# Funciones de conveniencia
def get_next_invoice_reference(company, document_type="factura"):
    """Obtiene la próxima referencia para factura"""
    service = SequenceService()
    return service.generate_invoice_reference(company, document_type)
    # return service.generate_next_reference(company, document_type)


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


def get_document_type(partner):
    service = SequenceService()
    return service.get_document_type(partner)
