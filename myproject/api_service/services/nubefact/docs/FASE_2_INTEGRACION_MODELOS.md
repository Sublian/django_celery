# Fase 2 - Refactorización Nubefact: Integración de Modelos

## 🎯 OBJETIVO DE FASE 2

Integrar los modelos Django `ApiRateLimit` y `ApiBatchRequest` en el servicio Nubefact para:
- ✅ Proteger contra rate limiting
- ✅ Soportar operaciones en batch
- ✅ Alinear con los patrones de MigoAPIService

---

## ✅ CAMBIOS IMPLEMENTADOS

### 1. Imports Mejorados en base_service.py ✅

**Antes:**
```python
from api_service.models import ApiEndpoint, ApiService, ApiCallLog
```

**Después:**
```python
from api_service.models import ApiEndpoint, ApiService, ApiCallLog, ApiRateLimit, ApiBatchRequest
from typing import Optional, Tuple  # Added Tuple
```

**Beneficio:** Base service ahora puede acceder a todos los modelos necesarios.

---

### 2. Métodos de Rate Limiting en base_service.py ✅

#### `_check_rate_limit(endpoint_name: str) -> Tuple[bool, float]`

**Funcionalidad:**
- Verifica si se puede hacer una petición según el rate limit
- Retorna `(puede_proceder, tiempo_espera_segundos)`
- Basado en el patrón de MigoAPIService

**Código:**
```python
def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
    """
    Verifica si se puede hacer una petición según el rate limit.
    
    Basado en el patrón de MigoAPIService.
    
    Returns:
        Tuple[bool, float]: (puede_proceder, tiempo_espera_segundos)
    """
    try:
        if not getattr(self, 'service', None):
            return True, 0
            
        endpoint = self._get_endpoint(endpoint_name)
        if endpoint:
            # Obtener o crear registro de rate limit
            rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                self.service, endpoint
            )
            
            # Verificar si se puede hacer la petición
            if rate_limit.can_make_request():
                return True, 0
            else:
                wait_seconds = rate_limit.get_wait_time()
                logger.warning(
                    f"Rate limit excedido para endpoint {endpoint_name}. "
                    f"Esperar {wait_seconds:.1f} segundos"
                )
                return False, wait_seconds
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
    
    # Por defecto, permitir si hay error
    return True, 0
```

**USO:**
```python
can_proceed, wait_time = service._check_rate_limit('emitir_comprobante')
if not can_proceed:
    print(f"Esperar {wait_time} segundos")
```

---

#### `_update_rate_limit(endpoint_name: str) -> None`

**Funcionalidad:**
- Actualiza el contador de rate limit después de una llamada exitosa
- Incrementa el contador de peticiones realizadas

**Código:**
```python
def _update_rate_limit(self, endpoint_name: str) -> None:
    """
    Actualiza el rate limit después de una llamada exitosa.
    
    Incrementa el contador de peticiones realizadas.
    """
    try:
        if not getattr(self, 'service', None):
            return
            
        endpoint = self._get_endpoint(endpoint_name)
        if endpoint:
            rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                self.service, endpoint
            )
            
            # Incrementar contador
            rate_limit.increment_count()
            logger.debug(
                f"Rate limit actualizado para endpoint {endpoint_name}. "
                f"Conteo actual: {rate_limit.current_count}/{rate_limit.get_limit()}"
            )
    except Exception as e:
        logger.error(f"Error updating rate limit: {str(e)}")
```

**USO:**
```python
# Se llama automáticamente después de cada petición exitosa
self._update_rate_limit('emitir_comprobante')
```

---

### 3. Mejorada Función _log_api_call ✅

**Alineación con MigoAPIService:**

**Cambios:**
1. Tipo explícito para `batch_request: ApiBatchRequest = None`
2. Validación con `getattr()` en lugar de solo `if not self.service`
3. Mejor documentación con ejemplo
4. Pass `endpoint` directamente en lugar de `endpoint.id`

