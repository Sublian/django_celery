# Nubefact API Service - Sync & Async Implementation

This document provides a comprehensive guide to the Nubefact API service implementations, including both synchronous and asynchronous versions.

## Overview

Two complementary implementations of the Nubefact API service are provided:

- **NubefactService (Sync)**: Traditional blocking HTTP requests using `requests` library
- **NubefactServiceAsync (Async)**: Non-blocking async/await using `httpx` library

Both share the same configuration (tokens, endpoints, rate limiting) through Django models.

## Architecture

### Shared Configuration

Both implementations use the same Django models for configuration:

- **ApiService**: Base service configuration (URL, auth token, status)
- **ApiEndpoint**: API endpoint definitions (path, timeout, etc.)
- **ApiRateLimit**: Rate limiting rules and state
- **ApiCallLog**: Complete audit trail of all API calls

### Key Differences

| Aspect | Sync (NubefactService) | Async (NubefactServiceAsync) |
|--------|----------------------|------------------------------|
| **HTTP Library** | `requests` | `httpx` |
| **Concurrency** | Sequential | Concurrent (asyncio) |
| **Threading** | None | ThreadPoolExecutor for ORM ops |
| **Inheritance** | BaseAPIService | Direct ABC (deferred init) |
| **Throughput (50 req)** | ~90 seconds (~0.5 req/s) | ~0.5 seconds (~100 req/s) |

## Synchronous Implementation (NubefactService)

### Location
```
api_service/services/nubefact/nubefact_service.py
```

### Usage

#### Basic Usage
```python
from api_service.services.nubefact.nubefact_service import NubefactService

service = NubefactService()

payload = {
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',
    'serie': 'F001',
    'numero': 12345,
    'items': [...],
    # ... other required fields
}

response = service.generar_comprobante(payload)
print(response['enlace'])  # Invoice link
print(response['codigo_hash'])  # Hash code
```

#### Context Manager
```python
from api_service.services.nubefact.nubefact_service import NubefactService

with NubefactService() as service:
    response = service.generar_comprobante(payload)
    # Connection automatically closed
```

### Methods

- **`generar_comprobante(payload: dict) -> dict`**: Generate invoice (factura)
  - Returns: Invoice data with enlace (link), codigo_hash (hash code)
  - Validates: Complete payload structure, item calculations, client info

- **`consultar_comprobante(numero: str) -> dict`**: Query existing invoice
  - Returns: Current invoice status from Nubefact

- **`anular_comprobante(numero: str, motivo: str) -> dict`**: Cancel/void invoice
  - Parameters: Invoice number, cancellation reason
  - Returns: Cancellation confirmation

### Testing

```bash
# Run unit tests
python -m pytest api_service/services/nubefact/test_nubefact_service.py -v

# Run integration test (real API calls)
python api_service/tests/test_nubefact_integration.py

# Run stress test (50 sequential requests)
python test_stress_sync.py
```

## Asynchronous Implementation (NubefactServiceAsync)

### Location
```
api_service/services/nubefact/nubefact_service_async.py
```

### Key Design Decisions

**Deferred Initialization**: Unlike BaseAPIService, async version does NOT inherit the sync base class or call DB operations in `__init__`. This avoids Django's "SynchronousOnlyOperation" errors.

**ThreadPoolExecutor**: All Django ORM operations (endpoint fetch, rate-limit check, logging) run in a thread pool via `loop.run_in_executor()`, keeping async context clean.

**Fire-and-Forget Logging**: Rate limit updates and API call logging run as background tasks via `asyncio.create_task()`, preventing async code from blocking on DB writes.

### Usage

#### Async Context Manager (Recommended)
```python
import asyncio
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync

async def main():
    payload = {
        'operacion': 'generar_comprobante',
        'tipo_de_comprobante': '1',
        'serie': 'F001',
        'numero': 12345,
        'items': [...],
        # ... other required fields
    }
    
    async with NubefactServiceAsync() as service:
        response = await service.generar_comprobante(payload)
        print(response['enlace'])  # Invoice link
        print(response['codigo_hash'])  # Hash code

asyncio.run(main())
```

#### Direct Usage
```python
async def send_invoices():
    service = NubefactServiceAsync()
    
    try:
        response = await service.generar_comprobante(payload)
        return response
    finally:
        if service._client:
            await service._client.aclose()
```

### Methods

Same as sync version, but all are async coroutines:

- **`async generar_comprobante(payload: dict) -> dict`**
- **`async consultar_comprobante(numero: str) -> dict`**
- **`async anular_comprobante(numero: str, motivo: str) -> dict`**

### Concurrent Usage (Concurrency Control)

```python
import asyncio

async def send_multiple_invoices(payloads: list):
    """Send multiple invoices concurrently with rate limiting"""
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def send_with_limit(payload):
        async with semaphore:
            async with NubefactServiceAsync() as svc:
                return await svc.generar_comprobante(payload)
    
    tasks = [send_with_limit(p) for p in payloads]
    results = await asyncio.gather(*tasks)
    return results

# Send 50 invoices with max 10 concurrent
payloads = [create_payload(i) for i in range(50)]
results = asyncio.run(send_multiple_invoices(payloads))
```

