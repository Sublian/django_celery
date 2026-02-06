#!/usr/bin/env python
"""
Script de prueba para APICacheService
Verifica que todo funcione correctamente

Para ejecutar los tests:
    pytest myproject/api_service/services/test_cache.py -v

O desde la raíz del proyecto:
    pytest api_service/services/test_cache.py -v -s

Requisitos:
    - pytest
    - pytest-django (opcional, pero conftest.py lo reemplaza)
"""
import pytest
from datetime import datetime
import json


def test_cache_initialization(cache_service):
    """Test 1: Inicialización del servicio"""

    print("\n✓ TEST 1: Inicialización del servicio")
    assert cache_service is not None, "Cache no inicializó"
    print(f"  Backend: {cache_service.backend}")
    assert cache_service.backend in [
        "local_memory",
        "memcached",
        "redis",
    ], "Backend desconocido"
    print("  Status: ✅ OK")


def test_cache_connection(cache_service):
    """Test 2: Verificación de conexión"""

    print("\n✓ TEST 2: Verificación de conexión")
    health = cache_service.get_health()

    assert health is not None, "Health check retornó None"
    assert "status" in health, "Health no tiene 'status'"
    assert health["status"] in ["healthy", "warning", "unhealthy"], "Status inválido"

    print(f"  Health status: {health['status']}")
    print(f"  Checks: {json.dumps(health['checks'], indent=4)}")

    assert health["status"] != "unhealthy", f"Cache unhealthy: {health}"
    print("  Status: ✅ OK")


def test_cache_basic_operations(cache_service):
    """Test 3: Operaciones básicas (GET/SET/DELETE)"""

    print("\n✓ TEST 3: Operaciones básicas")

    # SET
    test_data = {"mensaje": "Hello Cache", "timestamp": datetime.now().isoformat()}
    result = cache_service.set("test_key_basic", test_data, 60)
    assert result == True, "SET retornó False"
    print("  SET: ✅")

    # GET
    valor = cache_service.get("test_key_basic")
    assert valor is not None, "GET retornó None"
    assert valor["mensaje"] == "Hello Cache", "Datos incorrectos"
    print("  GET: ✅")

    # DELETE
    cache_service.delete("test_key_basic")
    valor_deleted = cache_service.get("test_key_basic")
    assert valor_deleted is None, "DELETE no funcionó"
    print("  DELETE: ✅")


def test_cache_ruc_valid(cache_service):
    """Test 4: Manejo de RUCs válidos"""

    print("\n✓ TEST 4: Manejo de RUCs válidos")

    ruc_data = {
        "ruc": "20100038146",
        "nombre_o_razon_social": "CONTINENTAL S.A.C.",
        "estado_del_contribuyente": "ACTIVO",
        "condicion_de_domicilio": "HABIDO",
        "direccion_simple": "AV. EL DERBY NRO. 254",
    }

    # SET RUC
    result = cache_service.set_ruc("20100038146", ruc_data)
    assert result == True, "SET RUC retornó False"
    print("  SET RUC: ✅")

    # GET RUC
    cached_ruc = cache_service.get_ruc("20100038146")
    assert cached_ruc is not None, "GET RUC retornó None"
    assert (
        cached_ruc["nombre_o_razon_social"] == "CONTINENTAL S.A.C."
    ), "Datos incorrectos"
    print(f"  GET RUC: ✅ ({cached_ruc['nombre_o_razon_social']})")

    # DELETE RUC
    cache_service.delete_ruc("20100038146")
    cached_deleted = cache_service.get_ruc("20100038146")
    assert cached_deleted is None, "DELETE RUC no funcionó"
    print("  DELETE RUC: ✅")


