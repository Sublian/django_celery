#!/usr/bin/env python
"""Quick async integration test with new invoice number"""
import os
import sys
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
project_dir = r'C:\Users\lagonzalez\Desktop\django_fx'
sys.path.insert(0, project_dir)
os.chdir(project_dir)
django.setup()

import asyncio
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync

payload = {
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',
    'serie': 'F001',
    'numero': 91500,
    'fecha_de_emision': datetime.now().strftime('%d/%m/%Y'),
    'moneda': '1',
    'porcentaje_igv': 18.0,
    'descuento_global': 0,
    'descuento': 0,
    'anticipos': 0,
    'redondeo': 0,
    'venta_al_credito': True,
    'detraccion': True,
    'guias_relacionadas': [],
    'relacionados': [],
    'items': [
        {
            'unidad_de_medida': 'ZZ',
            'codigo': 'S00137',
            'descripcion': '[S00137] Internet Dedicado',
            'cantidad': 80.0,
            'valor_unitario': 18.0,
            'precio_unitario': 21.24,
            'descuento': 0.0,
            'subtotal': 1440.0,
            'tipo_de_igv': '1',
            'igv': 259.2,
            'impuesto_bolsas': 0,
            'total': 1699.2,
            'anticipo_regularizacion': 'false',
            'anticipo_documento_serie': '',
            'anticipo_documento_numero': '',
            'codigo_producto_sunat': '81112101'
        }
    ],
    'cliente_numero_de_documento': '20343443961',
    'cliente_tipo_de_documento': '6',
    'cliente_denominacion': 'TEST COMPANY',
    'cliente_email': 'test@example.com',
    'cliente_domicilio': 'Av. Test 123',
    'cliente_pais_de_domicilio': 'PE',
    'cliente_ubigeo': '150131',
    'total_descuentos': 0,
    'total_anticipos': 0,
    'total_gravada': 1440.68,
    'total_igv': 259.20,
    'total_exonerada': 0,
    'total_inafecta': 0,
    'total_otros_cargos': 0,
    'total': '1699.20',
    'total_en_letras': 'MIL SEISCIENTOS NOVENTA Y NUEVE CON 20/100',
    'documento_relacionado_tipo': None,
    'documento_relacionado_serie': None,
    'documento_relacionado_numero': None,
    'tipo_de_nota': None,
    'motivo_de_nota': None,
    'envio_personalizado_correo': False,
    'envio_personalizado_usuario': 'test@example.com',
    'envio_personalizado_password': None,
}

async def main():
    print('\n' + '='*60)
    print('ASYNC INTEGRATION TEST - NubefactServiceAsync')
    print('='*60)
    
    async with NubefactServiceAsync() as svc:
        print('[✓] Service initialized')
        print(f'    Base URL: {svc.base_url}')
        print(f'    Token: {svc.auth_token[:25]}...')
        
        try:
            result = await svc.generar_comprobante(payload)
            print(f'[✓] API Call succeeded')
            print(f'    Numero: {result.get("numero")}')
            print(f'    Link: {result.get("enlace")}')
            print(f'    Hash: {result.get("codigo_hash")}')
        except Exception as e:
            print(f'[✗] Error: {e}')

if __name__ == '__main__':
    asyncio.run(main())