### Testing

```bash
# Run unit tests
python -m pytest api_service/services/nubefact/test_nubefact_async.py -v

# Run quick integration test (single request)
python test_async_quick.py

# Run stress test (50 concurrent requests)
python test_stress_async.py
```

## Performance Comparison

### Test Results (50 Invoices)

**Synchronous (Sequential):**
- Total Time: ~90 seconds
- Throughput: 0.55 requests/second
- Pattern: Each request blocks until response

**Asynchronous (10 concurrent):**
- Total Time: 0.46 seconds
- Throughput: 107.82 requests/second
- Pattern: Multiple requests in flight simultaneously
- **Speedup: ~195x faster**

## Payload Structure

Both implementations use the same payload format:

```python
payload = {
    # Invoice metadata
    'operacion': 'generar_comprobante',
    'tipo_de_comprobante': '1',  # 1=Invoice, 3=Credit Note, etc.
    'serie': 'F001',
    'numero': 12345,
    'fecha_de_emision': '30/01/2026',
    'moneda': 'PEN',  # Peruvian sol
    
    # Tax configuration
    'porcentaje_de_igv': 18.0,
    'total_gravada': 1440.68,  # Taxable amount
    'total_igv': 259.20,  # Tax amount (18%)
    'total': '1699.20',  # Grand total
    
    # Discount/Deductions
    'descuento_global': 0,
    'descuento': 0,
    'anticipos': 0,
    'redondeo': 0,
    
    # Invoice items
    'items': [
        {
            'unidad_de_medida': 'ZZ',  # Generic unit
            'descripcion': 'PRODUCTO 1',
            'cantidad': 1.0,
            'valor_unitario': 1699.20,  # Unit price without tax
            'precio_unitario': 2000.00,  # Unit price with tax
            'descuento': 0,
            'tipo_de_igv': 'gravada',  # Taxable
            'codigo_interior': 'PROD001',
            'codigo_producto_sunat': '31000000',
        }
    ],
    
    # Client information
    'cliente_numero_de_documento': '20343443961',  # RUC
    'cliente_tipo_de_documento': '6',  # 6=RUC, 1=DNI
    'cliente_denominacion': 'EMPRESA TEST SA',
    'cliente_email': 'contact@empresa.pe',
    'cliente_domicilio': 'Av. Principal 123',
    'cliente_pais_de_domicilio': 'PE',
    'cliente_ubigeo': '150131',
    
    # Detractions (optional, for eligible items)
    'detraccion': True,
    
    # Credit sale indicator
    'venta_al_credito': True,
    
    # Related documents (optional)
    'guias_relacionadas': [],
    'relacionados': [],
    
    # Email delivery (optional)
    'envio_personalizado_correo': False,
    'envio_personalizado_usuario': 'accounting@empresa.pe',
}
```

## Error Handling

Both implementations raise custom exceptions:

### Exception Types

```python
from api_service.services.nubefact.exceptions import (
    NubefactValidationError,  # Invalid payload
    NubefactAPIError,  # API errors (HTTP 500, network issues)
)

try:
    async with NubefactServiceAsync() as svc:
        response = await svc.generar_comprobante(payload)
except NubefactValidationError as e:
    # Handle validation errors (bad data)
    print(f"Validation failed: {e}")
except NubefactAPIError as e:
    # Handle API errors (server issues, network)
    print(f"API error: {e}")
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `El total del comprobante no coincide...` | Item totals don't match | Verify item prices and tax calculation |
| `Este documento ya existe...` | Invoice number already used | Use a different invoice number |
| `RUC inválido` | Client RUC validation failed | Verify RUC format (11 digits) |
| `Token inválido o expirado` | Auth token issue | Check ApiService.auth_token in DB |
| `{'errors': 'Solicitud incorrecta'}` | Malformed request | Verify payload structure |

## Configuration (Django Admin)

### Setting up Nubefact Service

1. **Create ApiService record:**
   - Name: "NUBEFACT"
   - Service Type: "NUBEFACT"
   - Base URL: `https://api.nubefact.com`
   - Auth Token: Your Nubefact API token
   - Is Active: ✓

2. **Create ApiEndpoint records:**
   
   | Name | Path | Timeout | Method |
   |------|------|---------|--------|
   | generar_comprobante | /api/v2/generar | 60 | POST |
   | consultar_comprobante | /api/v2/consultar | 30 | POST |
   | anular_comprobante | /api/v2/anular | 30 | POST |

3. **Create ApiRateLimit records:**
   - Set appropriate rate limits per endpoint
   - Current count: 0
   - Last request: auto-set

## Logging & Auditing

### ApiCallLog

Every successful API call is logged:

