# Project Plan — Sistema de Facturación Electrónica (Perú) ✅

**Propósito:** Guía de ejecución para implementar e2e de facturación electrónica, mejorar cálculos, pruebas y robustez. Este archivo será la guía maestra y fuente para crear issues y PRs.

---

## 1. Resumen ejecutivo
- Estado: Etapa inicial — modelos y clientes API estructurados, faltan piezas críticas (generación JSON e‑bill, envío/recepción, calculador de totales).
- Objetivo inmediato: Implementar flujo e‑bill (generar JSON, enviar a proveedor/SUNAT, persistir respuesta/CDR), robustecer cálculos, aumentar cobertura de tests y automatizar envíos idempotentes.

---

## 2. Mapa de módulos
- billing/ — Modelos y lógica de facturación (`AccountMove`, `AccountMoveLine`, `ElectronicInvoice`, secuencias, comandos).
- core/ — Tareas y utilidades Celery (`process_csv_file`, `reprocess_pending_tasks`, `celery_status`).
- users/ — Modelo `User` extendido y relación con `Partner`.
- api_service/ — Cliente APIMIGO, auditoría `ApiCallLog`, rate-limit y batch requests.
- celery-data/ — Schedules/archivos del scheduler (información operativa).

---

## 3. Hallazgos clave
- Implementaciones sólidas: modelos y cliente APIMIGO.
- Falta crítica: **generador de JSON para e‑bill** y **servicio de envío/recepción**.
- `billing/services/invoice_calculator.py` está vacío — imprescindible para cálculos de líneas/factura y redondeo.
- Buen patrón en `SequenceService` pero requiere tests de concurrencia y consolidación de helpers.

---

## 4. Tareas priorizadas (pueden usarse como issues)

### Alta prioridad
1. Implementar `InvoiceCalculatorService` (`billing/services/invoice_calculator.py`)
   - Tests: `tests/billing/test_invoice_calculator.py`
   - Casos: impuestos %, descuentos, anticipos, redondeo por línea/global, tolerancia 0.01.

2. Crear `EInvoiceService` (`billing/services/einvoice_service.py`)
   - Methods: `generate_json(account_move)`, `send_to_provider(json, provider_config)`, `handle_response`.
   - Tests: `tests/billing/test_einvoice_service.py` (mocks provider).

3. Idempotencia en envíos (idempotency-key / checks)
   - Tests: reenvío simulado, provider success/failure.

### Media prioridad
4. Reintentos y backoff en `api_service` (5xx), contador atómico (Redis) para rate-limit.
5. Tests de concurrencia para `SequenceService`.
6. Refactor helpers duplicados (document_type).

### Baja prioridad
7. Integración Celery+Redis en CI (docker-compose).
8. Documentación detallada de proveedores y despliegue.

---

## 5. Plantilla de issue (ejemplo)
- Title: `Implementar Invoice Calculator - cálculos y redondeo`
- Description: Objetivo, archivos, tests mínimos, criterios de aceptación.
- Labels: `billing`, `high priority`, `backend`, `tests`

---

## 6. Recomendaciones técnicas rápidas
- Usar `Decimal` + `quantize(..., rounding=ROUND_HALF_UP)`.
- Guardar `sent_json` / `response_json` / `xml_version` / `cdr_url_s3` en `ElectronicInvoice`.
- No loggear tokens en texto claro; preferir secrets manager o cifrado.

---

## 7. Próximos pasos sugeridos
1. Confirmar creación de los archivos y branch.  
2. Crear issue para "Invoice Calculator" y PR inicial con tests.  
3. Implementación incremental (PRs pequeños y revisables).

---
