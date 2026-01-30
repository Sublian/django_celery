# 🔧 CAMBIOS REQUERIDOS: Patrón de Configuración - Resumen de Acción

## Problema
El archivo `config.py` estaba usando `api_base_url` y `api_token` como atributos, pero:
1. No sigue el patrón de MigoAPIService
2. No permite usar múltiples endpoints configurables
3. Almacena la URL completa en lugar de solo la URL base

## Solución Implementada

### 1. ✅ config.py - COMPLETADO
- **Cambio:** Renombré `api_base_url` → `base_url` 
- **Cambio:** Renombré `api_token` → `auth_token`
- **Cambio:** Ya no concatena paths en la URL base
- **Razón:** Ahora solo contiene la URL base (ej: `https://api.nubefact.com`)

### 2. ✅ nubefact_service.py __init__ - COMPLETADO
- **Cambio:** Ahora obtiene `base_url` y `auth_token` desde `self.service` (cargado por BaseAPIService)
- **Cambio:** Agregué `self.token` como alias de `self.auth_token` (compatibilidad con MigoAPIService)
- **Razón:** Patrón consistente con MigoAPIService

### 3. ✅ nubefact_service.py send_request() - COMPLETADO
- **Cambio:** Cambié firma de `send_request(endpoint, ...)` a `send_request(endpoint_name, ...)`
- **Cambio:** Ahora usa `self._get_endpoint(endpoint_name)` para obtener ApiEndpoint de BD
- **Cambio:** Construye URL como `f"{self.base_url}{endpoint.path}"` (patrón MigoAPIService)
- **Cambio:** Usa `endpoint.timeout` en lugar de timeout global
- **Razón:** Configuración por endpoint en la BD

### 4. ✅ nubefact_service.py operaciones - COMPLETADO
- **Cambio:** `emitir_comprobante()` ahora llama `send_request("emitir_comprobante", data)`
- **Cambio:** `consultar_comprobante()` ahora llama `send_request("consultar_comprobante", data)`
- **Cambio:** `anular_comprobante()` ahora llama `send_request("anular_comprobante", data)`
- **Razón:** Nuevo patrón de endpoint_name

### 5. ⏳ client.py - PENDIENTE REVISAR
- Referencia a `config.api_token` → debe cambiar a `config.auth_token`
- Referencia a `config.api_base_url` → debe cambiar a `config.base_url`
- Pero este archivo NO está siendo usado por NubefactService (usa BaseAPIService)

---

## Configuración en BD Requerida

### Antes (Incorrecto)
```
ApiService NUBEFACT:
  base_url = "https://api.nubefact.com/api/v1"  ← URL completa

Llamada en código:
  send_request(endpoint="generar_comprobante", data=datos)
```

### Después (Correcto)
```
ApiService NUBEFACT:
  base_url = "https://api.nubefact.com"  ← Solo base URL

ApiEndpoint (bajo NUBEFACT):
  - name = "emitir_comprobante"
    path = "/api/v1/send"
    timeout = 60
    method = "POST"

  - name = "consultar_comprobante"
    path = "/api/v1/query"
    timeout = 30
    method = "POST"

  - name = "anular_comprobante"
    path = "/api/v1/cancel"
    timeout = 45
    method = "POST"

Llamada en código:
  send_request(endpoint_name="emitir_comprobante", data=datos)
```

---

## Impacto en Código

### Código que SÍ será afectado:
1. ✅ Cualquier llamada a `NubefactService.send_request()` - CAMBIO DE FIRMA
2. ✅ Acceso a `service.base_url` - AHORA VIENE DE BD (no de config.py)
3. ✅ Acceso a `service.auth_token` - AHORA VIENE DE BD (no de config.py)

### Código que NO será afectado:
1. `BaseAPIService` - Sin cambios (solo carga self.service)
2. `base_service.py` - Sin cambios
3. `_log_api_call()` - Sin cambios
4. `_check_rate_limit()` - Sin cambios
5. `_update_rate_limit()` - Sin cambios

---

## Próximos Pasos

### CRÍTICO: Actualizar config.py de BD
Ir a Django admin o shell y cambiar:

```python
# En Django shell:
from api_service.models import ApiService, ApiEndpoint

# Actualizar ApiService
service = ApiService.objects.get(service_type="NUBEFACT")
service.base_url = "https://api.nubefact.com"  # Solo base, sin /api/v1
service.save()

# Crear ApiEndpoints
endpoints = [
    {
        "name": "emitir_comprobante",
        "path": "/api/v1/send",
        "method": "POST",
        "timeout": 60,
    },
    {
        "name": "consultar_comprobante",
        "path": "/api/v1/query",
        "method": "POST",
        "timeout": 30,
    },
    {
        "name": "anular_comprobante",
        "path": "/api/v1/cancel",
        "method": "POST",
        "timeout": 45,
    }
]

for ep in endpoints:
    ApiEndpoint.objects.update_or_create(
        service=service,
        name=ep["name"],
        defaults={
            "path": ep["path"],
            "method": ep["method"],
            "timeout": ep["timeout"],
            "is_active": True,
        }
    )
```

### CRÍTICO: Actualizar tests
Si existen tests que llaman `send_request()`, actualizar:
- `send_request("generar_comprobante", data)` ← ANTIGUA
- `send_request("emitir_comprobante", data)` ← NUEVA

### OPCIONAL: Actualizar client.py
Si se usa client.py (no es el caso actualmente):
- Cambiar `self.config.api_token` → `self.config.auth_token`
- Cambiar `self.config.api_base_url` → `self.config.base_url`

---

## Validación

```python
# Verificar que funciona:
from api_service.services.nubefact.nubefact_service import NubefactService

service = NubefactService()
print(service.base_url)  # ← Debe mostrar: https://api.nubefact.com
print(service.auth_token)  # ← Debe mostrar: Bearer xxx

# Obtener endpoint
endpoint = service._get_endpoint("emitir_comprobante")
print(endpoint.path)  # ← Debe mostrar: /api/v1/send
print(endpoint.timeout)  # ← Debe mostrar: 60

# URL que se construirá:
url = f"{service.base_url}{endpoint.path}"  # ← https://api.nubefact.com/api/v1/send
```

---

## Resumen de Cambios de Código

| Archivo | Cambio | Tipo |
|---------|--------|------|
| config.py | `api_base_url` → `base_url` | Renombrar |
| config.py | `api_token` → `auth_token` | Renombrar |
| config.py | Removida concatenación de paths | Eliminar |
| nubefact_service.py | __init__() obtiene from self.service | Refactor |
| nubefact_service.py | send_request(endpoint) → send_request(endpoint_name) | Cambio firma |
| nubefact_service.py | URL construction: base_url + endpoint.path | Refactor |
| nubefact_service.py | emitir_comprobante() | Actualizar llamada |
| nubefact_service.py | consultar_comprobante() | Actualizar llamada |
| nubefact_service.py | anular_comprobante() | Actualizar llamada |
| client.py | `config.api_token` → `config.auth_token` | Refactor (opcional) |
| client.py | `config.api_base_url` → `config.base_url` | Refactor (opcional) |

---

## Status: ✅ Implementación Completada

Todos los cambios de código han sido aplicados. Ahora está pendiente:
1. Actualizar BD para tener endpoints en ApiEndpoint
2. Tests/validación
3. Actualizar ejemplos en documentación

