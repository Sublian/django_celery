# api_service/services/nubefact_service.py
import time
import json
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError

from .base_service import BaseAPIService
from .exceptions import NubefactAPIError, NubefactValidationError


class NubefactService(BaseAPIService):
    """Servicio para integración con Nubefact API con logging automático."""
    
    ERROR_CODES = {
        10: "Token incorrecto o eliminado",
        11: "Ruta/URL incorrecta o no existe",
        12: "Content-Type incorrecto en cabecera",
        20: "Archivo no cumple con el formato establecido",
        21: "No se pudo completar la operación",
        22: "Documento enviado fuera del plazo permitido",
        23: "Documento ya existe en Nubefact",
        24: "Documento no existe o no fue enviado a Nubefact",
        40: "Error interno desconocido",
        50: "Cuenta suspendida",
        51: "Cuenta suspendida por falta de pago"
    }
    
    def __init__(self):
        super().__init__("NUBEFACT")
        self.session = requests.Session()
        self._configure_session()
    
    def _configure_session(self):
        """Configura la sesión HTTP con headers y timeout."""
        self.session.headers.update({
            "Authorization": self.auth_token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        # Timeouts configurados (ajustar según necesidad)
        self.session.timeout = (30, 60)  # (connect, read)
    
    def _validate_json_structure(self, data: dict) -> dict:
        """
        Valida y normaliza la estructura del JSON para Nubefact.
        Convierte fechas al formato DD-MM-YYYY y maneja valores nulos.
        """
        validated_data = data.copy()
        
        # Campos de fecha: convertir de YYYY-MM-DD a DD-MM-YYYY
        date_fields = ['fecha_de_emision', 'fecha_de_vencimiento']
        for field in date_fields:
            if field in validated_data and validated_data[field]:
                try:
                    if '-' in str(validated_data[field]):
                        date_obj = datetime.strptime(str(validated_data[field]), '%Y-%m-%d')
                        validated_data[field] = date_obj.strftime('%d-%m-%Y')
                except ValueError:
                    raise ValidationError(f"Formato de fecha inválido en {field}: {validated_data[field]}")
        
        # Campos numéricos: convertir strings vacíos a 0
        numeric_fields = [
            'total_igv', 'total', 'descuento_global', 'total_descuento',
            'detraccion_total', 'detraccion_porcentaje'
        ]
        for field in numeric_fields:
            if field in validated_data and validated_data[field] == '':
                validated_data[field] = 0
        
        # Campos booleanos: convertir strings a booleanos
        # bool_fields = ['detraccion', 'enviar_automaticamente_a_la_sunat', 
        #               'enviar_automaticamente_al_cliente', 'anticipo_regularizacion']
        # for field in bool_fields:
        #     if field in validated_data:
        #         if isinstance(validated_data[field], str):
        #             validated_data[field] = validated_data[field].lower() == 'true'
        
        # Validar que los totales sean consistentes
        self._validate_totals(validated_data)
        
        return validated_data
    
    def _validate_totals(self, data: dict):
        """Valida que los totales matemáticos sean correctos."""
        try:
            # Validar total vs suma de items
            items_total = sum(float(item['total']) for item in data.get('items', []))
            invoice_total = float(data.get('total', 0))
            
            # Permitir pequeña diferencia por redondeo
            if abs(items_total - invoice_total) > 0.01:
                raise ValidationError(
                    f"El total del comprobante ({invoice_total}) no coincide con "
                    f"la suma de los items ({items_total})"
                )
            
            # Validar IGV si aplica
            if data.get('porcentaje_de_igv', 0) > 0:
                calculated_igv = float(data.get('total_gravada', 0)) * float(data.get('porcentaje_de_igv', 0)) / 100
                actual_igv = float(data.get('total_igv', 0))
                
                if abs(calculated_igv - actual_igv) > 0.01:
                    raise ValidationError(
                        f"El IGV calculado ({calculated_igv:.2f}) no coincide con "
                        f"el IGV proporcionado ({actual_igv:.2f})"
                    )
                    
        except (ValueError, KeyError) as e:
            raise ValidationError(f"Error validando totales: {str(e)}")
    
    def _handle_response(self, response: requests.Response, endpoint_name: str, 
                        request_data: dict, start_time: float) -> Dict[str, Any]:
        """Procesa la respuesta de Nubefact y registra el log."""
        duration_ms = int((time.time() - start_time) * 1000)
        
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"errors": "Respuesta no es JSON válido", "raw_response": response.text[:500]}
        
        # Determinar estado basado en código HTTP y respuesta Nubefact
        status = "SUCCESS"
        error_message = ""
        
        if response.status_code == 200:
            # Éxito HTTP, pero verificar si Nubefact reportó error
            if 'codigo' in response_data and response_data['codigo'] in self.ERROR_CODES:
                error_msg = self.ERROR_CODES[response_data['codigo']]
                error_message = f"Nubefact Error {response_data['codigo']}: {error_msg}"
                status = "FAILED"
        elif response.status_code == 400:
            error_message = response_data.get('errors', 'Solicitud incorrecta')
            status = "FAILED"
        elif response.status_code == 401:
            error_message = "Error de autenticación: Token inválido o expirado"
            status = "FAILED"
        elif response.status_code >= 500:
            error_message = f"Error interno del servidor Nubefact: {response.status_code}"
            status = "FAILED"
        else:
            error_message = f"Error HTTP {response.status_code}: {response.text[:200]}"
            status = "FAILED"
        
        # Registrar la llamada en la base de datos
        self._log_api_call(
            endpoint_name=endpoint_name,
            request_data=request_data,
            response_data=response_data,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            caller_info=self._get_caller_info()
        )
        
        # Si hubo error, lanzar excepción
        if status == "FAILED":
            if response.status_code == 400:
                raise NubefactValidationError(error_message)
            else:
                raise NubefactAPIError(error_message)
        
        return response_data
    
    def send_request(self, endpoint: str, data: dict, method: str = "POST", 
                    endpoint_name: str = None) -> Dict[str, Any]:
        """
        Envía una solicitud a la API de Nubefact con logging automático.
        
        Args:
            endpoint: Endpoint de la API
            data: Datos del comprobante
            method: Método HTTP
            endpoint_name: Nombre para logging (si no se proporciona, usa el endpoint)
        
        Returns:
            Dict con la respuesta de Nubefact
        """
        if endpoint_name is None:
            endpoint_name = endpoint or "generar_comprobante"
        
        start_time = time.time()
        
        try:
            # Validar y normalizar datos
            validated_data = self._validate_json_structure(data)
            
            # Construir URL
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else self.base_url
            
            # Enviar solicitud
            if method.upper() == "POST":
                response = self.session.post(url, json=validated_data)
            else:
                raise ValueError(f"Método no soportado: {method}")
            
            # Procesar respuesta y registrar log
            return self._handle_response(response, endpoint_name, validated_data, start_time)
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # Registrar error de conexión
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Error de conexión: {str(e)}"
            
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="FAILED",
                error_message=error_msg,
                duration_ms=duration_ms,
                caller_info=self._get_caller_info()
            )
            
            raise NubefactAPIError(error_msg)
            
        except (ValidationError, NubefactValidationError, NubefactAPIError):
            # Estas excepciones ya fueron registradas en _handle_response
            raise
            
        except Exception as e:
            # Registrar error inesperado
            duration_ms = int((time.time() - start_time) * 1000)
            
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="FAILED",
                error_message=str(e),
                duration_ms=duration_ms,
                caller_info=self._get_caller_info()
            )
            
            raise NubefactAPIError(f"Error inesperado en servicio Nubefact: {str(e)}")
    
    def emitir_comprobante(self, datos_comprobante: dict) -> Dict[str, Any]:
        """
        Método específico para emitir comprobantes.
        Simplifica el uso del servicio.
        """
        return self.send_request("", datos_comprobante, "POST", "emitir_comprobante")
    
    def consultar_comprobante(self, tipo: int, serie: str, numero: int) -> Dict[str, Any]:
        """Consulta un comprobante existente."""
        data = {
            "operacion": "consultar_comprobante",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero
        }
        return self.send_request("", data, "POST", "consultar_comprobante")
    
    def anular_comprobante(self, tipo: int, serie: str, numero: int, motivo: str) -> Dict[str, Any]:
        """Anula un comprobante existente."""
        data = {
            "operacion": "generar_anulacion",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero,
            "motivo": motivo
        }
        return self.send_request("", data, "POST", "anular_comprobante")
    
    def __del__(self):
        """Cierra la sesión al destruir el objeto."""
        if hasattr(self, 'session'):
            self.session.close()
            