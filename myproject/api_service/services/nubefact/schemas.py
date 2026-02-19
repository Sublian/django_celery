# nubefact_service/schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import date
from decimal import Decimal


class Item(BaseModel):
    """Modelo para un ítem o línea del comprobante."""

    unidad_de_medida: str = Field(..., min_length=2, max_length=5)  # Ej: "NIU", "ZZ"
    codigo: Optional[str] = Field(None, max_length=250)
    descripcion: str = Field(..., max_length=250)
    cantidad: Decimal = Field(..., gt=0)
    valor_unitario: Decimal  # Sin IGV
    precio_unitario: Decimal  # Con IGV
    descuento: Optional[Decimal] = None
    subtotal: Decimal
    tipo_de_igv: int = Field(..., ge=1, le=20)  # Del 1 al 20 según catálogo
    igv: Decimal
    total: Decimal
    anticipo_regularizacion: bool = False
    anticipo_documento_serie: Optional[str] = Field(None, min_length=4, max_length=4)
    anticipo_documento_numero: Optional[int] = Field(None, ge=1, le=99999999)
    codigo_producto_sunat: Optional[str] = Field(None, max_length=8)


class ComprobanteParaEnvio(BaseModel):
    """Modelo principal para la operación 'generar_comprobante'."""

    operacion: str = "generar_comprobante"
    tipo_de_comprobante: int = Field(..., ge=1, le=4)  # 1:Factura, 2:Boleta, etc.
    serie: str = Field(..., min_length=1, max_length=4)
    numero: int = Field(..., ge=1, le=99999999)
    sunat_transaction: int = Field(..., ge=1)  # 1:Venta Interna, etc.
    cliente_tipo_de_documento: int  # 6:RUC, 1:DNI, etc.
    cliente_numero_de_documento: str = Field(..., max_length=15)
    cliente_denominacion: str = Field(..., max_length=100)
    cliente_direccion: Optional[str] = Field(None, max_length=100)
    cliente_email: Optional[str] = Field(None, max_length=250)
    fecha_de_emision: str  # Formato DD-MM-YYYY
    moneda: int = Field(..., ge=1, le=4)  # 1:Soles, 2:Dólares, etc.
    porcentaje_de_igv: Decimal = Field(default=Decimal("18.00"))
    total_gravada: Decimal
    total_igv: Decimal
    total: Decimal
    enviar_automaticamente_a_la_sunat: bool = True
    enviar_automaticamente_al_cliente: bool = False
    items: List[Item]

    @validator("fecha_de_emision", pre=True)
    def parse_date(cls, v):
        """Valida y convierte fecha al formato DD-MM-YYYY."""
        if isinstance(v, date):
            return v.strftime("%d-%m-%Y")
        return v

    # Puedes agregar más campos opcionales aquí según necesites (descuento_global, guias, etc.)
    # Ejemplo: guias: Optional[List[Dict]] = None

    class Config:
        # Permite usar tipos Decimal de Python
        arbitrary_types_allowed = True
        json_encoders = {
            Decimal: lambda v: float(v)  # Nubefact espera números, no strings
        }


class ComprobanteSchema(BaseModel):
    tipo_de_comprobante: str
    serie: str
    numero: str
    cliente_numero_de_documento: str

    @validator("cliente_numero_de_documento")
    def validate_ruc(cls, v):
        if len(v) != 11:
            raise ValueError("RUC debe tener 11 dígitos")
        # Validar dígito verificador
        return v
