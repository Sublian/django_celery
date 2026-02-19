# flow_invoice_pdf_qr/run_all.py
"""
Ejecuta los 3 pasos en secuencia.
"""

import asyncio
import sys
from pathlib import Path

from .step1_send_only import send_to_nubefact_only
from .step2_generate_pdf import generate_pdf_from_response
from .step3_full_flow import full_flow


async def run_all_steps(numero=None):
    """Ejecuta los 3 pasos en orden."""
    
    print("\n" + "🚀" * 20)
    print("🚀 EJECUTANDO LOS 3 PASOS EN SECUENCIA")
    print("🚀" * 20 + "\n")
    
    # Paso 1
    print("\n" + "📌" * 20)
    print("📌 PASO 1: Envío a NubeFact")
    print("📌" * 20)
    result1 = await send_to_nubefact_only(numero)
    
    if not result1["success"]:
        print("\n❌ Paso 1 falló. Deteniendo secuencia.")
        return False
    
    # Paso 2
    print("\n" + "📌" * 20)
    print("📌 PASO 2: Generar PDF desde respuesta")
    print("📌" * 20)
    result2 = generate_pdf_from_response(result1["output_dir"] / result1["filename"])
    
    if not result2 or not result2["success"]:
        print("\n❌ Paso 2 falló.")
        return False
    
    # Paso 3
    print("\n" + "📌" * 20)
    print("📌 PASO 3: Flujo completo integrado")
    print("📌" * 20)
    numero_nuevo = int(numero) + 1
    result3 = await full_flow(numero_nuevo)
    
    return result3["success"]


def main():
    """Punto de entrada."""
    numero = sys.argv[1] if len(sys.argv) > 1 else None
    
    success = asyncio.run(run_all_steps(numero))
    
    if success:
        print("\n✅" * 10)
        print("✅ TODOS LOS PASOS COMPLETADOS EXITOSAMENTE")
        print("✅" * 10)
        sys.exit(0)
    else:
        print("\n❌" * 10)
        print("❌ LA SECUENCIA FALLÓ")
        print("❌" * 10)
        sys.exit(1)


if __name__ == "__main__":
    main()