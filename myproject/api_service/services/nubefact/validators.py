"""
Módulo de validadores para Nubefact.

Proporciona funciones reutilizables para validar y normalizar datos
antes de enviarlos a la API de Nubefact.

Ejemplo:
    >>> from validators import validate_json_structure
    >>> datos = {...}
    >>> validados = validate_json_structure(datos)
"""

import logging
from datetime import datetime
from typing import Dict, Any
from decimal import Decimal
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_json_structure(data: dict) -> dict:
    """
    Valida y normaliza la estructura del JSON para Nubefact.

    Realiza las siguientes transformaciones:
    - Convierte fechas de YYYY-MM-DD a DD-MM-YYYY
    - Convierte strings vacíos en campos numéricos a 0
    - Valida que los totales sean consistentes

    Args:
        data (dict): Diccionario con los datos del comprobante

    Returns:
        dict: Diccionario normalizado y validado

    Raises:
        ValidationError: Si los datos no pasan validación

    Example:
        >>> datos = {
        ...     'fecha_de_emision': '2024-01-15',
        ...     'total_igv': '',
        ...     'items': [...]
        ... }
        >>> validados = validate_json_structure(datos)
        >>> print(validados['fecha_de_emision'])
        '15-01-2024'
    """
    validated_data = data.copy()

    # Campos de fecha: convertir de YYYY-MM-DD a DD-MM-YYYY
    date_fields = ["fecha_de_emision", "fecha_de_vencimiento"]
    for field in date_fields:
        if field in validated_data and validated_data[field]:
            try:
                value = str(validated_data[field]).strip()
                if "-" in value:
                    # Detectar formato
                    if value.count("-") == 2:
                        parts = value.split("-")

                        # Si es YYYY-MM-DD (primeros 4 caracteres son año)
                        if len(parts[0]) == 4:
                            date_obj = datetime.strptime(value, "%Y-%m-%d")
                        # Si es DD-MM-YYYY
                        elif len(parts[2]) == 4:
                            date_obj = datetime.strptime(value, "%d-%m-%Y")
                        else:
                            raise ValueError(f"Formato de fecha no reconocido: {value}")

                        validated_data[field] = date_obj.strftime("%d-%m-%Y")
                    else:
                        raise ValueError(f"Formato de fecha inválido: {value}")

            except ValueError as e:
                raise ValidationError(f"Error validando {field}: {str(e)}")

    # Campos numéricos: convertir strings vacíos a 0
    numeric_fields = [
        "total_igv",
        "total",
        "descuento_global",
        "total_descuento",
        "detraccion_total",
        "detraccion_porcentaje",
    ]
    for field in numeric_fields:
        if field in validated_data:
            if (
                isinstance(validated_data[field], str)
                and validated_data[field].strip() == ""
            ):
                validated_data[field] = 0
            # Convertir Decimal a float si es necesario
            elif isinstance(validated_data[field], Decimal):
                validated_data[field] = float(validated_data[field])

    # Validar que los totales sean consistentes
    validate_totals(validated_data)

    logger.debug(f"Datos validados y normalizados correctamente")
    return validated_data


