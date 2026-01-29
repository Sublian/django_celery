# APICacheService - Guía de Referencia

## Resumen

`APICacheService` es un servicio centralizado de cache para las APIs externas (actualmente APIMIGO, escalable para otros servicios). Utiliza **Memcached** como backend y proporciona métodos especializados para diferentes tipos de datos.

## Instalación y Configuración

### 1. Instalar Memcached

```bash
# Ubuntu/Debian
sudo apt-get install memcached libmemcached-tools

# MacOS
brew install memcached
```

### 2. Iniciar Memcached

```bash
# Puerta por defecto: 11211
memcached -p 11211

# O en background
nohup memcached -p 11211 > /tmp/memcached.log 2>&1 &
```

### 3. Verificar Configuración en Django

En `settings.py`, ya debe estar configurado:

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

## Timeouts por Defecto

| Tipo de Dato | TTL | Descripción |
|---|---|---|
| DEFAULT | 900s | 15 minutos - Uso general |
| RUC_VALID | 3600s | 1 hora - RUCs verificados en SUNAT |
| RUC_INVALID | 86400s | 24 horas - RUCs no encontrados en SUNAT |
| RATE_LIMIT | 60s | 1 minuto - Tracking de rate limiting |

## Métodos Principales

### Operaciones Básicas

```python
from api_service.services.cache_service import APICacheService

cache_service = APICacheService()

# GET - Obtener un valor
valor = cache_service.get('mi_clave')
valor = cache_service.get('mi_clave', default={'vacio': True})

# SET - Guardar un valor
cache_service.set('mi_clave', {'datos': 'algo'})
cache_service.set('mi_clave', {'datos': 'algo'}, ttl=7200)  # 2 horas

# DELETE - Eliminar una clave
cache_service.delete('mi_clave')

# CLEAR - Limpiar TODO el cache (¡cuidado!)
cache_service.clear()
```

### Manejo de RUCs Válidos

```python
# Guardar RUC válido (1 hora)
cache_service.set_ruc('20100038146', {
    'nombre_o_razon_social': 'CONTINENTAL S.A.C.',
    'estado_del_contribuyente': 'ACTIVO',
    'condicion_de_domicilio': 'HABIDO',
    'direccion_simple': 'AV. EL DERBY NRO. 254...',
})

# Obtener RUC
ruc_data = cache_service.get_ruc('20100038146')
if ruc_data:
    print(f"Razón Social: {ruc_data['nombre_o_razon_social']}")

# Eliminar RUC del cache
cache_service.delete_ruc('20100038146')
```

### Manejo de RUCs Inválidos

```python
# Marcar RUC como inválido (24 horas)
cache_service.add_invalid_ruc(
    ruc='20999999999',
    reason='NO_EXISTE_SUNAT',
    ttl_hours=24
)

# Verificar si RUC es inválido
if cache_service.is_ruc_invalid('20999999999'):
    print("RUC está marcado como inválido")

# Obtener información del RUC inválido
info = cache_service.get_invalid_ruc_info('20999999999')
print(f"Razón: {info['reason']}")
print(f"Agregado: {info['added_at']}")

# Remover RUC del cache de inválidos
cache_service.remove_invalid_ruc('20999999999')

# Obtener todos los RUCs inválidos
todos_invalidos = cache_service.get_all_invalid_rucs()
for ruc, info in todos_invalidos.items():
    print(f"{ruc}: {info['reason']}")

# Limpiar todos los RUCs inválidos
cache_service.clear_invalid_rucs()
```

### Monitoreo y Estadísticas

```python
# Obtener estadísticas completas
stats = cache_service.get_cache_stats()
print(f"Backend: {stats['backend']}")
print(f"RUCs inválidos: {stats['invalid_rucs']['total_count']}")
print(f"Breakdown por razón: {stats['invalid_rucs']['breakdown_by_reason']}")

# Verificar salud del cache
health = cache_service.get_health()
if health['status'] == 'healthy':
    print("✅ Cache está funcionando correctamente")
else:
    print(f"⚠️  Estado: {health['status']}")
    print(f"Detalles: {health['checks']}")

# Limpiar elementos expirados
cleaned = cache_service.cleanup_expired()
print(f"Limpios: {cleaned}")
```

## Patrones de Uso en APIMIGO

### En `migo_service.py`

```python
from api_service.services.cache_service import APICacheService

class MigoAPIService:
    def __init__(self):
        self.cache_service = APICacheService()
    
    def consultar_ruc(self, ruc: str) -> Dict[str, Any]:
        # 1. Verificar si está en cache válidos
        cached_data = self.cache_service.get_ruc(ruc)
        if cached_data:
            return {**cached_data, 'cache_hit': True}
        
        # 2. Verificar si está en cache inválidos
        if self.cache_service.is_ruc_invalid(ruc):
            return {'success': False, 'error': 'RUC en cache de inválidos'}
        
        # 3. Consultar API
        result = self._make_request('consultar_ruc', {'ruc': ruc})
        
        # 4. Guardar en cache (válido o inválido)
        if result.get('success'):
            self.cache_service.set_ruc(ruc, result)
        else:
            self.cache_service.add_invalid_ruc(ruc, 'NO_EXISTE_SUNAT')
        
        return result
```