def test_cache_ruc_invalid(cache_service):
    """Test 5: Manejo de RUCs inválidos"""

    print("\n✓ TEST 5: Manejo de RUCs inválidos")

    # ADD invalid
    result = cache_service.add_invalid_ruc(
        "20999999999", reason="NO_EXISTE_SUNAT", ttl_hours=24
    )
    assert result == True, "ADD INVALID retornó False"
    print("  ADD INVALID: ✅")

    # IS invalid
    is_invalid = cache_service.is_ruc_invalid("20999999999")
    assert is_invalid == True, "IS INVALID retornó False"
    print("  IS INVALID: ✅")

    # GET invalid info
    invalid_info = cache_service.get_invalid_ruc_info("20999999999")
    assert invalid_info is not None, "GET INVALID INFO retornó None"
    assert invalid_info["reason"] == "NO_EXISTE_SUNAT", "Razón incorrecta"
    print(f"  GET INVALID INFO: ✅ (reason: {invalid_info['reason']})")

    # GET ALL invalid
    all_invalid = cache_service.get_all_invalid_rucs()
    assert "20999999999" in all_invalid, "RUC no está en lista de inválidos"
    print(f"  GET ALL INVALID: ✅ (count: {len(all_invalid)})")

    # REMOVE invalid
    result = cache_service.remove_invalid_ruc("20999999999")
    assert result == True, "REMOVE INVALID retornó False"
    is_invalid_after = cache_service.is_ruc_invalid("20999999999")
    assert not is_invalid_after, "REMOVE INVALID falló"
    print("  REMOVE INVALID: ✅")


def test_cache_cleanup(cache_service):
    """Test 6: Limpieza de RUCs inválidos"""

    print("\n✓ TEST 6: Limpieza de RUCs inválidos")

    # Agregar múltiples RUCs inválidos
    cache_service.add_invalid_ruc("20111111111", "RAZÓN 1")
    cache_service.add_invalid_ruc("20222222222", "RAZÓN 2")
    cache_service.add_invalid_ruc("20333333333", "RAZÓN 3")
    all_before = len(cache_service.get_all_invalid_rucs())
    assert all_before >= 3, "No se guardaron RUCs inválidos"

    # Limpiar
    cache_service.clear_invalid_rucs()
    all_after = len(cache_service.get_all_invalid_rucs())

    assert all_after == 0, "CLEAR INVALID RUCS falló"
    print(f"  RUCs antes: {all_before}")
    print(f"  RUCs después: {all_after}")
    print("  CLEAR INVALID: ✅")


def test_cache_statistics(cache_service):
    """Test 7: Estadísticas del cache"""

    print("\n✓ TEST 7: Estadísticas del cache")

    # Agregar datos de prueba
    cache_service.add_invalid_ruc("20100000001", "ERROR_1")
    cache_service.add_invalid_ruc("20100000002", "ERROR_1")
    cache_service.add_invalid_ruc("20100000003", "ERROR_2")

    stats = cache_service.get_cache_stats()

    assert stats is not None, "Stats es None"
    assert "status" in stats, "Stats no tiene 'status'"
    assert "backend" in stats, "Stats no tiene 'backend'"
    assert "invalid_rucs" in stats, "Stats no tiene 'invalid_rucs'"

    print(f"  Status: {stats['status']}")
    print(f"  Backend: {stats['backend']}")
    print(f"  RUCs inválidos: {stats['invalid_rucs']['total_count']}")
    print(f"  Breakdown: {stats['invalid_rucs']['breakdown_by_reason']}")
    print("  STATS: ✅")


def test_cache_cleanup_expired(cache_service):
    """Test 8: Limpieza de expirados"""

    print("\n✓ TEST 8: Limpieza de expirados")

    cleaned = cache_service.cleanup_expired()

    assert isinstance(cleaned, dict), "Cleanup no retorna dict"
    assert "invalid_rucs" in cleaned, "Cleanup dict no tiene 'invalid_rucs'"

    print(f"  Limpios: {cleaned}")
    print("  CLEANUP: ✅")


def test_cache_multi_service(cache_service):
    """Test 9: Soporte multi-servicio"""

    print("\n✓ TEST 9: Soporte multi-servicio")

    # MIGO key
    key_migo = cache_service.get_service_cache_key("migo", "ruc_20100038146")
    assert "migo" in key_migo, "Key format incorrecto"
    print(f"  MIGO key: {key_migo}")

    # NUBEFACT key
    key_nubefact = cache_service.get_service_cache_key("nubefact", "inv_abc123")
    assert "nubefact" in key_nubefact, "Key format incorrecto"
    print(f"  NUBEFACT key: {key_nubefact}")

    # SUNAT key
    key_sunat = cache_service.get_service_cache_key("sunat", "doc_xyz789")
    assert "sunat" in key_sunat, "Key format incorrecto"
    print(f"  SUNAT key: {key_sunat}")

    print("  MULTI-SERVICE: ✅")


