# api_service/services/base/token_utils.py
"""
Utilidades para manejo de tokens de autenticación.
Funciona para cualquier servicio que use Bearer tokens.
"""

import logging

logger = logging.getLogger(__name__)


def validate_and_format_token(token: str, service_name: str = "servicio") -> str:
    """
    Valida y formatea un token con prefijo 'Bearer'.
    
    Args:
        token: Token crudo desde BD
        service_name: Nombre del servicio (para mensajes de error)
        
    Returns:
        Token formateado con prefijo 'Bearer '
        
    Raises:
        ValueError: Si el token está vacío
        
    Example:
        >>> token = validate_and_format_token("abc123", "NubeFact")
        >>> print(token)
        'Bearer abc123'
    """
    if not token:
        raise ValueError(f"Token de autenticación no configurado para {service_name}")
    
    # Limpiar caracteres no deseados
    token = str(token).strip().replace('\n', '').replace('\r', '')
    
    if not token.startswith("Bearer "):
        token = f"Bearer {token}"
    
    return token


def sanitize_token(token: str) -> str:
    """
    Limpia un token eliminando espacios, saltos de línea y caracteres invisibles.
    
    Args:
        token: Token crudo desde BD
    
    Returns:
        Token limpio
        
    Example:
        >>> token = sanitize_token("  abc123\\n")
        >>> print(token)
        'abc123'
    """
    if not token:
        return ""
    return str(token).strip().replace('\n', '').replace('\r', '')