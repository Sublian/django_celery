# test_minimal.py
import httpx
import asyncio
from  datetime import datetime

async def test_minimal():
    url = "https://api.nubefact.com/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer 737745e11f79445d8b3658e66ee0a085de51aefe18554c4ba51532d8f0e57e9b",
        "Accept": "application/json",
    }
    data = {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": "1",
            "serie": "F001",
            "numero": 91516,
            "sunat_transaction": "1",
            "cliente_tipo_de_documento": "6",
            "cliente_numero_de_documento": "20343443961",  # RUC válido
            "cliente_denominacion": "EMPRESA DE PRUEBA S.A.C.",
            "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
            "cliente_email": "contacto@empresaprueba.com",
            "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
            "fecha_de_vencimiento": datetime.now().strftime("%Y-%m-%d"),
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
                    "descripcion": "SERVICIO DE CONSULTORÍA IT - Asesoría técnica",
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
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=data, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

asyncio.run(test_minimal())