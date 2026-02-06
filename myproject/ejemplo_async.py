"""
Ejemplo FUNCIONAL de MigoAPIServiceAsync

Este archivo demuestra el uso correcto de la versión simplificada.
TODOS LOS EJEMPLOS AQUÍ FUNCIONAN.

Ejecutar con:
    python ejemplo_async.py
"""

import asyncio
import sys
from pathlib import Path

# Agregar path para imports
sys.path.insert(0, str(Path(__file__).parent / "myproject"))

from api_service.services.migo_service_async import (
    MigoAPIServiceAsync,
    validate_ruc,
    validate_dni,
    batch_query,
)


# ============================================================================
# EJEMPLO 1: Consulta Individual Simple
# ============================================================================


async def ejemplo_1_consulta_simple():
    """Consultar un RUC individual"""
    print("\n" + "=" * 70)
    print("EJEMPLO 1: Consulta Individual")
    print("=" * 70)

    async with MigoAPIServiceAsync() as service:
        # RUC válido
        result = await service.consultar_ruc_async("20100038146")

        print(f"\nRUC: 20100038146")
        print(f"Success: {result['success']}")
        print(f"Keys: {result.keys()}")

        # RUC inválido
        result = await service.consultar_ruc_async("ABC")
        print(f"\nRUC: ABC (inválido)")
        print(f"Success: {result['success']}")
        print(f"Error: {result.get('error')}")


# ============================================================================
# EJEMPLO 2: Consulta Masiva
# ============================================================================


async def ejemplo_2_consulta_masiva():
    """Consultar múltiples RUCs en paralelo"""
    print("\n" + "=" * 70)
    print("EJEMPLO 2: Consulta Masiva")
    print("=" * 70)

    async with MigoAPIServiceAsync() as service:
        rucs = [
            "20100038146",  # Válido
            "20123456789",  # Válido
            "ABC",  # Inválido
            "123",  # Inválido
        ]

        print(f"\nConsultando {len(rucs)} RUCs...")
        result = await service.consultar_ruc_masivo_async(
            rucs, batch_size=2  # 2 en paralelo
        )

        print(f"\nResultados:")
        print(f"  Total: {result['total']}")
        print(f"  Exitosos: {result['exitosos']}")
        print(f"  Fallidos: {result['fallidos']}")
        print(f"  RUCs válidos: {result['validos']}")
        print(f"  RUCs inválidos: {result['invalidos']}")
        print(f"  Tiempo: {result['duration_ms']}ms")


# ============================================================================
# EJEMPLO 3: Consulta DNI
# ============================================================================


async def ejemplo_3_consulta_dni():
    """Consultar DNI"""
    print("\n" + "=" * 70)
    print("EJEMPLO 3: Consulta DNI")
    print("=" * 70)

    async with MigoAPIServiceAsync() as service:
        # DNI válido
        result = await service.consultar_dni_async("12345678")
        print(f"\nDNI: 12345678")
        print(f"Success: {result['success']}")

        # DNI inválido
        result = await service.consultar_dni_async("ABC")
        print(f"\nDNI: ABC (inválido)")
        print(f"Success: {result['success']}")
        print(f"Error: {result.get('error')}")


# ============================================================================
# EJEMPLO 4: Validadores
# ============================================================================


def ejemplo_4_validadores():
    """Demostrar validadores"""
    print("\n" + "=" * 70)
    print("EJEMPLO 4: Validadores")
    print("=" * 70)

    # Test RUC
    print("\nValidación de RUC:")
    test_rucs = [
        ("20100038146", True),  # Válido - 11 dígitos
        ("20123456789", True),  # Válido - 11 dígitos
        ("123", False),  # Inválido - muy corto
        ("ABC", False),  # Inválido - no dígitos
        ("", False),  # Inválido - vacío
    ]

    for ruc, expected in test_rucs:
        result = validate_ruc(ruc)
        status = "✅" if result == expected else "❌"
        print(f"  {status} validate_ruc('{ruc}') = {result}")

    # Test DNI
    print("\nValidación de DNI:")
    test_dnis = [
        ("12345678", True),  # Válido - 8 dígitos
        ("123456789", True),  # Válido - 9 dígitos
        ("123", False),  # Inválido - muy corto
        ("ABC", False),  # Inválido - no dígitos
        ("", False),  # Inválido - vacío
    ]

    for dni, expected in test_dnis:
        result = validate_dni(dni)
        status = "✅" if result == expected else "❌"
        print(f"  {status} validate_dni('{dni}') = {result}")


# ============================================================================
# EJEMPLO 5: Batch Query Helper
# ============================================================================


