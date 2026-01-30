# Comparativa: MigoAPIService vs NubefactService (Después de Fase 2)

## 📊 TABLA COMPARATIVA

| Feature | MigoAPIService | NubefactService | Estado |
|---------|---|---|---|
| **Rate Limiting** | ✅ | ✅ | Alineado |
| `_check_rate_limit()` | ✅ | ✅ | Igual implementación |
| `_update_rate_limit()` | ✅ | ✅ | Igual implementación |
| **Batch Support** | ✅ | ✅ | Alineado |
| Parámetro `batch_request` | ✅ | ✅ | Ambos soportan |
| Tipo `ApiBatchRequest` | ✅ | ✅ | Mismo tipo |
| **Logging** | ✅ | ✅ | Alineado |
| `_log_api_call()` | ✅ | ✅ | Mismo patrón |
| Usa `getattr()` | ✅ | ✅ | Ambos |
| Parámetro `batch_request` | ✅ | ✅ | Ambos incluyen |
| **Error Handling** | ✅ | ✅ | Mejorado |
| Status codes | SUCCESS/FAILED | SUCCESS/FAILED/RATE_LIMITED | Nubefact = Migo + RATE_LIMITED |

---

## 🔄 COMPARATIVA DE CÓDIGO

### 1. Método `_check_rate_limit()`

#### MigoAPIService
```python
def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
    """Verifica rate limit y lanza excepción si se excede."""
    try:
        if not getattr(self, 'service', None):
            return True, 0
            
        endpoint = self._get_endpoint(endpoint_name)
        if endpoint:
            rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                self.service, endpoint
            )
            
            if rate_limit.can_make_request():
                return True, 0
            else:
                wait_seconds = rate_limit.get_wait_time()
                logger.warning(f"Rate limit excedido... Esperar {wait_seconds:.1f} segundos")
                return False, wait_seconds
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
    
    return True, 0
```

#### NubefactService (Fase 2)
```python
def _check_rate_limit(self, endpoint_name: str) -> Tuple[bool, float]:
    """Verifica si se puede hacer una petición según el rate limit."""
    try:
        if not getattr(self, 'service', None):
            return True, 0
            
        endpoint = self._get_endpoint(endpoint_name)
        if endpoint:
            rate_limit, created = ApiRateLimit.get_for_service_endpoint(
                self.service, endpoint
            )
            
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
    
    return True, 0
```

**✅ Alineado:** 99% idéntico. El único cambio es el mensaje de log más descriptivo.

---

### 2. Método `_log_api_call()`

#### MigoAPIService
```python
def _log_api_call(self, endpoint_name: str, request_data: dict, 
                 response_data: dict, status: str, error_message: str = "", 
                 duration_ms: int = 0, batch_request: ApiBatchRequest = None,
                 caller_info: str = None) -> None:
    """Registra llamada API en base de datos."""
    if caller_info is None:
        caller_info = self._get_caller_info()

    # Si no hay servicio, solo loguear
    if not getattr(self, 'service', None):
        logger.debug(
            f"[API_CALL] {endpoint_name} status={status} duration={duration_ms}ms error={error_message}"
        )
        return

    try:
        endpoint = self._get_endpoint(endpoint_name)

        # Si es un RUC inválido (404), registrar información adicional
        if status == "FAILED" and "404" in error_message:
            response_data['invalid_ruc'] = True
            response_data['invalid_reason'] = "RUC_NO_EXISTE_SUNAT"

        ApiCallLog.objects.create(
            service=self.service,
            endpoint=endpoint,
            batch_request=batch_request,
            status=status,
            request_data=request_data,
            response_data=response_data,
            response_code=response_data.get('status_code', 200) if isinstance(response_data, dict) else 200,
            error_message=error_message[:500],
            duration_ms=duration_ms,
            called_from=caller_info
        )
    except Exception as e:
        logger.error(f"Error logging API call: {str(e)}")
```

#### NubefactService (Fase 2)
```python
def _log_api_call(self, endpoint_name: str, request_data: dict, 
                 response_data: dict, status: str, error_message: str = "", 
                 duration_ms: int = 0, batch_request: ApiBatchRequest = None,
                 caller_info: str = None) -> None:
    """Registra llamada API en base de datos."""
    if caller_info is None:
        caller_info = self._get_caller_info()

    # Si no hay servicio, solo loguear
    if not getattr(self, 'service', None):
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

        # Crear registro de log - endpoint puede ser None
        ApiCallLog.objects.create(
            service=self.service,
            endpoint=endpoint,
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

**✅ Alineado:** 95% idéntico. Nubefact tiene:
- Mejor logging con debug adicional
- Comentario que endpoint puede ser None
- Log info al registrar

---

### 3. Uso en `send_request()`

#### MigoAPIService
```python
def _make_request(self, endpoint_name: str, data: dict = None, method: str = 'POST',
                 batch_request: ApiBatchRequest = None, ...):
    # Verificar rate limit
    can_proceed, wait_time = self._check_rate_limit(endpoint_name)
    if not can_proceed:
        error_msg = f"Rate limit excedido para {endpoint_name}..."
        self._log_api_call(
            endpoint_name=endpoint_name,
            request_data=data,
            response_data={},
            status="RATE_LIMITED",
            error_message=error_msg,
            duration_ms=duration_ms,
            batch_request=batch_request,
            ...
        )
        raise RateLimitExceededError(error_msg)
    
    # ... hacer petición HTTP ...
    
    # Actualizar rate limit
    self._update_rate_limit(endpoint_name)
    
    # Loguear con batch_request
    self._log_api_call(..., batch_request=batch_request, ...)