```python
from api_service.models import ApiCallLog

# Query all Nubefact calls
logs = ApiCallLog.objects.filter(
    service__service_type='NUBEFACT'
).order_by('-created_at')

# Analyze by status
success = logs.filter(status='SUCCESS').count()
failed = logs.filter(status='FAILED').count()

# Get response times
from django.db.models import Avg
avg_time = logs.aggregate(Avg('response_time_ms'))
```

### Available Metrics

- `status`: SUCCESS, FAILED, RATE_LIMITED, RETRYING
- `response_code`: HTTP status code
- `response_time_ms`: Round-trip time in milliseconds
- `response_data`: Full API response (stored as JSON)

## Migration Path: Sync → Async

### When to Use Each

**Use Synchronous** when:
- Simple, one-off API calls
- Sending a single or few invoices
- Running in non-async context (management commands, signals)
- Debugging is easier priority than performance

**Use Asynchronous** when:
- Bulk operations (50+ invoices)
- High-throughput scenarios
- Running in async framework (FastAPI, Django Async Views)
- Performance and responsiveness critical

### Migration Example

```python
# Before (Sync)
def process_invoices(invoices):
    service = NubefactService()
    results = []
    for inv in invoices:
        result = service.generar_comprobante(inv)
        results.append(result)
    return results  # Takes ~90s for 50 invoices

# After (Async)
async def process_invoices(invoices):
    async with NubefactServiceAsync() as service:
        tasks = [
            service.generar_comprobante(inv)
            for inv in invoices
        ]
        return await asyncio.gather(*tasks)
    # Takes ~0.5s for 50 invoices with concurrency
```

## Troubleshooting

### "SynchronousOnlyOperation" Errors

**Cause**: Calling sync code from async context.

**Solution**: 
- Use `NubefactServiceAsync` instead of `NubefactService`
- Wrap sync calls with `sync_to_async()` if necessary

### Rate Limiting

**Cause**: Too many requests in short time.

**Solution**:
- Use `Semaphore` to limit concurrent requests
- Check ApiRateLimit configuration in Django admin
- Increase `min_interval` between requests

### Token Errors

**Cause**: Invalid or expired token.

**Solution**:
1. Verify token in `ApiService` record (Django admin)
2. Regenerate token in Nubefact dashboard if needed
3. Ensure `Bearer ` prefix is automatically added (handled by code)

### Connection Timeouts

**Cause**: API unresponsive or network issues.

**Solution**:
- Increase timeout: `NubefactServiceAsync(timeout=(60, 120))`
- Check ApiEndpoint timeout configuration
- Verify network connectivity to `api.nubefact.com`

## Testing Checklist

```bash
# Unit Tests
pytest api_service/services/nubefact/test_nubefact_service.py -v
pytest api_service/services/nubefact/test_nubefact_async.py -v

# Integration Tests (Real API)
python api_service/tests/test_nubefact_integration.py
python test_async_quick.py

# Stress Tests
python test_stress_sync.py  # Sequential 50 requests
python test_stress_async.py  # Concurrent 50 requests

# Results Analysis
# Check stress_results_*.json for timing metrics
```

## Files Reference

### Core Implementation
- `api_service/services/nubefact/base_service.py` - Base class for sync services
- `api_service/services/nubefact/nubefact_service.py` - Synchronous implementation
- `api_service/services/nubefact/nubefact_service_async.py` - Asynchronous implementation

### Utilities
- `api_service/services/nubefact/validators.py` - Payload validation
- `api_service/services/nubefact/exceptions.py` - Custom exceptions

### Tests
- `api_service/services/nubefact/test_nubefact_service.py` - Sync unit tests
- `api_service/services/nubefact/test_nubefact_async.py` - Async unit tests
- `api_service/tests/test_nubefact_integration.py` - Sync integration test
- `test_async_quick.py` - Async quick test
- `test_stress_sync.py` - Sync stress test (50 sequential)
- `test_stress_async.py` - Async stress test (50 concurrent)

### Models
- `api_service/models.py`:
  - `ApiService` - Service configuration
  - `ApiEndpoint` - Endpoint definitions
  - `ApiRateLimit` - Rate limiting
  - `ApiCallLog` - Call audit trail

## Support & Debugging

### Enable Debug Logging

```python
import logging

# Get logger for Nubefact services
logger = logging.getLogger('api_service.services.nubefact')
logger.setLevel(logging.DEBUG)

# Or globally
logging.getLogger().setLevel(logging.DEBUG)
```

### Inspect Requests/Responses

```python
# View API calls made
from api_service.models import ApiCallLog

logs = ApiCallLog.objects.filter(
    service__service_type='NUBEFACT'
).order_by('-created_at')[:10]

for log in logs:
    print(f"{log.status} - {log.response_code}")
    print(f"  Request:  {log.request_data}")
    print(f"  Response: {log.response_data}")
    print(f"  Time:     {log.response_time_ms}ms")
```

---

**Last Updated**: January 30, 2026  
**Version**: 1.0 - Async Implementation Complete
