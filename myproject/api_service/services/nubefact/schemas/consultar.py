# schemas/consultar.py
from pydantic import BaseModel, Field, validator


class ConsultarComprobanteSchema(BaseModel):
    """Schema para operación consultar_comprobante."""
    
    operacion: str = "consultar_comprobante"
    numero: str = Field(..., regex="^[0-9]{1,8}$")
    
    @validator('numero')
    def validate_numero(cls, v):
        if not v.isdigit():
            raise ValueError("Número debe contener solo dígitos")
        return v


