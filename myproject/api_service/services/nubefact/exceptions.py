# nubefact_service/exceptions.py
class NubefactAPIError(Exception):
    """Excepción base para errores de la API de Nubefact."""

    pass


class NubefactAuthenticationError(NubefactAPIError):
    """Error de autenticación (token o ruta inválidos)."""

    pass


class NubefactValidationError(NubefactAPIError):
    """Error de validación en los datos enviados."""

    pass
