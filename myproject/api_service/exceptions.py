# api_service/exceptions.py
"""
Excepciones personalizadas para el módulo api_service.
"""


class APIError(Exception):
    """Excepción base para todos los errores de API"""

    pass


class RateLimitExceededError(APIError):
    """Se excedió el límite de peticiones por minuto"""

    def __init__(self, wait_time, limit):
        self.wait_time = wait_time
        self.limit = limit
        super().__init__(
            f"Rate limit excedido. Esperar {wait_time} segundos. Límite: {limit}/minuto"
        )


class AuthenticationError(APIError):
    """Error de autenticación (token inválido, etc.)"""

    pass


class APINotFoundError(APIError):
    """Recurso no encontrado (ej: RUC no existe)"""

    pass


class APIBadResponseError(APIError):
    """La API devolvió una respuesta inesperada o inválida"""

    pass


class APITimeoutError(APIError):
    """Timeout en la conexión con la API"""

    pass
