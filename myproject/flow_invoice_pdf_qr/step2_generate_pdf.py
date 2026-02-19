# flow_invoice_pdf_qr/step2_generate_pdf.py
"""
PASO 2: Generar PDF con QR a partir de una respuesta guardada.
NO envía a NubeFact, usa datos de step1.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django
django.setup()

from .shared import (
    setup_directories,
    load_response_from_file,
    save_api_log  # Para logging opcional
)
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator


def find_latest_response_file(base_dir: Path = Path("test_output/step1")) -> Path:
    """Encuentra el archivo de respuesta más reciente en el directorio step1."""
    if not base_dir.exists():
        raise FileNotFoundError(f"❌ Directorio no encontrado: {base_dir}")
    
    # Buscar todos los archivos response_*.json
    response_files = list(base_dir.rglob("response_*.json"))
    
    if not response_files:
        raise FileNotFoundError(f"❌ No hay archivos response_*.json en {base_dir}")
    
    # Ordenar por fecha de modificación (más reciente primero)
    latest = max(response_files, key=lambda p: p.stat().st_mtime)
    return latest


def extract_invoice_data_from_response(response_data: dict) -> dict:
    """
    Extrae los datos necesarios para el PDF desde la respuesta de NubeFact.
    """
    # Datos básicos de la respuesta
    invoice_data = {
        "serie": response_data.get('serie', 'F001'),
        "numero": str(response_data.get('numero', '00000')),
        "fecha_de_emision": response_data.get('fecha_de_emision', 
                                              datetime.now().strftime("%Y-%m-%d")),
        "fecha_de_vencimiento": response_data.get('fecha_de_vencimiento', ''),
        "moneda": response_data.get('moneda', '1'),
        
        # Datos del cliente (podrían venir en la respuesta o usar defaults)
        "cliente_denominacion": "EMPRESA DE PRUEBA V2 S.A.C.",
        "cliente_numero_de_documento": "20343443961",
        "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
        
        # Totales
        "total_gravada": str(response_data.get('total_gravada', '847.46')),
        "total_igv": str(response_data.get('total_igv', '152.54')),
        "total": str(response_data.get('total', '1000.00')),
        
        # Datos críticos de NubeFact
        "codigo_hash": response_data.get('codigo_hash'),
        "cadena_para_codigo_qr": response_data.get('cadena_para_codigo_qr'),
        "aceptada_por_sunat": response_data.get('aceptada_por_sunat', False),
        "enlace_del_pdf": response_data.get('enlace_del_pdf'),
        
        # Items (simplificado - podrías extraerlos de la respuesta si vienen)
        "items": [
            {
                "unidad_de_medida": "ZZ",
                "codigo": "SERV-001",
                "descripcion": "SERVICIO DE CONSULTORÍA IT - Asesoría técnica",
                "cantidad": "10",
                "precio_unitario": "100.00",
                "subtotal": "847.46",
                "igv": "152.54",
                "total": "1000.00",
            }
        ],
    }
    
    # Intentar extraer items si están en la respuesta
    if 'items' in response_data and response_data['items']:
        invoice_data['items'] = response_data['items']
    
    return invoice_data


def generate_pdf_from_response(
    response_file: Path = None,
    output_dir: Path = None,
    log_to_db: bool = True
) -> dict:
    """
    Genera PDF a partir de un archivo de respuesta.
    
    Args:
        response_file: Ruta al archivo JSON de respuesta (si es None, busca el último)
        output_dir: Directorio de salida (si es None, crea uno nuevo)
        log_to_db: Si debe registrar un log en la BD
    
    Returns:
        Dict con información del PDF generado
    """
    
    print("\n" + "=" * 60)
    print("🧪 PASO 2: GENERAR PDF DESDE RESPUESTA GUARDADA")
    print("=" * 60)
    
    # 1. Determinar archivo de respuesta
    if response_file is None:
        try:
            response_file = find_latest_response_file()
            print(f"\n📂 Usando respuesta más reciente: {response_file}")
        except FileNotFoundError as e:
            print(f"❌ {e}")
            print("   Ejecuta primero: python -m flow_invoice_pdf_qr.step1_send_only")
            return None
    else:
        response_file = Path(response_file)
        if not response_file.exists():
            print(f"❌ Archivo no encontrado: {response_file}")
            return None
    
    # 2. Cargar respuesta
    response_data = load_response_from_file(response_file)
    print(f"\n📄 Respuesta cargada:")
    print(f"   Factura: {response_data.get('serie', 'F001')}-{response_data.get('numero', 'N/A')}")
    print(f"   Hash: {response_data.get('codigo_hash', 'N/A')[:30]}...")
    print(f"   Estado SUNAT: {'✅ ACEPTADA' if response_data.get('aceptada_por_sunat') else '⏳ PENDIENTE'}")
    
    # 3. Extraer datos para el PDF
    invoice_data = extract_invoice_data_from_response(response_data)
    
    # 4. Configurar directorio de salida
    if output_dir is None:
        output_dir = setup_directories(Path("test_output/step2"))
    
    # 5. Generar PDF
    print(f"\n📄 Generando PDF...")
    
    try:
        pdf_generator = InvoicePDFGenerator(invoice_data)
        pdf_content = pdf_generator.generate_sync()
        
        # 6. Guardar PDF
        filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_from_response.pdf"
        filepath = output_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(pdf_content)
        
        print(f"\n✅ PDF GENERADO EXITOSAMENTE")
        print(f"   Ruta: {filepath}")
        print(f"   Tamaño: {len(pdf_content) / 1024:.1f} KB")
        print(f"   QR incluido: {'✅' if invoice_data.get('cadena_para_codigo_qr') else '❌'}")
        print(f"   Hash incluido: {'✅' if invoice_data.get('codigo_hash') else '❌'}")
        
        # 7. Log opcional en BD
        if log_to_db:
            # Podríamos registrar un log indicando que se generó el PDF
            # Esto es opcional, ya que no es una llamada a API
            print(f"\n📝 Registro en BD (opcional)...")
            # Aquí podrías llamar a save_api_log si quisieras
        
        return {
            "success": True,
            "response_file": response_file,
            "invoice_data": invoice_data,
            "pdf_path": filepath,
            "pdf_size": len(pdf_content)
        }
        
    except Exception as e:
        print(f"\n❌ Error generando PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """Punto de entrada."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generar PDF desde respuesta de NubeFact')
    parser.add_argument('--file', type=str, help='Ruta específica al archivo de respuesta')
    parser.add_argument('--numero', type=str, help='Buscar respuesta por número de factura')
    args = parser.parse_args()
    
    # Determinar archivo de respuesta
    response_file = None
    if args.file:
        response_file = Path(args.file)
    elif args.numero:
        # Buscar archivo que contenga el número
        step1_dir = Path("test_output/step1")
        pattern = f"*{args.numero}*.json"
        matches = list(step1_dir.rglob(pattern))
        if matches:
            response_file = matches[0]
            print(f"📂 Encontrado archivo para número {args.numero}: {response_file}")
        else:
            print(f"❌ No se encontró respuesta para el número {args.numero}")
            sys.exit(1)
    
    result = generate_pdf_from_response(response_file)
    
    if result and result["success"]:
        print(f"\n🎯 PASO 2 COMPLETADO")
        print(f"   PDF guardado en: {result['pdf_path']}")
    else:
        print(f"\n❌ PASO 2 FALLÓ")
        sys.exit(1)


if __name__ == "__main__":
    main()