**Antes:**
```python
def _log_api_call(self, endpoint_name: str, request_data: dict, 
                 response_data: dict, status: str, error_message: str = "", 
                 duration_ms: int = 0, batch_request=None,
                 caller_info: str = None) -> None:
    # ...
    if not self.service:
        # ...
    ApiCallLog.objects.create(
        endpoint=endpoint.id if endpoint else None,  # ❌ Pasando ID
        batch_request=batch_request,
        # ...
    )
```

**Después:**
```python
def _log_api_call(self, endpoint_name: str, request_data: dict, 
                 response_data: dict, status: str, error_message: str = "", 
                 duration_ms: int = 0, batch_request: ApiBatchRequest = None,
                 caller_info: str = None) -> None:
    """
    Registra llamada API en base de datos.
    
    Alineado con el patrón de MigoAPIService para consistencia.
    """
    if caller_info is None:
        caller_info = self._get_caller_info()

    # Si no hay servicio, solo loguear
    if not getattr(self, 'service', None):  # ✅ Usando getattr
        logger.debug(
            f"[API_CALL] {endpoint_name} status={status} duration={duration_ms}ms error={error_message}"
        )
        return

    try:
        endpoint = self._get_endpoint(endpoint_name)
        logger.debug(f"Registrando llamada API: {endpoint_name}")

        # Si es un RUC inválido (404), registrar información adicional
        if status == "FAILED" and "404" in error_message:
            response_data['invalid_ruc'] = True
            response_data['invalid_reason'] = "RUC_NO_EXISTE_SUNAT"

        # Crear registro - endpoint puede ser None
        ApiCallLog.objects.create(
            service=self.service,
            endpoint=endpoint,  # ✅ Pasando objeto endpoint
            batch_request=batch_request,
            status=status,
            request_data=request_data,
            response_data=response_data,
            response_code=response_data.get('status_code', 200) if isinstance(response_data, dict) else 200,
            error_message=error_message[:500],
            duration_ms=duration_ms,
            called_from=caller_info
        )
        
        logger.info(f"[API_CALL_LOGGED] {endpoint_name} - {status} - {duration_ms}ms")
        
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}")
```

**Beneficio:** Consistencia con MigoAPIService, mejor manejo de errores.

---

### 4. Rate Limiting en send_request ✅

**ANTES (sin rate limiting):**
```python
def send_request(self, endpoint: str, data: dict, method: str = "POST", 
                endpoint_name: str = None) -> Dict[str, Any]:
    # ... directo a validar datos ...
    validated_data = validate_json_structure(data)
```

**DESPUÉS (con rate limiting):**
```python
def send_request(self, endpoint: str, data: dict, method: str = "POST", 
                endpoint_name: str = None, batch_request=None) -> Dict[str, Any]:
    """
    Envía solicitud con rate limiting y batch request support.
    
    Args:
        batch_request: Instancia de ApiBatchRequest si esta llamada es parte de un lote
    """
    start_time = time.time()
    
    try:
        # ✅ NUEVA: Verificar rate limit ANTES de hacer petición
        can_proceed, wait_time = self._check_rate_limit(endpoint_name)
        if not can_proceed:
            error_msg = f"Rate limit excedido para {endpoint_name}. Esperar {wait_time:.1f} segundos"
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="RATE_LIMITED",  # ✅ Nuevo status
                error_message=error_msg,
                duration_ms=duration_ms,
                batch_request=batch_request,  # ✅ Incluir batch_request
                caller_info=self._get_caller_info()
            )
            raise NubefactAPIError(error_msg)
        
        # ... validar y enviar ...
        
        # ✅ NUEVA: Actualizar rate limit después de petición exitosa
        self._update_rate_limit(endpoint_name)
        
        # Procesar respuesta con batch_request incluido
        return self._handle_response(response, endpoint_name, validated_data, start_time, batch_request)
```

**Beneficio:** Protección contra rate limiting, tracking de operaciones en batch.

---

### 5. Batch Request Support en send_request ✅

