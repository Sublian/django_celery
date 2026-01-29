# 🗄️ Caching Strategy Guide

**Last Updated:** January 28, 2026  
**Status:** Production ✅

---

## Overview

The caching system in this project is built around **APICacheService**, a centralized service that provides:
- Flexible backend support (LocMemCache, Memcached, Redis)
- Multi-service key namespace isolation
- RUC validity tracking
- Cache statistics and monitoring

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                      │
│              (MigoAPIService, OtherServices)            │
└──────────────────────┬──────────────────────────────────┘
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────────┐
│               APICacheService                           │
│    (Centralized Cache Abstraction)                      │
├─────────────────────────────────────────────────────────┤
│ • Key Management      • Statistics                      │
│ • TTL Handling        • Multi-Service Support           │
│ • RUC Tracking        • Expiration Cleanup              │
└──────────────────────┬──────────────────────────────────┘
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────────┐
│             Django Cache Framework                      │
│    (Memcached, Redis, LocMemCache, etc.)               │
└─────────────────────────────────────────────────────────┘
```

---

## Key Types & Naming

### Standard Key Format

```python
# Single service
key = f"{service}:{key_type}_{identifier}"

# Examples
"migo:ruc_20123456789"           # MIGO API RUC query
"nubefact:invoice_INV-001"       # NubeFactura invoice
"cache:stats_2026_01_28"         # Cache statistics
```

### Special Keys

```python
# Invalid RUC tracking
"invalid_rucs"                   # Dict of invalid RUCs

# Service stats
f"stats_{service}_{date}"        # Service statistics

# Batch operations
f"batch_{service}_{batch_id}"    # Batch result tracking
```

---

## TTL (Time-To-Live) Configuration

### Default TTLs

| Data Type | TTL | Reasoning |
|-----------|-----|-----------|
| RUC Query | 1 hour (3600s) | Business data stable |
| Exchange Rate | 1 day (86400s) | Rates update daily |
| Rate Limits | 1 minute (60s) | Should refresh frequently |
| Invalid RUCs | 7 days (604800s) | Long-term tracking |
| Statistics | 1 day (86400s) | Daily reports |

### Configuration

```python
# In api_service/services/cache_service.py
CACHE_TIMEOUT_SHORT = 60        # 1 minute
CACHE_TIMEOUT_MEDIUM = 3600     # 1 hour
CACHE_TIMEOUT_LONG = 86400      # 1 day
CACHE_TIMEOUT_EXTRA_LONG = 604800  # 7 days
```

---

## Usage Patterns

### Pattern 1: Simple GET/SET

```python
from api_service.services import APICacheService

cache = APICacheService()

# SET
data = {"ruc": "20123456789", "name": "Company Inc"}
cache.set("migo_data", data, ttl=3600)

# GET
result = cache.get("migo_data")
# Returns: {"ruc": "20123456789", "name": "Company Inc"}
```

### Pattern 2: Service-Scoped Keys

```python
# Get service-scoped key
cache_key = cache.get_service_cache_key('migo', f'ruc_20123456789')
# Returns: "migo:ruc_20123456789"

# Use it
cache.set(cache_key, data)
```

### Pattern 3: RUC Validation Caching

```python
# Mark invalid RUC
cache.add_invalid_ruc('20000000000', reason='INVALID_FORMAT')

# Check if invalid
if cache.is_ruc_invalid('20000000000'):
    # Skip API call
    return {"success": False, "error": "Invalid RUC format"}

# Get invalid RUCs
invalid_dict = cache.get_invalid_rucs()
```

### Pattern 4: Batch Operations

```python
# Cache multiple RUCs
for ruc in ruc_list:
    cache_key = f"ruc_{ruc}"
    cache.set(cache_key, result, ttl=3600)

# Later: retrieve batch
results = {}
for ruc in ruc_list:
    cached = cache.get(f"ruc_{ruc}")
    if cached:
        results[ruc] = cached
```

---

## Cache Backends

### Development: LocMemCache

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

**Characteristics:**
- ✅ In-memory (no external service)
- ✅ Single-process
- ❌ Not distributed
- ❌ Lost on restart

**Best for:** Local development, testing

---

### Production: Memcached

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': 'memcached:11211',
    }
}
```

**Characteristics:**
- ✅ Distributed
- ✅ Fast
- ✅ LRU eviction
- ⚠️ Requires running service

**Best for:** Production environments

---

### Production: Redis

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
    }
}
```

**Characteristics:**
- ✅ Persistent
- ✅ Distributed
- ✅ Complex data structures
- ✅ Transactions

**Best for:** High-availability production

---

## Monitoring & Statistics

### Get Cache Statistics

```python
stats = cache.get_statistics()
# Returns:
{
    'hits': 1523,
    'misses': 342,
    'hit_rate': 81.6,
    'total_keys': 342,
    'service_breakdown': {
        'migo': {'hits': 900, 'misses': 100},
        'nubefact': {'hits': 623, 'misses': 242}
    },
    'timestamp': '2026-01-28 15:30:00'
}
```

### Check Cache Health

```python
health = cache.get_health()
# Returns:
{
    'status': 'healthy',  # or 'degraded' or 'error'
    'backend': 'memcached',
    'connection': 'OK',
    'avg_response_time': 2.3,  # ms
    'uptime': 86400  # seconds
}
```

### View Invalid RUCs

```python
invalid = cache.get_invalid_rucs()
# Returns:
{
    '20000000000': {
        'reason': 'INVALID_FORMAT',
        'timestamp': '2026-01-25 10:30:00',
        'attempts': 5
    },
    '20999999999': {
        'reason': 'NOT_FOUND',
        'timestamp': '2026-01-26 14:20:00',
        'attempts': 3
    }
}
```

---

## Cleanup & Maintenance

### Automatic Cleanup

```python
# Runs hourly via Celery
from api_service.tasks import cleanup_expired_cache

