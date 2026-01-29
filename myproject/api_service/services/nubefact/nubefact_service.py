# api_service/services/nubefact_service.py
import requests
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional
from django.core.exceptions import ValidationError
from .base_service import BaseAPIService

class NubefactService(BaseAPIService):
    """Servicio para integración con Nubefact API."""
    
    # Mapeo de códigos de error de Nubefact
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
        
        # Timeouts configurados (ajusta según necesites)
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
        bool_fields = ['detraccion', 'enviar_automaticamente_a_la_sunat', 
                      'enviar_automaticamente_al_cliente', 'anticipo_regularizacion']
        for field in bool_fields:
            if field in validated_data:
                if isinstance(validated_data[field], str):
                    validated_data[field] = validated_data[field].lower() == 'true'
        
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
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Procesa la respuesta de Nubefact, manejando errores."""
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"errors": "Respuesta no es JSON válido"}
        
        # Verificar códigos de estado HTTP
        if response.status_code == 200:
            # Éxito, pero verificar si Nubefact reportó error
            if 'codigo' in response_data and response_data['codigo'] in self.ERROR_CODES:
                error_msg = self.ERROR_CODES[response_data['codigo']]
                raise Exception(f"Nubefact Error {response_data['codigo']}: {error_msg}")
            return response_data
        
        elif response.status_code == 400:
            error_detail = response_data.get('errors', 'Solicitud incorrecta')
            raise ValidationError(f"Error de validación: {error_detail}")
        
        elif response.status_code == 401:
            raise Exception("Error de autenticación: Token inválido o expirado")
        
        elif response.status_code == 500:
            raise Exception("Error interno del servidor Nubefact")
        
        else:
            raise Exception(f"Error HTTP {response.status_code}: {response.text}")
    
    def send_request(self, endpoint: str, data: dict, method: str = "POST") -> Dict[str, Any]:
        """
        Envía una solicitud a la API de Nubefact.
        
        Args:
            endpoint: Endpoint de la API (normalmente vacío para Nubefact)
            data: Datos del comprobante en formato JSON
            method: Método HTTP (POST por defecto)
        
        Returns:
            Dict con la respuesta de Nubefact
        
        Raises:
            ValidationError: Si los datos no son válidos
            Exception: Si hay error en la comunicación
        """
        try:
            # Validar y normalizar datos
            validated_data = self._validate_json_structure(data)
            
            # Construir URL completa
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else self.base_url
            
            # Enviar solicitud
            if method.upper() == "POST":
                response = self.session.post(url, json=validated_data)
            else:
                raise ValueError(f"Método no soportado: {method}")
            
            # Procesar respuesta
            return self._handle_response(response)
            
        except requests.exceptions.Timeout:
            raise Exception("Timeout al conectar con Nubefact")
        except requests.exceptions.ConnectionError:
            raise Exception("Error de conexión con Nubefact")
        except ValidationError as ve:
            raise ve
        except Exception as e:
            raise Exception(f"Error en servicio Nubefact: {str(e)}")
    
    def emitir_comprobante(self, datos_comprobante: dict) -> Dict[str, Any]:
        """
        Método específico para emitir comprobantes.
        Simplifica el uso del servicio.
        """
        return self.send_request("", datos_comprobante, "POST")
    
    def consultar_comprobante(self, tipo: int, serie: str, numero: int) -> Dict[str, Any]:
        """Consulta un comprobante existente."""
        data = {
            "operacion": "consultar_comprobante",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero
        }
        return self.send_request("", data, "POST")
    
    def anular_comprobante(self, tipo: int, serie: str, numero: int, motivo: str) -> Dict[str, Any]:
        """Anula un comprobante existente."""
        data = {
            "operacion": "generar_anulacion",
            "tipo_de_comprobante": tipo,
            "serie": serie,
            "numero": numero,
            "motivo": motivo
        }
        return self.send_request("", data, "POST")
    
    def __del__(self):
        """Cierra la sesión al destruir el objeto."""
        if hasattr(self, 'session'):
            self.session.close()
            