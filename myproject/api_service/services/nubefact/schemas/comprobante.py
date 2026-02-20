# api_service/services/nubefact/schemas/comprobante.py

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date
from decimal import Decimal


class ItemSchema(BaseModel):
    """Modelo para un ítem o línea del comprobante."""
    
    # ✅ CORREGIDO: regex -> pattern
    unidad_de_medida: str = Field(..., min_length=2, max_length=5, pattern="^[A-Z0-9]+$")
    codigo: Optional[str] = Field(None, max_length=250)
    descripcion: str = Field(..., max_length=250)
    cantidad: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    valor_unitario: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    precio_unitario: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    descuento: Optional[str] = Field(None, pattern="^[0-9]+(\\.[0-9]+)?$")
    subtotal: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    tipo_de_igv: str = Field(..., pattern="^[0-9]{1,2}$")
    igv: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    total: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    anticipo_regularizacion: bool = False
    anticipo_documento_serie: Optional[str] = Field(None, min_length=4, max_length=4)
    anticipo_documento_numero: Optional[str] = Field(None, pattern="^[0-9]{1,8}$")
    codigo_producto_sunat: Optional[str] = Field(None, max_length=8)
    
    @validator('cantidad', 'valor_unitario', 'precio_unitario', 'subtotal', 'igv', 'total')
    def validate_numeric_string(cls, v):
        """Asegura que los valores numéricos sean strings válidos."""
        if v is None:
            return v
        try:
            float(v)
            return v
        except ValueError:
            raise ValueError(f"Debe ser un número válido como string: {v}")


class ComprobanteSchema(BaseModel):
    """Modelo principal unificado para comprobante NubeFact."""
    
    # Operación
    operacion: str = "generar_comprobante"
    
    # Identificación
    tipo_de_comprobante: str = Field(..., pattern="^[0-9]{1,2}$")
    serie: str = Field(..., min_length=1, max_length=4, pattern="^[A-Z0-9]+$")
    numero: str = Field(..., pattern="^[0-9]{1,8}$")
    
    # Transacción SUNAT
    sunat_transaction: str = Field(..., pattern="^[0-9]+$")
    
    # Cliente
    cliente_tipo_de_documento: str = Field(..., pattern="^[0-9]+$")
    cliente_numero_de_documento: str = Field(..., max_length=15)
    cliente_denominacion: str = Field(..., max_length=100)
    cliente_direccion: Optional[str] = Field(None, max_length=100)
    cliente_email: Optional[str] = Field(None, max_length=250)
    
    # Fechas
    fecha_de_emision: str
    fecha_de_vencimiento: Optional[str] = None
    
    # Moneda y montos
    moneda: str = Field(..., pattern="^[0-9]$")
    tipo_de_cambio: Optional[str] = Field(None, pattern="^[0-9]+(\\.[0-9]+)?$")
    porcentaje_de_igv: str = Field("18.00", pattern="^[0-9]+(\\.[0-9]+)?$")
    
    # Totales
    total_gravada: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    total_inafecta: Optional[str] = Field("0.00", pattern="^[0-9]+(\\.[0-9]+)?$")
    total_exonerada: Optional[str] = Field("0.00", pattern="^[0-9]+(\\.[0-9]+)?$")
    total_igv: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    total: str = Field(..., pattern="^[0-9]+(\\.[0-9]+)?$")
    
    # Opciones de envío
    enviar_automaticamente_a_la_sunat: bool = True
    enviar_automaticamente_al_cliente: bool = False
    
    # Items
    items: List[ItemSchema]
    
    # Campos opcionales adicionales
    observaciones: Optional[str] = None
    condiciones_de_pago: Optional[str] = None
    medio_de_pago: Optional[str] = None
    placa_vehiculo: Optional[str] = None
    
    @validator("fecha_de_emision", "fecha_de_vencimiento", pre=True)
    def validate_date_format(cls, v):
        """Valida y convierte fecha al formato DD-MM-YYYY."""
        if v is None:
            return v
        
        from datetime import datetime
        
        if isinstance(v, date):
            return v.strftime("%d-%m-%Y")
        
        if isinstance(v, str):
            # Si ya está en DD-MM-YYYY, validar
            try:
                datetime.strptime(v, "%d-%m-%Y")
                return v
            except ValueError:
                pass
            
            # Si está en YYYY-MM-DD, convertir
            try:
                date_obj = datetime.strptime(v, "%Y-%m-%d")
                return date_obj.strftime("%d-%m-%Y")
            except ValueError:
                raise ValueError(f"Formato de fecha inválido: {v}. Use DD-MM-YYYY o YYYY-MM-DD")
        
        raise ValueError(f"Tipo de fecha inválido: {type(v)}")
    
    @validator("cliente_numero_de_documento")
    def validate_ruc(cls, v):
        """Validación básica de RUC."""
        v = str(v).strip()
        if not v.isdigit():
            raise ValueError("RUC debe contener solo dígitos")
        if len(v) != 11:
            raise ValueError(f"RUC debe tener 11 dígitos, se recibieron {len(v)}")
        return v
    
    class Config:
        json_encoders = {
            Decimal: lambda v: str(v)
        }