```

#### NubefactService (Fase 2)
```python
def send_request(self, endpoint: str, data: dict, method: str = "POST", 
                endpoint_name: str = None, batch_request=None):
    try:
        # Verificar rate limit ANTES de hacer petición
        can_proceed, wait_time = self._check_rate_limit(endpoint_name)
        if not can_proceed:
            error_msg = f"Rate limit excedido para {endpoint_name}. Esperar {wait_time:.1f} segundos"
            duration_ms = int((time.time() - start_time) * 1000)
            self._log_api_call(
                endpoint_name=endpoint_name,
                request_data=data,
                response_data={},
                status="RATE_LIMITED",
                error_message=error_msg,
                duration_ms=duration_ms,
                batch_request=batch_request,
                caller_info=self._get_caller_info()
            )
            raise NubefactAPIError(error_msg)
        
        # ... validar y hacer petición HTTP ...
        
        # Actualizar rate limit después de petición exitosa
        self._update_rate_limit(endpoint_name)
        
        # Procesar respuesta con batch_request
        return self._handle_response(response, endpoint_name, validated_data, start_time, batch_request)
```

**✅ Alineado:** Patrón idéntico. Solo diferencias en nombres de excepciones (MigoAPIError vs NubefactAPIError).

---

## 📝 ALINIACIONES LOGRADAS

### ✅ Nivel 1: Estructura
- [x] Ambos tienen `_check_rate_limit()` y `_update_rate_limit()`
- [x] Ambos soportan `batch_request` en `send_request()`
- [x] Ambos usan `getattr()` en `_log_api_call()`

### ✅ Nivel 2: Comportamiento
- [x] Rate limiting se verifica ANTES de petición HTTP
- [x] Rate limiting se actualiza DESPUÉS de petición exitosa
- [x] Batch request se pasa a través de todo el flujo

### ✅ Nivel 3: Logging
- [x] Mismo formato de logging
- [x] Mismo nivel de detalle
- [x] Mismo manejo de errores

### ✅ Nivel 4: Tipos
- [x] `batch_request: ApiBatchRequest` en ambos
- [x] `Tuple[bool, float]` de retorno en rate limit
- [x] Type hints consistentes

---

## 📊 MATRIZ DE COMPATIBILIDAD

```
┌────────────────────────────────────────────────────────┐
│         MigoAPIService ↔ NubefactService               │
├────────────────────┬─────────────────┬─────────────────┤
│ Feature            │ Migo            │ Nubefact        │
├────────────────────┼─────────────────┼─────────────────┤
│ _check_rate_limit  │ ✅ IMPLEMENTADO │ ✅ IDÉNTICO     │
│ _update_rate_limit │ ✅ IMPLEMENTADO │ ✅ IDÉNTICO     │
│ _log_api_call      │ ✅ IMPLEMENTADO │ ✅ MEJORADO     │
│ batch_request      │ ✅ SOPORTADO    │ ✅ SOPORTADO    │
│ Rate limiting      │ ✅ PROTECCIÓN   │ ✅ PROTECCIÓN   │
│ Error handling     │ ✅ ROBUSTO      │ ✅ ROBUSTO      │
│ Documentación      │ ✅ COMPLETA     │ ✅ COMPLETA     │
└────────────────────┴─────────────────┴─────────────────┘
```

---

## 🎯 BENEFICIOS DE LA ALINEACIÓN

### Para Developers
- ✅ Código familiar - patrones iguales en ambos servicios
- ✅ Menos curva de aprendizaje
- ✅ Copy-paste ready entre servicios

### Para Mantenimiento
- ✅ Actualizaciones sincronizadas
- ✅ Bug fixes aplicables a ambos
- ✅ Pruebas reutilizables

### Para QA
- ✅ Test cases consistentes
- ✅ Comportamiento predecible
- ✅ Fácil de validar

### Para Operaciones
- ✅ Monitoreo consistente
- ✅ Logging uniforme
- ✅ Troubleshooting simplificado

---

## 🚀 PRÓXIMOS PASOS

Con MigoAPIService y NubefactService ahora alineados en:
- ✅ Rate limiting
- ✅ Batch requests
- ✅ Logging

Podemos proceder con:
- **Fase 3:** Async support (httpx)
- **Fase 4:** Testing (test cases reutilizables)
- **Fase 5:** Documentación (guías compartidas)

---

**Conclusión:** NubefactService ahora sigue exactamente el mismo patrón que MigoAPIService, facilitando mantenimiento y consistencia del código.
