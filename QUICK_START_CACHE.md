# Instrucciones Rápidas - APICacheService

## ⚡ Quick Start

### 1. Verificar que Memcached está corriendo

```bash
# Verificar si Memcached está activo
echo stats | nc localhost 11211

# Si devuelve info, está corriendo ✅
# Si no responde, iniciar:
memcached -p 11211
```

### 2. Probar desde Django Shell

```bash
python manage.py shell
```

```python
from api_service.services.cache_service import APICacheService

# Inicializar
cache = APICacheService()

# Verificar salud
health = cache.get_health()
print(f"Estado: {health['status']}")  # → healthy, warning, unhealthy

# Obtener estadísticas
stats = cache.get_cache_stats()
print(f"RUCs inválidos: {stats['invalid_rucs']['total_count']}")

# Guardar RUC
cache.set_ruc('20100038146', {
    'nombre_o_razon_social': 'CONTINENTAL S.A.C.',
    'estado_del_contribuyente': 'ACTIVO'
})

# Recuperar RUC
ruc = cache.get_ruc('20100038146')
print(ruc)

# Marcar como inválido
cache.add_invalid_ruc('20999999999', 'NO_EXISTE_SUNAT')

# Verificar si es inválido
if cache.is_ruc_invalid('20999999999'):
    print("RUC inválido")
```

### 3. Ejecutar Tests

```bash
python manage.py shell < myproject/api_service/services/test_cache.py

# O directamente
python myproject/api_service/services/test_cache.py
```

## 🔧 Operaciones Comunes

### Guardar datos

```python
cache.set('mi_clave', {'datos': 'algo'}, ttl=3600)  # 1 hora
cache.set_ruc('20100038146', ruc_data)               # RUC válido (1h)
cache.add_invalid_ruc('20999999999', 'RAZÓN')       # RUC inválido (24h)
```

### Recuperar datos

```python
valor = cache.get('mi_clave')
ruc = cache.get_ruc('20100038146')
if cache.is_ruc_invalid('20999999999'):
    print("Está marcado como inválido")
```

### Eliminar datos

```python
cache.delete('mi_clave')
cache.delete_ruc('20100038146')
cache.remove_invalid_ruc('20999999999')
cache.clear_invalid_rucs()
cache.clear()  # ¡Cuidado! Limpia TODO
```

### Monitoreo

```python
health = cache.get_health()
stats = cache.get_cache_stats()
cleaned = cache.cleanup_expired()
```

## 📊 Ejemplos de Salida

### Health Check

```python
{
  'timestamp': '2026-01-28T15:30:45.123456',
  'status': 'healthy',  # healthy | warning | unhealthy
  'checks': {
    'connection': '✅ OK',
    'basic_operations': '✅ OK',
    'invalid_rucs': '✅ 5 RUCs'
  }
}
```

### Estadísticas

```python
{
  'timestamp': '2026-01-28T15:30:45.123456',
  'status': 'healthy',
  'backend': 'memcached',
  'invalid_rucs': {
    'total_count': 5,
    'sample': ['20100000001', '20100000002', ...],
    'breakdown_by_reason': {
      'NO_EXISTE_SUNAT': 3,
      'FORMATO_INVALIDO': 2
    }
  },
  'timeouts': {
    'default': '15min',
    'ruc_valid': '1h',
    'ruc_invalid': '24h',
    'rate_limit': '1min'
  }
}
```

## ⚙️ Configuración

### settings.py (Ya configurado ✅)

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': '127.0.0.1:11211',
        'TIMEOUT': 3600,
        'OPTIONS': {
            'no_delay': True,
            'ignore_exc': True,
            'max_pool_size': 4,
            'use_pooling': True,
        }
    }
}
```

## 🐛 Debugging

### Si cache no responde

```bash
# 1. Verificar Memcached
echo stats | nc localhost 11211

# 2. Comprobar puerto
netstat -tlnp | grep 11211

# 3. Reiniciar Memcached
pkill memcached
memcached -p 11211
```

### Ver logs

```python
import logging
logging.getLogger('api_service.services.cache_service').setLevel(logging.DEBUG)

# Luego hacer operaciones para ver DEBUG logs
```

### Limpiar Memcached

```bash
# Desde terminal
echo "flush_all" | nc localhost 11211

# Desde Python
cache.clear()
```

## 📝 Timeouts (Tiempos de Vida)

| Tipo | TTL | Uso |
|---|---|---|
| DEFAULT | 15 min | Uso general |
| RUC_VALID | 1 hora | RUCs verificados |
| RUC_INVALID | 24 horas | RUCs no encontrados |
| RATE_LIMIT | 1 minuto | Tracking de rate limit |

Modificar en `cache_service.py`:

```python
class APICacheService:
    DEFAULT_TTL = 900        # Cambiar aquí
    RUC_VALID_TTL = 3600     # Cambiar aquí
    RUC_INVALID_TTL = 86400  # Cambiar aquí
```

## 🔗 Integración con MigoAPIService

En `migo_service.py`:

```python
from api_service.services.cache_service import APICacheService

class MigoAPIService:
    def __init__(self):
        self.cache_service = APICacheService()
    
    def consultar_ruc(self, ruc: str):
        # Verificar cache válidos
        if cached := self.cache_service.get_ruc(ruc):
            return cached
        
        # Verificar cache inválidos
        if self.cache_service.is_ruc_invalid(ruc):
            return {'success': False, 'error': 'RUC no existe'}
        
        # Consultar API
        result = self._make_request('consultar_ruc', {'ruc': ruc})
        
        # Guardar en cache
        if result.get('success'):
            self.cache_service.set_ruc(ruc, result)
        else:
            self.cache_service.add_invalid_ruc(ruc, 'NO_EXISTE_SUNAT')
        
        return result
```

## 📚 Documentación Completa

- **[CACHE_README.md](./CACHE_README.md)** - Documentación detallada
- **[CACHE_SERVICE_REVIEW.md](../CACHE_SERVICE_REVIEW.md)** - Revisión completa
- **[test_cache.py](./test_cache.py)** - Suite de tests

## ✅ Checklist Pre-Producción

- [ ] Memcached está instalado y corriendo
- [ ] Puerto 11211 es accesible
- [ ] Settings.py tiene CACHES configurado
- [ ] `test_cache.py` pasa todos los tests
- [ ] `cache.get_health()` devuelve status 'healthy'
- [ ] Se integró con `migo_service.py`
- [ ] Logs DEBUG están configurados
- [ ] Backups o monitoreo está en lugar

## 🚀 Próximos Pasos

1. **Corto Plazo**:
   - [ ] Ejecutar tests en servidor de staging
   - [ ] Configurar monitoreo de health checks
   - [ ] Integrar con APIMIGO

2. **Mediano Plazo**:
   - [ ] Agregar task en Celery para cleanup periódico
   - [ ] Dashboard en Django admin para estadísticas
   - [ ] Alertas si cache cae

3. **Largo Plazo**:
   - [ ] Considerar migrar a Redis
   - [ ] Agregar más servicios API (APINUBEFACT, SUNAT)
   - [ ] Implementar cache warming

---

**¿Problemas?** Revisar [CACHE_README.md](./CACHE_README.md) o ejecutar tests.
