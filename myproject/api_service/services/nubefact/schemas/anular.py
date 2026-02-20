# schemas/anular.py
from pydantic import BaseModel, Field, validator


class AnularComprobanteSchema(BaseModel):
    """Schema para operación anular_comprobante."""
    
    operacion: str = "anular_comprobante"
    numero: str = Field(..., regex="^[0-9]{1,8}$")
    motivo: str = Field(..., min_length=5, max_length=200)
    
    @validator('numero')
    def validate_numero(cls, v):
        if not v.isdigit():
            raise ValueError("Número debe contener solo dígitos")
        return v