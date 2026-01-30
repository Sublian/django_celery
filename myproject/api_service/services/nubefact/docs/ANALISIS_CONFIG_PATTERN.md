# 📋 ANÁLISIS: Patrón de Configuración - Config vs Modelos

## 🎯 Problema Identificado

El archivo `config.py` actual no sigue el patrón utilizado en `MigoAPIService`.

### Patrón Actual (INCORRECTO)
```
config.py retorna:
- api_base_url = "https://api.nubefact.com/api/v1" ← URL COMPLETA
- Luego en send_request():
  - url = f"{base_url}/{endpoint}" ← Concatenación manual
```

### Patrón Correcto (MigoAPIService)
```
config.py retorna:
- base_url = ApiService.base_url (solo base sin paths)
- Luego en send_request():
  - endpoint = ApiEndpoint.path (ruta del endpoint)
  - url = f"{base_url}{endpoint.path}" ← Concatenación correcta
```

---

## 🔍 Análisis Comparativo

### MigoAPIService (`migo_service.py`)

**Configuración:**
```python
def __init__(self, token=None):
    self.service = ApiService.objects.filter(service_type="MIGO").first()
    self.base_url = self.service.base_url  # ← De BD, URL base
    self.token = token or self.service.auth_token
```

**Construcción de URL:**
```python
def _make_request(self, endpoint_name: str, ...):
    endpoint = self._get_endpoint(endpoint_name)  # ← ApiEndpoint.path
    
    # URL se construye así:
    response = requests.post(
        f"{self.base_url}{endpoint.path}",  # ← base_url + endpoint.path
        json=request_data,
        timeout=endpoint.timeout or 30
    )
```

**Ejemplo Real:**
- `self.base_url` = `"https://api.migo.pe"`
- `endpoint.path` = `"/api/v1/ruc"`
- **URL final** = `"https://api.migo.pe/api/v1/ruc"`

---

### NubefactService Actual (INCORRECTO)

**Configuración (config.py):**
```python
def _load_config(self) -> None:
    self.service = ApiService.objects.filter(service_type="NUBEFACT", is_active=True).first()
    self.api_base_url = self.service.base_url or os.getenv('NUBEFACT_API_URL')
    # ← Aquí se asume que base_url ya contiene TODO
    # Ejemplo: "https://api.nubefact.com/api/v1"
```

**Construcción de URL (nubefact_service.py):**
```python
def send_request(self, endpoint: str, ...):
    url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    # ← Concatenación manual con endpoint como parámetro
    # Esto funciona pero NO usa ApiEndpoint.path de BD
```

**Problema:**
- No usa `ApiEndpoint` de la BD
- Tiene que recibir el endpoint como parámetro string
- No beneficia de: timeout custom, rate limiting por endpoint, etc.

---

## ✅ Solución Requerida

### Cambios en `config.py`

1. **Remover la URL completa**
   - Usar solo `ApiService.base_url` (URL base sin paths)
   - No concatenar con paths en config.py

2. **Proporcionar acceso a ApiService**
   - Hacer que `config.service` sea accesible
   - Permitir que NubefactService obtenga ApiEndpoint

3. **Ejemplo de BD correcto:**
   ```
   ApiService (NUBEFACT):
     - base_url = "https://api.nubefact.com"
     - auth_token = "Bearer xxxx"
   
   ApiEndpoint (bajo NUBEFACT):
     - name = "emitir_comprobante"
     - path = "/api/v1/send"
     - timeout = 60
     - method = "POST"
   
   ApiEndpoint (bajo NUBEFACT):
     - name = "consultar_comprobante"
     - path = "/api/v1/query"
     - timeout = 30
     - method = "POST"
   ```

### Cambios en `nubefact_service.py`

1. **Usar `BaseAPIService._get_endpoint()`**
   - Ya existe en base_service.py
   - Obtiene ApiEndpoint de la BD

2. **Cambiar firma de `send_request()`**
   ```python
   # ANTES (manual endpoint string)
   send_request(endpoint="generar_comprobante", data=datos)
   
   # DESPUÉS (endpoint_name como identificador)
   send_request(endpoint_name="emitir_comprobante", data=datos)
   ```

3. **Construcción de URL correcta**
   ```python
   endpoint = self._get_endpoint(endpoint_name)
   url = f"{self.base_url}{endpoint.path}"
   ```

---

## 📊 Diferencias de Comportamiento

| Aspecto | MigoAPIService | NubefactService Actual | NubefactService Correcto |
|---------|---|---|---|
| URL base | `ApiService.base_url` | Full URL en config.py | `ApiService.base_url` |
| Endpoint | `ApiEndpoint.path` | String parameter | `ApiEndpoint.path` |
| Rate limit | Por endpoint (BD) | Por endpoint (BD) | Por endpoint (BD) ✓ |
| Timeout | Por endpoint (BD) | Parámetro global | Por endpoint (BD) ✓ |
| Custom rate | Soportado | Soportado | Soportado ✓ |
| Escalabilidad | ✓ Múltiples endpoints | ✗ Manual | ✓ Múltiples endpoints |

---

## 🔧 Cambios Mínimos Requeridos

### 1. config.py
```python
class NubefactConfig:
    def _load_config(self) -> None:
        # ... 
        self.api_base_url = self.service.base_url  # ← Solo base URL
        # NO concatenar con paths aquí
```

### 2. nubefact_service.py
```python
def send_request(self, endpoint_name: str, data: dict, ...):
    # ← Cambiar de 'endpoint' a 'endpoint_name'
    endpoint = self._get_endpoint(endpoint_name)
    url = f"{self.base_url}{endpoint.path}"
    # ← Usar endpoint.path de BD
```

### 3. Métodos de operación
```python
# ANTES
def emitir_comprobante(self, datos):
    return self.send_request(endpoint="generar_comprobante", data=datos)

# DESPUÉS
def emitir_comprobante(self, datos):
    return self.send_request(endpoint_name="emitir_comprobante", data=datos)
```

---

## 🎓 Beneficios de Seguir el Patrón

1. ✅ **Consistencia** - Mismo patrón que MigoAPIService
2. ✅ **Escalabilidad** - Fácil agregar nuevos endpoints sin cambiar código
3. ✅ **Configurabilidad** - Timeout y rate limit por endpoint en BD
4. ✅ **Testing** - Mismo pattern de mocking que MigoAPIService
5. ✅ **Mantenibilidad** - Menos lógica hardcodeada en código
6. ✅ **Auditabilidad** - Todos los endpoints registrados en BD

---

## 📝 Estado Actual

- [ ] Revisar BD actual para Nubefact
- [ ] Actualizar config.py para usar solo base_url
- [ ] Actualizar nubefact_service.py para usar endpoint_name
- [ ] Actualizar métodos de operación
- [ ] Actualizar tests si existen

---

**Propuesta:** Ajustar config.py y nubefact_service.py para seguir exactamente el patrón de MigoAPIService.
