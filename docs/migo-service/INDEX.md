# 📚 MigoAPIService Documentation Index

## Quick Links

### 🧪 Testing
- [Test Results](./TEST_RESULTS.md) - 18/18 tests passing ✅

### 🏗️ Architecture
- [API Overview](./API_OVERVIEW.md) - Service design
- [Endpoints Guide](./ENDPOINTS_GUIDE.md) - All endpoints documented
- [Cache Integration](./CACHE_INTEGRATION.md) - How cache works

### 🚀 Usage Guide
- [Getting Started](./GETTING_STARTED.md) - Basic usage
- [RUC Operations](./RUC_OPERATIONS.md) - RUC queries
- [Batch Operations](./BATCH_OPERATIONS.md) - Bulk processing
- [Billing Validation](./BILLING_VALIDATION.md) - Facturación

### 🔧 Configuration
- [Setup Guide](./SETUP_GUIDE.md) - Configuration
- [Rate Limiting](./RATE_LIMITING.md) - Rate limit config
- [Error Handling](./ERROR_HANDLING.md) - Exception handling

---

## Overview

MigoAPIService is a specialized API client for APIMIGO with comprehensive functionality.

**Features:**
- ✅ RUC queries (individual and batch)
- ✅ DNI queries
- ✅ Exchange rate queries (latest, by date, range)
- ✅ Legal representatives lookup
- ✅ Billing validation (ACTIVO, HABIDO)
- ✅ Batch processing (up to 100 RUCs per call, auto-partitioning)
- ✅ Cache integration (1 hour for valid, 24 hours for invalid)
- ✅ Rate limiting
- ✅ Comprehensive logging

**Current Status:** ✅ Production Ready (18/18 tests passing)

---

## Test Coverage

```
✅ 18 Tests All Passing
├─ Initialization (2 tests)
├─ Validations (1 test)
├─ Individual Queries (2 tests)
├─ Exchange Rate (3 tests)
├─ Representatives (1 test)
├─ Batch Queries (2 tests)
├─ Billing Validation (2 tests)
├─ Cache (1 test)
├─ Rate Limiting (1 test)
├─ Logging (1 test)
├─ Integration (1 test)
└─ Summary (1 test)
```

---

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ruc` | POST | Query single RUC |
| `/api/v1/dni` | POST | Query DNI |
| `/api/v1/exchange/latest` | POST | Latest exchange rate |
| `/api/v1/exchange/date` | POST | Exchange rate by date |
| `/api/v1/exchange` | POST | Exchange rate range |
| `/api/v1/ruc/representantes-legales` | POST | Legal representatives |
| `/api/v1/ruc/collection` | POST | Batch RUC queries |

---

## Quick Start

```python
from api_service.services.migo_service import MigoAPIService

# Initialize
migo = MigoAPIService()

# Query single RUC
result = migo.consultar_ruc('20100038146')
print(result)  # {'nombre_o_razon_social': 'CONTINENTAL S.A.C.', ...}

# Validate for billing
validation = migo.validar_ruc_para_facturacion('20100038146')
print(validation['valido'])  # True/False

# Batch query (max 100)
rucs = ['20100038146', '20000000001', '20123456789']
results = migo.consultar_ruc_masivo(rucs)
print(results['total_validos'])  # Number of valid

# Exchange rate
tc = migo.consultar_tipo_cambio_latest()
print(tc['tipo_cambio'])  # Exchange rate value
```

---

## Caching Behavior

| Type | TTL | Details |
|------|-----|---------|
| Valid RUC | 1 hour | Company info cached |
| Invalid RUC | 24 hours | Prevents repeated API calls |
| Exchange Rate | Configured | By configuration |

---

## Batch Processing

- **Limit:** 100 RUCs per API call
- **Auto-partitioning:** >100 RUCs automatically split
- **Consolidation:** Results merged automatically
- **Rate limiting:** 2 second delay between batches

---

## Billing Validation Criteria

A RUC is valid for billing when:
1. ✅ Estado del contribuyente = "ACTIVO"
2. ✅ Condición de domicilio = "HABIDO"
3. ✅ Address is complete (>10 characters)
4. ✅ Data is up-to-date

---

## Documentation Structure

```
docs/migo-service/
├── TEST_RESULTS.md                 (This file)
├── API_OVERVIEW.md                 (Architecture)
├── ENDPOINTS_GUIDE.md              (All endpoints)
├── CACHE_INTEGRATION.md            (Cache behavior)
├── GETTING_STARTED.md              (Basic usage)
├── RUC_OPERATIONS.md               (RUC queries)
├── BATCH_OPERATIONS.md             (Bulk processing)
├── BILLING_VALIDATION.md           (Facturación)
├── SETUP_GUIDE.md                  (Configuration)
├── RATE_LIMITING.md                (Rate limits)
└── ERROR_HANDLING.md               (Exceptions)
```

---

## Error Handling

Common error scenarios:
- **RUC not found** - Marked as invalid for 24 hours
- **Rate limit exceeded** - Wait time calculated
- **Connection error** - Auto-retry with exponential backoff
- **Invalid format** - Rejected before API call