## Limitaciones y Consideraciones

### Limitaciones de Memcached

| Limitación | Valor | Impacto |
|---|---|---|
| Tamaño máximo de valor | ~1MB | RUCs grandes pueden no caber |
| Tamaño máximo de clave | 250 caracteres | Se truncan y hashean automáticamente |
| Persistencia | No persiste | Se pierden datos al reiniciar |
| TTL máximo | ~30 días | Suficiente para nuestro uso |
| Patrón de claves | No soporta | No hay SCAN/PATTERN |

### Limitaciones Actuales

1. **No hay soporte para SCAN**: No se pueden buscar claves por patrón en Memcached
2. **`clear_service_cache()` limitado**: Solo funciona con claves conocidas
3. **No hay persistencia**: Los datos se pierden al reiniciar Memcached

### Soluciones Futuras

Para mejor escalabilidad con múltiples servicios:

1. **Migrar a Redis**:
   - Soporte para SCAN y patrones
   - Persistencia RDB/AOF
   - Mejor para debugging
   - Cluster support

2. **Implementar mecanismo de key tracking**:
   - Base de datos que registre todas las claves
   - Permite limpiezas selectivas por servicio

3. **Usar namespaces explícitos**:
   ```python
   # Futuro: Para cuando haya múltiples servicios
   cache_service.get_service_cache_key('migo', 'ruc_20100038146')
   # → 'migo:ruc_20100038146'
   ```

## Debugging

### Verificar Conexión a Memcached

```bash
# Desde terminal
echo stats | nc localhost 11211

# Desde Python
>>> from api_service.services.cache_service import APICacheService
>>> cache = APICacheService()
>>> health = cache.get_health()
>>> print(health['status'])
healthy
```

### Ver Logs

```python
import logging

# Habilitar DEBUG logging
logging.getLogger('api_service.services.cache_service').setLevel(logging.DEBUG)

# Luego hacer operaciones
cache_service.get('ruc_20100038146')
# → "Cache HIT: ruc_20100038146"
```

### Limpiar Cache Completamente

```bash
# Desde terminal
echo "flush_all" | nc localhost 11211

# Desde Python
cache_service.clear()
```

## Performance

### Benchmarks (aproximados)

- **GET**: ~1-5ms
- **SET**: ~1-5ms
- **DELETE**: ~1ms
- **Overhead de normalización de claves**: <1ms

### Recomendaciones

1. **Usar TTLs apropiados**:
   - RUCs válidos: 1 hora (datos stabiles)
   - RUCs inválidos: 24 horas (cambian raramente)

2. **Limpieza periódica**:
   ```python
   # En una tarea celery cada hora
   cache_service.cleanup_expired()
   ```

3. **Monitoreo**:
   ```python
   # Cada 5 minutos
   health = cache_service.get_health()
   if health['status'] != 'healthy':
       send_alert('Cache unhealthy')
   ```

## Ejemplos Completos

### Ejemplo 1: Validación de RUC con Cache

```python
def validar_ruc(ruc: str) -> bool:
    cache = APICacheService()
    
    # Revisar cache primero
    if cache.is_ruc_invalid(ruc):
        logger.info(f"RUC {ruc} inválido (desde cache)")
        return False
    
    cached_ruc = cache.get_ruc(ruc)
    if cached_ruc:
        logger.info(f"RUC {ruc} válido (desde cache)")
        return cached_ruc.get('estado_del_contribuyente') == 'ACTIVO'
    
    # Consultar API
    migo = MigoAPIService()
    result = migo.consultar_ruc(ruc)
    
    if result.get('success'):
        return result.get('estado_del_contribuyente') == 'ACTIVO'
    else:
        return False
```

### Ejemplo 2: Consulta Masiva con Cache

```python
def validar_rucs_masivo(rucs: List[str]) -> Dict[str, bool]:
    cache = APICacheService()
    migo = MigoAPIService()
    resultados = {}
    a_consultar = []
    
    # Verificar cache
    for ruc in rucs:
        if cache.is_ruc_invalid(ruc):
            resultados[ruc] = False
        elif cache.get_ruc(ruc):
            resultados[ruc] = True
        else:
            a_consultar.append(ruc)
    
    # Consultar lo que no está en cache
    if a_consultar:
        batch_result = migo.consultar_ruc_masivo(a_consultar)
        for item in batch_result.get('validos', []):
            resultados[item['ruc']] = True
        for item in batch_result.get('invalidos', []):
            resultados[item['ruc']] = False
    
    return resultados
```

## Support

Para problemas o mejoras, contactar al equipo de desarrollo.