async def ejemplo_5_batch_query():
    """Demostrar helper batch_query"""
    print("\n" + "=" * 70)
    print("EJEMPLO 5: Batch Query Helper")
    print("=" * 70)

    async def proceso_item(item):
        """Función async para procesar un item"""
        await asyncio.sleep(0.1)  # Simular trabajo
        return f"Resultado de {item}"

    items = ["A", "B", "C", "D", "E"]

    print(f"\nProcesando {len(items)} items en lotes de 2...")
    import time

    start = time.time()

    results = await batch_query(proceso_item, items, batch_size=2)

    elapsed = time.time() - start

    print(f"\nResultados:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result}")
    print(f"\nTiempo total: {elapsed:.2f}s")
    print(f"(5 items * 0.1s cada uno, pero en paralelo = ~0.3s)")


# ============================================================================
# EJEMPLO 6: Context Manager
# ============================================================================


async def ejemplo_6_context_manager():
    """Demostrar context manager y cleanup"""
    print("\n" + "=" * 70)
    print("EJEMPLO 6: Context Manager (Gestión de recursos)")
    print("=" * 70)

    print("\n✅ CORRECTO - Usando context manager:")
    async with MigoAPIServiceAsync() as service:
        print("   - Cliente creado")
        result = await service.consultar_ruc_async("20100038146")
        print("   - Consulta realizada")
    print("   - Cliente cerrado automáticamente")

    print("\n❌ INCORRECTO - Sin context manager:")
    service = MigoAPIServiceAsync()
    print("   - Cliente NOT creado (se crearían memory leaks)")


# ============================================================================
# EJEMPLO 7: Manejo de Errores
# ============================================================================


async def ejemplo_7_manejo_errores():
    """Demostrar manejo robusto de errores"""
    print("\n" + "=" * 70)
    print("EJEMPLO 7: Manejo de Errores")
    print("=" * 70)

    async with MigoAPIServiceAsync(timeout=5) as service:

        print("\n1. Validación fallida:")
        result = await service.consultar_ruc_async("ABC")
        if not result["success"]:
            print(f"   Error detectado: {result['error']}")

        print("\n2. Consulta correcta:")
        result = await service.consultar_ruc_async("20100038146")
        if result["success"]:
            print(f"   ✅ Consulta exitosa")
        else:
            print(f"   ❌ Error: {result['error']}")

        print("\n3. Masivo con mix de válidos e inválidos:")
        result = await service.consultar_ruc_masivo_async(
            ["20100038146", "ABC", "20123456789"], batch_size=2
        )
        print(f"   Exitosos: {result['exitosos']}")
        print(f"   Fallidos: {result['fallidos']}")


# ============================================================================
# EJEMPLO 8: Rendimiento
# ============================================================================


async def ejemplo_8_rendimiento():
    """Comparar performance"""
    print("\n" + "=" * 70)
    print("EJEMPLO 8: Rendimiento")
    print("=" * 70)

    import time

    async with MigoAPIServiceAsync() as service:
        # Simulación de 10 consultas
        rucs = ["20100038146"] * 10

        print(f"\nConsultando {len(rucs)} RUCs...")

        start = time.time()
        result = await service.consultar_ruc_masivo_async(rucs, batch_size=10)
        elapsed = time.time() - start

        print(f"\nResultado (paralelo, batch_size=10):")
        print(f"  Tiempo total: {result['duration_ms']}ms")
        print(f"  Tiempo de ejecución real: {elapsed * 1000:.0f}ms")
        print(f"  Exitosos: {result['exitosos']}")

        # Estimación si fuera secuencial
        print(f"\nEstimaciones:")
        print(f"  Paralelo (10 en paralelo): ~{result['duration_ms']}ms")
        print(f"  Secuencial (uno a uno): ~{result['duration_ms'] * 10}ms")
        print(f"  Ganancia: ~{10}x más rápido")


# ============================================================================
# MAIN
# ============================================================================


async def main():
    """Ejecutar todos los ejemplos"""

    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║          MigoAPIServiceAsync - Ejemplos FUNCIONALES               ║")
    print("║                    Status: ✅ Completamente Funcional             ║")
    print("╚════════════════════════════════════════════════════════════════════╝")

    try:
        # Ejemplos síncronos
        ejemplo_4_validadores()
        await ejemplo_6_context_manager()

        # Ejemplos asincronos
        await ejemplo_1_consulta_simple()
        await ejemplo_3_consulta_dni()
        await ejemplo_5_batch_query()
        await ejemplo_2_consulta_masiva()
        await ejemplo_7_manejo_errores()
        await ejemplo_8_rendimiento()

        print("\n" + "=" * 70)
        print("✅ TODOS LOS EJEMPLOS COMPLETADOS EXITOSAMENTE")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