**Nuevos parámetros:**
```python
def send_request(self, endpoint: str, data: dict, method: str = "POST", 
                endpoint_name: str = None, batch_request=None) -> Dict[str, Any]:
    # ...
    self._log_api_call(
        # ...
        batch_request=batch_request,  # ✅ Nuevo parámetro
        # ...
    )
```

**USO PARA BATCH:**
```python
from api_service.models import ApiBatchRequest

# Crear batch request
batch = ApiBatchRequest.objects.create(
    service=service,
    description="Emisión de 100 comprobantes",
    total_items=100
)

# Usar en peticiones
with NubefactService() as service:
    # Primera petición del batch
    respuesta1 = service.send_request(
        endpoint="generar_comprobante",
        data=datos1,
        batch_request=batch  # ✅ Asociar al batch
    )
    
    # Segunda petición del batch
    respuesta2 = service.send_request(
        endpoint="generar_comprobante",
        data=datos2,
        batch_request=batch  # ✅ Misma instancia de batch
    )

# Todos los logs estarán asociados al batch
# Se puede consultar: batch.apicalllog_set.all()
```

**Beneficio:** Trazabilidad completa de operaciones en batch.

---

### 6. Mejorada _handle_response ✅

**Cambios:**
```python
def _handle_response(self, response: requests.Response, endpoint_name: str, 
                    request_data: dict, start_time: float, batch_request=None) -> Dict[str, Any]:
    """
    Procesa respuesta e incluye batch_request en logging.
    """
    # ... procesar respuesta ...
    
    # Registrar con batch_request
    self._log_api_call(
        endpoint_name=endpoint_name,
        request_data=request_data,
        response_data=response_data,
        status=status,
        error_message=error_message,
        duration_ms=duration_ms,
        batch_request=batch_request,  # ✅ Nuevo
        caller_info=self._get_caller_info()
    )
```

**Beneficio:** Todos los logs ahora incluyen info del batch si aplica.

---

## 📊 CAMBIOS RESUMIDOS

| Aspecto | Antes | Después | Beneficio |
|--------|-------|---------|-----------|
| Rate Limiting | ❌ No soportado | ✅ Integrado | Protección |
| Batch Requests | ❌ No soportado | ✅ Soportado | Trazabilidad |
| _log_api_call | ❌ Inconsistente | ✅ Alineado con Migo | Consistencia |
| Type Hints | ❌ batch_request sin tipo | ✅ ApiBatchRequest | Claridad |
| Status Codes | ❌ Solo SUCCESS/FAILED | ✅ +RATE_LIMITED | Mejor tracking |

---

## 🔄 EJEMPLO DE USO - FASE 2

### Caso 1: Petición Simple con Rate Limiting
```python
from api_service.services.nubefact.nubefact_service import NubefactService

with NubefactService() as service:
    try:
        # Automáticamente verifica rate limit
        respuesta = service.emitir_comprobante(datos)
        print(f"Comprobante emitido: {respuesta.get('enlace_comprobante')}")
    except NubefactAPIError as e:
        if "Rate limit" in str(e):
            print(f"Limite de peticiones excedido: {str(e)}")
        else:
            print(f"Error en API: {str(e)}")
```

### Caso 2: Batch de Comprobantes
```python
from api_service.models import ApiBatchRequest
from api_service.services.nubefact.nubefact_service import NubefactService

# Crear batch
batch = ApiBatchRequest.objects.create(
    service=ApiService.objects.get(service_type="NUBEFACT"),
    description="Batch de 50 comprobantes del mes de Enero",
    total_items=50
)

# Procesar con rate limiting
with NubefactService() as service:
    for i, datos in enumerate(comprobantes_list):
        try:
            # Cada petición respeta rate limit y se asocia al batch
            respuesta = service.send_request(
                endpoint="generar_comprobante",
                data=datos,
                endpoint_name=f"comprobante_{i+1}",
                batch_request=batch  # ✅ Asociar al batch
            )
            print(f"✅ {i+1}/50 completado")
        except NubefactAPIError as e:
            print(f"❌ {i+1}/50 falló: {str(e)}")
            batch.increment_failed_count()  # Si existe el método

# Consultar resultados del batch
logs = batch.apicalllog_set.all()
success_count = logs.filter(status="SUCCESS").count()
failed_count = logs.filter(status="FAILED").count()
print(f"Resultados: {success_count} exitosos, {failed_count} fallidos")
```

