# nubefact_service/operations.py
from .client import NubefactClient
from .schemas import ComprobanteParaEnvio


def emitir_comprobante(datos_comprobante: dict) -> dict:
    """
    Función principal para emitir un comprobante electrónico.
    Valida los datos y los envía a Nubefact.

    Args:
        datos_comprobante (dict): Diccionario con los datos del comprobante.

    Returns:
        dict: Respuesta completa de Nubefact.

    Raises:
        NubefactValidationError: Si los datos no son válidos.
        NubefactAPIError: Si hay un error en la comunicación con la API.
    """
    # 1. Validar y limpiar los datos de entrada
    comprobante = ComprobanteParaEnvio(**datos_comprobante)

    # 2. Convertir el modelo a diccionario para enviar
    payload = comprobante.dict(exclude_none=True)  # Excluye campos con valor `None`

    # 3. Enviar a Nubefact usando el cliente
    client = NubefactClient()
    # Nubefact no usa un endpoint específico, se envía a la URL base
    respuesta = client.post("", payload)

    # 4. Retornar la respuesta procesada (aquí puedes añadir lógica extra, como guardar en BD)
    return respuesta
