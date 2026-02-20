"""
Validadores específicos para NubeFact.
Funciones reutilizables para validar datos antes de enviar.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_totals_consistency(data: Dict[str, Any]) -> None:
    """
    Valida que los totales matemáticos sean consistentes.
    
    Verifica:
    - Suma de items coincide con total
    - IGV calculado coincide con IGV proporcionado
    
    Args:
        data: Diccionario con datos del comprobante
    
    Raises:
        ValidationError: Si hay inconsistencia
    """
    try:
        # Validar total vs suma de items
        items = data.get("items", [])
        if items:
            items_total = sum(float(item.get("total", 0)) for item in items)
            invoice_total = float(data.get("total", 0))
            
            if abs(items_total - invoice_total) > 0.01:
                logger.warning(
                    f"Discrepancia en totales: suma items ({items_total:.2f}) != "
                    f"total ({invoice_total:.2f})"
                )
                raise ValidationError(
                    f"Total inconsistente: {invoice_total:.2f} vs suma items {items_total:.2f}"
                )
        
        # Validar IGV
        porcentaje_igv = float(data.get("porcentaje_de_igv", 18.0))
        total_gravada = float(data.get("total_gravada", 0))
        igv_proporcionado = float(data.get("total_igv", 0))
        
        igv_calculado = total_gravada * porcentaje_igv / 100
        
        if abs(igv_calculado - igv_proporcionado) > 0.01:
            logger.warning(
                f"Discrepancia en IGV: calculado {igv_calculado:.2f} != "
                f"proporcionado {igv_proporcionado:.2f}"
            )
            raise ValidationError(
                f"IGV inconsistente: {igv_proporcionado:.2f} vs calculado {igv_calculado:.2f}"
            )
            
    except (ValueError, KeyError, TypeError) as e:
        raise ValidationError(f"Error validando totales: {str(e)}")


def ensure_string_numbers(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Asegura que todos los campos numéricos sean strings.
    NubeFact espera strings, no números.
    
    Args:
        data: Datos a normalizar
    
    Returns:
        Datos con todos los valores numéricos como strings
    """
    result = data.copy()
    
    numeric_fields = [
        "tipo_de_comprobante", "numero", "sunat_transaction",
        "total_gravada", "total_igv", "total", "cantidad",
        "precio_unitario", "subtotal", "igv", "valor_unitario"
    ]
    
    def process_item(item):
        for field in numeric_fields:
            if field in item and item[field] is not None:
                if not isinstance(item[field], str):
                    item[field] = str(item[field])
        return item
    
    # Procesar campos principales
    for field in numeric_fields:
        if field in result and result[field] is not None:
            if not isinstance(result[field], str):
                result[field] = str(result[field])
    
    # Procesar items
    if "items" in result and isinstance(result["items"], list):
        result["items"] = [process_item(item) for item in result["items"]]
    
    return result


def sanitize_token(token: str) -> str:
    """
    Limpia un token eliminando espacios, saltos de línea y caracteres invisibles.
    
    Args:
        token: Token crudo desde BD
    
    Returns:
        Token limpio
    """
    if not token:
        return ""
    return token.strip().replace('\n', '').replace('\r', '')


def validate_ruc(ruc: str) -> str:
    """
    Valida formato de RUC peruano (11 dígitos).
    
    Args:
        ruc: Número de RUC
    
    Returns:
        RUC validado
    
    Raises:
        ValidationError: Si el formato es inválido
    """
    ruc_str = str(ruc).strip()
    
    if not ruc_str.isdigit():
        raise ValidationError(f"RUC debe contener solo dígitos: {ruc}")
    
    if len(ruc_str) != 11:
        raise ValidationError(f"RUC debe tener 11 dígitos, se recibieron {len(ruc_str)}")
    
    return ruc_str


def validate_dates_range(fecha_emision: str, fecha_vencimiento: str = None) -> None:
    """
    Valida que las fechas estén en un rango razonable.
    
    Args:
        fecha_emision: Fecha de emisión (DD-MM-YYYY)
        fecha_vencimiento: Fecha de vencimiento (opcional)
    
    Raises:
        ValidationError: Si las fechas son inválidas
    """
    from datetime import datetime, timedelta
    
    try:
        emision = datetime.strptime(fecha_emision, "%d-%m-%Y")
        
        # No debería ser futura (excepto pruebas)
        if emision > datetime.now() + timedelta(days=1):
            logger.warning(f"Fecha de emisión futura: {fecha_emision}")
        
        if fecha_vencimiento:
            vencimiento = datetime.strptime(fecha_vencimiento, "%d-%m-%Y")
            if vencimiento < emision:
                raise ValidationError(
                    f"Fecha de vencimiento {fecha_vencimiento} anterior a emisión {fecha_emision}"
                )
                
    except ValueError as e:
        raise ValidationError(f"Error validando fechas: {str(e)}")