def validate_totals(data: dict) -> None:
    """
    Valida que los totales matemáticos sean correctos.

    Verifica:
    - Suma de items coincide con total del comprobante
    - IGV calculado coincide con IGV proporcionado

    Args:
        data (dict): Diccionario con los datos del comprobante

    Raises:
        ValidationError: Si los cálculos no son consistentes

    Example:
        >>> datos = {
        ...     'items': [
        ...         {'total': 100},
        ...         {'total': 50}
        ...     ],
        ...     'total': 150,
        ...     'total_gravada': 127.12,
        ...     'total_igv': 22.88,
        ...     'porcentaje_de_igv': 18
        ... }
        >>> validate_totals(datos)  # No levanta excepción
    """
    try:
        # Validar total vs suma de items
        items = data.get("items", [])
        if items:
            items_total = sum(float(item.get("total", 0)) for item in items)
            invoice_total = float(data.get("total", 0))

            # Permitir pequeña diferencia por redondeo (0.01 = 1 centavo)
            if abs(items_total - invoice_total) > 0.01:
                logger.warning(
                    f"Discrepancia en totales: suma de items ({items_total:.2f}) != "
                    f"total del comprobante ({invoice_total:.2f})"
                )
                raise ValidationError(
                    f"El total del comprobante ({invoice_total:.2f}) no coincide con "
                    f"la suma de los items ({items_total:.2f}). "
                    f"Diferencia: {abs(items_total - invoice_total):.2f}"
                )

        # Validar IGV si aplica
        porcentaje_igv = float(data.get("porcentaje_de_igv", 0))
        if porcentaje_igv > 0:
            total_gravada = float(data.get("total_gravada", 0))
            calculated_igv = total_gravada * porcentaje_igv / 100
            actual_igv = float(data.get("total_igv", 0))

            # Permitir pequeña diferencia por redondeo
            if abs(calculated_igv - actual_igv) > 0.01:
                logger.warning(
                    f"Discrepancia en IGV: calculado ({calculated_igv:.2f}) != "
                    f"proporcionado ({actual_igv:.2f})"
                )
                raise ValidationError(
                    f"El IGV calculado ({calculated_igv:.2f}) no coincide con "
                    f"el IGV proporcionado ({actual_igv:.2f}). "
                    f"Diferencia: {abs(calculated_igv - actual_igv):.2f}"
                )

    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Error validando totales: {str(e)}")
        raise ValidationError(f"Error validando totales: {str(e)}")


def validate_dates_format(value: str, expected_format: str = "%d-%m-%Y") -> str:
    """
    Valida que una fecha esté en el formato esperado.

    Args:
        value (str): Valor de fecha como string
        expected_format (str): Formato esperado (por defecto DD-MM-YYYY)

    Returns:
        str: La fecha validada en el formato correcto

    Raises:
        ValidationError: Si la fecha no es válida

    Example:
        >>> date_str = validate_dates_format('15-01-2024', '%d-%m-%Y')
        >>> print(date_str)
        '15-01-2024'
    """
    try:
        datetime.strptime(value, expected_format)
        return value
    except ValueError as e:
        raise ValidationError(
            f"Fecha inválida: {value}. Formato esperado: {expected_format}"
        )


def validate_currency_amount(
    amount: Any, min_value: float = 0, max_value: float = None
) -> Decimal:
    """
    Valida que un monto sea un número válido en el rango especificado.

    Args:
        amount: Valor a validar (int, float, str, Decimal)
        min_value (float): Valor mínimo permitido (por defecto 0)
        max_value (float): Valor máximo permitido (opcional)

    Returns:
        Decimal: Monto validado como Decimal

    Raises:
        ValidationError: Si el monto no es válido

    Example:
        >>> monto = validate_currency_amount('150.50')
        >>> print(type(monto))
        <class 'decimal.Decimal'>
    """
    try:
        decimal_amount = Decimal(str(amount))

        if decimal_amount < Decimal(str(min_value)):
            raise ValidationError(
                f"Monto {decimal_amount} es menor que el mínimo permitido ({min_value})"
            )

        if max_value is not None and decimal_amount > Decimal(str(max_value)):
            raise ValidationError(
                f"Monto {decimal_amount} excede el máximo permitido ({max_value})"
            )

        return decimal_amount

    except (ValueError, TypeError) as e:
        raise ValidationError(f"Monto inválido: {amount}. Debe ser un número.")


def validate_ruc(ruc: str) -> str:
    """
    Valida que un RUC tenga el formato correcto (11 dígitos).

    Args:
        ruc (str): Número de RUC

    Returns:
        str: RUC validado

    Raises:
        ValidationError: Si el RUC no es válido

    Example:
        >>> ruc = validate_ruc('20123456789')
        >>> print(ruc)
        '20123456789'
    """
    ruc_str = str(ruc).strip()

    if not ruc_str.isdigit():
        raise ValidationError(f"RUC debe contener solo dígitos: {ruc}")

    if len(ruc_str) != 11:
        raise ValidationError(
            f"RUC debe tener 11 dígitos, se recibieron {len(ruc_str)}"
        )

    return ruc_str
