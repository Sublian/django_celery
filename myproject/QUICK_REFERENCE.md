# Quick Reference - Async Implementation Commands

## Running Tests

### Unit Tests (All Passing)
```bash
pytest api_service/services/nubefact/test_nubefact_async.py -v
# Expected: 3 passed
```

### Integration Test (Real API)
```bash
python test_async_quick.py
# Sends single real invoice to Nubefact API
```

### Stress Test (50 Concurrent)
```bash
python test_stress_async.py
# Results: ~0.46 seconds, 107.82 req/s throughput
# Output: stress_results_async_YYYYMMDD_HHMMSS.json
```

### Verification Script
```bash
python verify_async_implementation.py
# Expected: 12/12 checks passed (100%)
```

## Using the Async Service

### Simple Usage
```python
import asyncio
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync

async def send_invoice():
    payload = {
        'operacion': 'generar_comprobante',
        'tipo_de_comprobante': '1',
        'serie': 'F001',
        'numero': 12345,
        # ... other fields
    }
    
    async with NubefactServiceAsync() as svc:
        response = await svc.generar_comprobante(payload)
        print(response['enlace'])

asyncio.run(send_invoice())
```

### Batch Processing (Concurrent)
```python
import asyncio

async def send_batch(payloads):
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    
    async def send_limited(payload):
        async with semaphore:
            async with NubefactServiceAsync() as svc:
                return await svc.generar_comprobante(payload)
    
    return await asyncio.gather(*[send_limited(p) for p in payloads])

# Send 50 invoices concurrently
results = asyncio.run(send_batch(invoice_payloads))
```

## Configuration (Django Admin)

1. Create `ApiService` record:
   - Name: NUBEFACT
   - Type: NUBEFACT
   - Base URL: https://api.nubefact.com
   - Token: Your Nubefact API token
   - Active: Yes

2. Create `ApiEndpoint` records:
   - Name: generar_comprobante, Path: /api/v2/generar
   - Name: consultar_comprobante, Path: /api/v2/consultar
   - Name: anular_comprobante, Path: /api/v2/anular

## Performance Metrics

- **50 Invoices Async**: 0.46 seconds (107.82 req/s)
- **50 Invoices Sync**: ~90 seconds (0.55 req/s)
- **Improvement**: 195x faster

## Key Files

| File | Purpose |
|------|---------|
| `api_service/services/nubefact/nubefact_service_async.py` | Core async service |
| `api_service/services/nubefact/README.md` | Complete documentation |
| `ASYNC_IMPLEMENTATION_SUMMARY.md` | Project report |
| `DELIVERABLES.md` | This checklist |
| `test_stress_async.py` | Stress test script |

## Troubleshooting

### SynchronousOnlyOperation Error
Use `NubefactServiceAsync` instead of `NubefactService`

### Token Invalid
Check `ApiService.auth_token` in Django admin

### Timeout Issues
Increase timeout: `NubefactServiceAsync(timeout=(60, 120))`

## Documentation

- **User Guide**: `api_service/services/nubefact/README.md`
- **Project Summary**: `ASYNC_IMPLEMENTATION_SUMMARY.md`
- **Deliverables**: `DELIVERABLES.md`
