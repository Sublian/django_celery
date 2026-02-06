# test_cache_diagnostico.py
import os
import sys
import django
import logging

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.core.cache import cache
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_memcached_basico():
    """Test básico de funcionalidad de Memcached"""
    print("\n" + "=" * 60)
    print("🧪 TEST DIAGNÓSTICO MEMCACHED")
    print("=" * 60)

    # 1. Test de conexión básica
    print("\n1. 🔌 Test de conexión a Memcached...")
    try:
        cache.set("test_connection", "ok", 10)
        result = cache.get("test_connection")
        if result == "ok":
            print("   ✅ Conexión exitosa a Memcached")
        else:
            print(f"   ❌ Resultado inesperado: {result}")
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")

    # 2. Test de almacenamiento y recuperación
    print("\n2. 💾 Test de almacenamiento/recuperación...")
    test_data = {
        "ruc": "20100038146",
        "razon_social": "CONTINENTAL S.A.C.",
        "timestamp": datetime.now().isoformat(),
        "valido": True,
    }

    cache.set("test_ruc_data", test_data, 30)
    retrieved = cache.get("test_ruc_data")

    if retrieved and retrieved["ruc"] == test_data["ruc"]:
        print(f"   ✅ Datos recuperados correctamente: {retrieved['ruc']}")
    else:
        print(
            f"   ❌ Error recuperando datos. Esperado: {test_data}, Obtenido: {retrieved}"
        )

    # 3. Test de expiración
    print("\n3. ⏱️  Test de expiración...")
    cache.set("test_expire", "deberia_expirar", 2)  # 2 segundos
    import time

    time.sleep(3)
    expired = cache.get("test_expire")
    if expired is None:
        print("   ✅ Expiración funciona correctamente")
    else:
        print(f"   ❌ No expiró: {expired}")

    # 4. Test de incremento/decremento (útil para rate limiting)
    print("\n4. 🔢 Test de operaciones atómicas...")
    cache.set("test_counter", 0, 60)
    cache.incr("test_counter", 1)
    counter = cache.get("test_counter")
    if counter == 1:
        print("   ✅ Incremento atómico funciona")
    else:
        print(f"   ❌ Incremento falló: {counter}")

    # 5. Test de cache de RUCs inválidos
    print("\n5. 🚫 Test de cache de RUCs inválidos...")
    from api_service.services.cache_service import APICacheService

    cache_service = APICacheService()

    # Limpiar primero
    cache.delete("invalid_rucs")

    # Agregar RUC inválido
    ruc_invalido = "99900011122"
    razon = "RUC de prueba inválido"
    resultado = cache_service.marcar_ruc_invalido(ruc_invalido, razon)

    if resultado:
        print(f"   ✅ RUC {ruc_invalido} marcado como inválido")
    else:
        print(f"   ❌ No se pudo marcar RUC {ruc_invalido} como inválido")

    # Verificar si está en cache
    invalidos = cache_service.obtener_rucs_invalidos()
    if ruc_invalido in invalidos:
        print(f"   ✅ RUC {ruc_invalido} encontrado en cache de inválidos")
        print(f"      Razón: {invalidos[ruc_invalido]}")
    else:
        print(f"   ❌ RUC {ruc_invalido} NO encontrado en cache")
        print(f"      Cache actual: {invalidos}")

    # 6. Test de limpieza
    print("\n6. 🧹 Test de limpieza de cache...")
    cache_service.limpiar_cache_invalidos()
    invalidos_despues = cache_service.obtener_rucs_invalidos()
    if not invalidos_despues:
        print("   ✅ Cache de inválidos limpiado correctamente")
    else:
        print(f"   ❌ Cache no se limpió: {invalidos_despues}")

    print("\n" + "=" * 60)
    print("📊 RESUMEN DIAGNÓSTICO MEMCACHED")
    print("=" * 60)


if __name__ == "__main__":
    test_memcached_basico()