cleanup_expired_cache.delay()
```

**What it does:**
- Removes expired keys
- Clears old statistics
- Compacts invalid RUC tracking

### Manual Cleanup

```python
# Clear specific service cache
cache.clear_service_cache('migo')

# Clear all cache
cache.clear()

# Remove specific key
cache.delete('migo:ruc_20123456789')
```

---

## Best Practices

### ✅ DO

1. **Use service-scoped keys**
   ```python
   cache_key = cache.get_service_cache_key('migo', f'ruc_{ruc}')
   ```

2. **Set appropriate TTLs**
   ```python
   # Not forever!
   cache.set(key, data, ttl=3600)
   ```

3. **Check cache before API calls**
   ```python
   if cache.get(key):
       return cached_result
   ```

4. **Track invalid data**
   ```python
   cache.add_invalid_ruc(ruc, reason)
   ```

5. **Monitor statistics**
   ```python
   stats = cache.get_statistics()
   log.info(f"Cache hit rate: {stats['hit_rate']:.1f}%")
   ```

### ❌ DON'T

1. **Don't cache large objects**
   ```python
   # ❌ Bad - memcached has size limits
   cache.set(key, large_dataframe)
   
   # ✅ Good - serialize to JSON
   cache.set(key, large_dataframe.to_json())
   ```

2. **Don't rely on cache for critical data**
   ```python
   # ❌ Bad - cache can fail
   critical_data = cache.get(key)
   
   # ✅ Good - cache is optional
   cached_data = cache.get(key)
   if not cached_data:
       critical_data = fetch_from_db()
   ```

3. **Don't forget TTL**
   ```python
   # ❌ Bad - permanent cache
   cache.set(key, data)
   
   # ✅ Good - explicit TTL
   cache.set(key, data, ttl=3600)
   ```

4. **Don't mix services in same key**
   ```python
   # ❌ Bad - namespace pollution
   cache.set("ruc_20123456789", data)
   
   # ✅ Good - service-scoped
   cache.set("migo:ruc_20123456789", data)
   ```

---

## Performance Guidelines

### Cache Hit Rate Target

| Environment | Target | Status |
|-------------|--------|--------|
| Development | > 50% | ℹ️ Variable |
| Staging | > 70% | ℹ️ Target |
| Production | > 80% | ✅ Goal |

### Response Time

| Operation | Target | Typical |
|-----------|--------|---------|
| GET hit | < 5ms | 2-3ms |
| SET | < 10ms | 3-5ms |
| DELETE | < 10ms | 2-4ms |
| CLEAR | < 100ms | 50ms |

### Memory Usage

```python
# Estimate: Average entry size
- RUC query: ~500 bytes
- Exchange rate: ~100 bytes
- Invoice data: ~2 KB

# Typical cache allocation
Memcached: 512MB (≈1 million entries)
Redis: 1GB (≈2 million entries)
```

---

## Troubleshooting

### Issue: Cache Misses Increasing

**Diagnosis:**
```python
stats = cache.get_statistics()
if stats['hit_rate'] < 50:
    print("Issue: Too many cache misses")
```

**Solutions:**
1. Increase TTL for stable data
2. Pre-warm cache with frequent queries
3. Check backend capacity

### Issue: Memory Growing

**Diagnosis:**
```python
cache.get_statistics()  # Check total_keys
cache.get_health()      # Check memory usage
```

**Solutions:**
1. Reduce TTL values
2. Increase backend memory
3. Run cleanup more frequently

### Issue: Cache Not Working

**Diagnosis:**
```python
# Test basic operations
cache.set('test', 'value')
result = cache.get('test')
assert result == 'value'

# Check health
health = cache.get_health()
print(health['status'])
```

**Solutions:**
1. Check backend service running
2. Verify connection settings
3. Review Django cache configuration

---

## Testing

### Cache-Aware Tests

```python
@pytest.fixture
def clear_cache():
    """Clear cache before and after test"""
    cache.clear()
    yield
    cache.clear()

def test_with_cache(clear_cache):
    # Cache is empty
    result = cache.get('key')
    assert result is None
    
    # Set cache
    cache.set('key', 'value')
    
    # Verify
    assert cache.get('key') == 'value'
```

### Test Cache Statistics

```python
def test_cache_statistics(clear_cache):
    # Perform cache operations
    cache.set('key1', 'value1')
    cache.get('key1')  # Hit
    cache.get('key2')  # Miss
    
    # Check statistics
    stats = cache.get_statistics()
    assert stats['hits'] == 1
    assert stats['misses'] == 1
    assert stats['hit_rate'] == 50.0
```

---

## Next Steps

1. **Monitor** cache hit rate in production
2. **Adjust** TTL values based on usage patterns
3. **Scale** backend when approaching capacity
4. **Document** any service-specific patterns