### Caso 3: Manejo de Rate Limit Manual
```python
from api_service.services.nubefact.nubefact_service import NubefactService
import time

service = NubefactService()

# Verificar rate limit manualmente
can_proceed, wait_time = service._check_rate_limit('emitir_comprobante')

if not can_proceed:
    print(f"Rate limit: esperar {wait_time:.1f} segundos")
    time.sleep(wait_time)
    can_proceed, _ = service._check_rate_limit('emitir_comprobante')

if can_proceed:
    respuesta = service.emitir_comprobante(datos)
```

---

## 📋 ARCHIVOS MODIFICADOS EN FASE 2

### Modificados:
1. ✅ [base_service.py](base_service.py)
   - Agregado imports: `Tuple, ApiRateLimit, ApiBatchRequest`
   - Agregado método `_check_rate_limit()`
   - Agregado método `_update_rate_limit()`
   - Mejorado `_log_api_call()` alineado con MigoAPIService

2. ✅ [nubefact_service.py](nubefact_service.py)
   - Actualizado `send_request()` con verificación de rate limit
   - Actualizado `send_request()` con soporte para batch_request
   - Actualizado `_handle_response()` para incluir batch_request

### SIN CAMBIOS:
- config.py
- validators.py
- schemas.py
- exceptions.py
- client.py
- operations.py

---

## ✅ VALIDACIÓN

### Checklist Fase 2
- ✅ Rate limiting integrado desde base_service.py
- ✅ ApiRateLimit importado y utilizado
- ✅ ApiBatchRequest importado y pasado correctamente
- ✅ Métodos _check_rate_limit y _update_rate_limit implementados
- ✅ _log_api_call alineado con MigoAPIService
- ✅ send_request maneja rate limiting
- ✅ send_request soporta batch_request
- ✅ _handle_response incluye batch_request

### Testing Recomendado
```python
# Test 1: Rate limiting no afecta en primer intento
service = NubefactService()
can_proceed, wait_time = service._check_rate_limit('emitir_comprobante')
assert can_proceed == True
assert wait_time == 0

# Test 2: Batch request se registra
from api_service.models import ApiBatchRequest
batch = ApiBatchRequest.objects.create(service=service.service, total_items=1)
# Hacer petición con batch
# Verificar que ApiCallLog.batch_request == batch

# Test 3: Rate limit se actualiza
initial_count = rate_limit.current_count
# Hacer petición exitosa
# Verificar que current_count aumentó
```

---

## 📊 IMPACTO FASE 2

### Protección de API
- ✅ Rate limiting previene abuso
- ✅ Tiempo de espera automático calculado
- ✅ Logging de excesos de límite

### Trazabilidad
- ✅ Operaciones en batch completamente trackables
- ✅ Cada petición asociada a su batch
- ✅ Reportes de éxito/fallo por batch

### Consistencia
- ✅ Mismo patrón que MigoAPIService
- ✅ Fácil mantenimiento futuro
- ✅ Menos duplicación de código

---

## 🚀 PRÓXIMAS FASES

### Fase 3: Async Support (⏳ Pendiente)
- [ ] Crear nubefact_service_async.py
- [ ] Migrar a httpx (async)
- [ ] Rate limiting async

### Fase 4: Testing (⏳ Pendiente)
- [ ] Tests de rate limiting
- [ ] Tests de batch requests
- [ ] Tests de error handling

### Fase 5: Documentación (⏳ Pendiente)
- [ ] Crear docs completa
- [ ] Ejemplos de uso

---

**Estado:** ✅ FASE 2 COMPLETADA
**Siguiente:** Fase 3 - Async Support
**Tiempo estimado fases restantes:** 3-4 horas
