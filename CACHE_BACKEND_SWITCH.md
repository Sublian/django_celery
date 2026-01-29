# 🔄 Guía: Cambiar Backend de Cache

Esta guía te muestra cómo cambiar de **LocMemCache (desarrollo)** a **Memcached/Redis (producción)**.

## 📋 Tabla de Decisión

| Ambiente | Backend | Cuando usar |
|----------|---------|------------|
| 🖥️ Desarrollo Local | **LocMemCache** | Desarrollo, testing local |
| 🧪 Testing/Staging | **Memcached** o **Redis** | Pre-producción, testing distribuido |
| 🚀 Producción | **Memcached** o **Redis** | Servidores en vivo |

---

## ✅ Estado Actual

```bash
Backend: LocMemCache ✅
Ubicación: myproject/myproject/settings.py (líneas 223-228)
Status: Funcionando correctamente
```

---

## 🔄 Cambiar a Memcached (Recomendado para Producción)

### Paso 1: Instalar Memcached

**Linux/Ubuntu:**
```bash
sudo apt-get update
sudo apt-get install memcached libmemcached-tools
sudo systemctl start memcached
sudo systemctl enable memcached  # Iniciar automáticamente
```

**MacOS:**
```bash
brew install memcached
brew services start memcached
```

**Windows (en WSL):**
```bash
sudo apt-get install memcached
memcached -p 11211 &  # Ejecutar en background
```

### Paso 2: Instalar dependencia Python

```bash
pip install pymemcache>=4.0.0
```

### Paso 3: Actualizar settings.py

Reemplaza la sección CACHES en `myproject/myproject/settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',  # O IP del servidor Memcached
        'TIMEOUT': 3600,  # 1 hora
        'OPTIONS': {
            'no_delay': True,           # Desabilita algoritmo de Nagle
            'ignore_exc': True,         # Ignora excepciones (fallback sin cache)
            'max_pool_size': 4,         # Número de conexiones simultáneas
            'use_pooling': True,        # Usa pool de conexiones
        }
    }
}
```

### Paso 4: Verificar Memcached está corriendo

```bash
# Desde WSL/Linux
echo "stats" | nc localhost 11211

# O desde Python
python manage.py shell
>>> from api_service.services.cache_service import APICacheService
>>> cache = APICacheService()
>>> health = cache.get_health()
>>> print(health['status'])  # Debería ser 'healthy'
```

---

## 🔄 Cambiar a Redis (Alternativa Avanzada)

### Paso 1: Instalar Redis

**Linux/Ubuntu:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**MacOS:**
```bash
brew install redis
brew services start redis
```

**Windows (en WSL):**
```bash
sudo apt-get install redis-server
redis-server &  # Ejecutar en background
```

### Paso 2: Instalar dependencia Python

```bash
pip install redis>=4.0.0
```

### Paso 3: Actualizar settings.py

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',  # DB 1 para cache
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 3600,
    }
}
```

### Paso 4: Verificar Redis está corriendo

```bash
# Desde WSL/Linux
redis-cli ping  # Debería responder: PONG

# O desde Python
python manage.py shell
>>> from api_service.services.cache_service import APICacheService
>>> cache = APICacheService()
>>> health = cache.get_health()
>>> print(health['status'])  # Debería ser 'healthy'
```

---

## 🔙 Volver a LocMemCache (Desarrollo)

Si necesitas volver al desarrollo:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 3600,
    }
}
```

---

## ✅ Verificación Post-Cambio

Después de cambiar el backend, ejecuta estos tests:

```bash
cd myproject
python manage.py shell
```

```python
from api_service.services.cache_service import APICacheService

# Test 1: Inicialización
cache = APICacheService()
print(f"✅ Backend: {cache.backend}")

# Test 2: Health Check
health = cache.get_health()
print(f"✅ Health: {health['status']}")

# Test 3: SET/GET
cache.set('test_key', {'data': 'value'}, 60)
result = cache.get('test_key')
print(f"✅ Cache works: {result == {'data': 'value'}}")

# Test 4: RUC operations
cache.set_ruc('20100038146', {'ruc': '20100038146'})
cache.add_invalid_ruc('20999999999', 'TEST')
print(f"✅ RUC cache works: {cache.is_ruc_invalid('20999999999')}")

# Si todo muestra ✅, estás listo
```

---

## 📊 Comparativa de Configuración

| Parámetro | LocMemCache | Memcached | Redis |
|-----------|------------|-----------|-------|
| BACKEND | locmem.LocMemCache | memcached.PyMemcacheCache | redis.RedisCache |
| LOCATION | 'unique-snowflake' | '127.0.0.1:11211' | 'redis://127.0.0.1:6379/1' |
| TIMEOUT | 3600 | 3600 | 3600 |
| OPTIONS | {} | Muchas opciones | Opciones cliente |
| Persistencia | ❌ No | ❌ No | ✅ Sí (opcional) |
| Multi-proceso | ❌ No | ✅ Sí | ✅ Sí |
| Producción | ❌ No | ✅ Sí | ✅ Sí |

---

## 🚨 Troubleshooting

### "Connection refused" con Memcached

```bash
# Verifica que Memcached está corriendo
ps aux | grep memcached

# Si no aparece, inicia Memcached
memcached -p 11211 &

# Verifica puerto
netstat -tuln | grep 11211
```

### "Backend LocMemCache no es válido"

Asegúrate que la ruta al backend está correcta:
```python
'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'  # ✅ Correcto
# NO hagas esto:
'BACKEND': 'django.core.cache.backends.local_memory.LocalMemoryCache'  # ❌ Incorrecto
```

### "Health check fails"

```python
# Ejecuta en Django shell
from api_service.services.cache_service import APICacheService
cache = APICacheService()
health = cache.get_health()
print(health)

# Revisa el detalle del error en health['checks']
```

---

## 📝 Ejemplo Completo: settings.py

```python
# Configuración actual (desarrollo)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 3600,
    }
}

# Comentado: Producción con Memcached
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
#         'LOCATION': 'servidor-prod:11211',
#         'TIMEOUT': 3600,
#         'OPTIONS': {
#             'no_delay': True,
#             'ignore_exc': True,
#             'max_pool_size': 10,
#             'use_pooling': True,
#         }
#     }
# }
```

---

## 🎯 Mejores Prácticas

1. **Desarrollo:** Usa LocMemCache
2. **Staging/Testing:** Usa Memcached o Redis (igual que producción)
3. **Producción:** Usa Memcached o Redis según necesidad
4. **Monitoreo:** Usa `cache.get_health()` regularmente
5. **Limpieza:** No necesaria, TTL automático

---

## 📚 Referencias

- [Django Cache Framework](https://docs.djangoproject.com/en/stable/topics/cache/)
- [Memcached Official](https://memcached.org/)
- [Redis Official](https://redis.io/)
- [APICacheService Documentation](myproject/api_service/services/CACHE_README.md)

---

**Última actualización:** 28 Enero 2026  
**Estado:** ✅ LISTO PARA PRODUCCIÓN