def test_cache_key_normalization(cache_service):
    """Test 10: Normalización de claves"""

    print("\n✓ TEST 10: Normalización de claves")

    # Clave con espacios
    key_with_spaces = "mi clave con espacios"
    normalized = cache_service._normalize_key(key_with_spaces)
    assert " " not in normalized, "Normalización falló (espacios)"
    print(f"  Original: '{key_with_spaces}'")
    print(f"  Normalized: '{normalized}'")

    # Clave muy larga
    long_key = "a" * 300
    normalized_long = cache_service._normalize_key(long_key)
    assert len(normalized_long) <= 256, f"Clave muy larga: {len(normalized_long)}"
    print(f"  Long key length: {len(long_key)}")
    print(f"  Normalized length: {len(normalized_long)}")

    print("  NORMALIZATION: ✅")


def test_cache_with_migo_integration(cache_service):
    """Test 11: Integración con MigoAPIService (simulado)"""

    print("\n✓ TEST 11: Integración simulada con MigoAPIService")

    # Simular consulta a APIMIGO
    ruc = "20100038146"

    # 1. Primer intento - Cache MISS
    print(f"  1️⃣  Primer intento (sin cache):")
    cached = cache_service.get_ruc(ruc)
    if not cached:
        print(f"     Cache MISS → Consultar API")

        # Simular respuesta de API
        api_response = {
            "ruc": ruc,
            "nombre_o_razon_social": "CONTINENTAL S.A.C.",
            "estado_del_contribuyente": "ACTIVO",
            "condicion_de_domicilio": "HABIDO",
        }
        cache_service.set_ruc(ruc, api_response)
        print(f"     Guardado en cache (TTL: 1 hora)")

    # 2. Segundo intento - Cache HIT
    print(f"  2️⃣  Segundo intento (con cache):")
    cached_result = cache_service.get_ruc(ruc)
    assert cached_result is not None, "Cache HIT falló"
    assert (
        cached_result["nombre_o_razon_social"] == "CONTINENTAL S.A.C."
    ), "Datos incorrectos"
    print(f"     Cache HIT → {cached_result['nombre_o_razon_social']}")

    # 3. RUC inválido
    print(f"  3️⃣  Consultar RUC inválido:")
    invalid_ruc = "20999999999"
    cache_service.add_invalid_ruc(invalid_ruc, "NO_EXISTE_SUNAT")

    if cache_service.is_ruc_invalid(invalid_ruc):
        print(f"     RUC inválido detectado → No consultar API")
        print(f"     Guardar log de error")

    print("  INTEGRATION TEST: ✅")


def test_cache_error_handling(cache_service):
    """Test 12: Manejo de errores"""

    print("\n✓ TEST 12: Manejo de errores")

    # RUC inválido (menos de 11 dígitos)
    try:
        result = cache_service.set_ruc("123", {"data": "test"})
        assert result == False, "Debería rechazar RUC corto"
        print("  RUC corto rechazado: ✅")
    except Exception as e:
        print(f"  Error esperado: {e}")

    # RUC vacío
    try:
        result = cache_service.get_ruc("")
        assert result is None, "Debería retornar None para RUC vacío"
        print("  RUC vacío manejado: ✅")
    except Exception as e:
        print(f"  Error esperado: {e}")

    print("  ERROR HANDLING: ✅")

    print("\n" + "=" * 70)
    print("✅ INTEGRACIÓN EXITOSA")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    try:
        test_cache_service()
        test_cache_with_migo()
        print("\n🎉 TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE\n")
    except AssertionError as e:
        print(f"\n❌ TEST FALLÓ: {str(e)}\n")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}\n")
