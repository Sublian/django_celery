# tests/integration/nubefact_flow/base_test.py

import os
import sys
import django
from pathlib import Path

# ✅ Configurar Django ANTES de cualquier importación de modelos
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# Ahora sí, importaciones que dependen de Django
import json
from datetime import datetime
from typing import Dict, Any, Optional

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.services.nubefact.schemas.comprobante import ComprobanteSchema
from api_service.services.base.timeout_config import TimeoutConfig


class NubefactTestBase:
    """
    Clase base para pruebas de integración con NubeFact.
    Proporciona métodos comunes y configuración.
    """
    
    # Directorio base para outputs de prueba
    BASE_OUTPUT_DIR = Path("test_output/integration")
    
    @classmethod
    def setup_output_dir(cls, test_name: str) -> Path:
        """Crea y retorna directorio para outputs de una prueba específica."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = cls.BASE_OUTPUT_DIR / test_name / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    @classmethod
    def create_test_invoice_data(cls, numero: Optional[str] = None) -> Dict[str, Any]:
        """
        Crea datos de prueba para una factura usando el esquema Pydantic.
        """
        if numero is None:
            numero = str(int(datetime.now().timestamp() % 100000))
        
        # Datos según el esquema ComprobanteSchema (todos strings)
        data = {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": "1",
            "serie": "F001",
            "numero": numero,
            "sunat_transaction": "1",
            "cliente_tipo_de_documento": "6",
            "cliente_numero_de_documento": "20343443961",
            "cliente_denominacion": "EMPRESA DE PRUEBA INTEGRACIÓN S.A.C.",
            "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
            "cliente_email": "test@integracion.com",
            "fecha_de_emision": datetime.now().strftime("%d-%m-%Y"),
            "fecha_de_vencimiento": datetime.now().strftime("%d-%m-%Y"),
            "moneda": "1",
            "tipo_de_cambio": "1",
            "porcentaje_de_igv": "18.00",
            "total_gravada": "847.46",
            "total_igv": "152.54",
            "total": "1000.00",
            "enviar_automaticamente_a_la_sunat": "false",
            "enviar_automaticamente_al_cliente": "false",
            "items": [
                {
                    "unidad_de_medida": "ZZ",
                    "codigo": "SERV-001",
                    "descripcion": "SERVICIO DE CONSULTORÍA IT - Prueba integración",
                    "cantidad": "10",
                    "valor_unitario": "84.746",
                    "precio_unitario": "100.00",
                    "subtotal": "847.46",
                    "tipo_de_igv": "1",
                    "igv": "152.54",
                    "total": "1000.00",
                    "codigo_producto_sunat": "81112105",
                }
            ],
        }
        
        # Validar con Pydantic (opcional, pero recomendado)
        try:
            validated = ComprobanteSchema(**data)
            return validated.dict()
        except Exception as e:
            print(f"⚠️ Error validando con Pydantic: {e}")
            return data
    
    @classmethod
    def save_response(cls, response: Dict, filename: str, output_dir: Path) -> Path:
        """Guarda una respuesta en archivo JSON."""
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2, ensure_ascii=False)
        return filepath
    
    @classmethod
    def load_response(cls, filepath: Path) -> Dict:
        """Carga una respuesta desde archivo JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @classmethod
    def get_async_service(cls, timeout_config: Optional[TimeoutConfig] = None) -> NubefactServiceAsync:
        """Obtiene una instancia del servicio asíncrono."""
        return NubefactServiceAsync(timeout_config=timeout_config)
    
    @classmethod
    def get_sync_service(cls, timeout_config: Optional[TimeoutConfig] = None) -> NubefactService:
        """Obtiene una instancia del servicio síncrono."""
        return NubefactService(timeout_config=timeout_config)