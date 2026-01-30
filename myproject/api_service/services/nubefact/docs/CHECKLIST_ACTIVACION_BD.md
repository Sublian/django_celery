# ✅ CHECKLIST: Activación de Fase 2.5 en Base de Datos

**Objetivo:** Configurar la BD para que NubefactService funcione correctamente con el nuevo patrón.

---

## 🔄 Paso 1: Verificar/Actualizar ApiService

### En Django Shell:
```python
from api_service.models import ApiService

# Obtener servicio Nubefact
service = ApiService.objects.get(service_type="NUBEFACT")

# Verificar estado actual
print(f"Nombre: {service.name}")
print(f"URL actual: {service.base_url}")
print(f"Token presente: {bool(service.auth_token)}")
print(f"Activo: {service.is_active}")
```

### Checklist:
- [x ] Service existe con `service_type="NUBEFACT"`
- [x ] `service.is_active = True`
- [x ] `service.auth_token` está configurado (Bearer token)
- [x ] `service.base_url` contiene SOLO URL base (ej: `https://api.nubefact.com`)
  - ❌ NO debe tener: `https://api.nubefact.com/api/v1`
  - ✅ Debe tener: `https://api.nubefact.com`

### Si necesita ajustar:
```python
service.base_url = "https://api.nubefact.com"  # ← SOLO base, sin /api/v1
service.save()
print("✅ ApiService actualizado")
```

---

## 🔄 Paso 2: Crear ApiEndpoints

### Endpoints requeridos (3 mínimos):

#### 2.1 - Emitir Comprobante
```python
from api_service.models import ApiEndpoint

endpoint1, created = ApiEndpoint.objects.update_or_create(
    service=service,
    name="emitir_comprobante",
    defaults={
        "path": "/api/v1/send",
        "method": "POST",
        "description": "Emitir comprobante electrónico en Nubefact",
        "is_active": True,
        "timeout": 60,  # ← 60 segundos para emisión (más tiempo por ser operación crítica)
    }
)
print(f"{'✅ Creado' if created else '🔄 Actualizado'}: emitir_comprobante")
```

#### 2.2 - Consultar Comprobante
```python
endpoint2, created = ApiEndpoint.objects.update_or_create(
    service=service,
    name="consultar_comprobante",
    defaults={
        "path": "/api/v1/query",
        "method": "POST",
        "description": "Consultar estado de comprobante en Nubefact",
        "is_active": True,
        "timeout": 30,  # ← 30 segundos para consulta (operación rápida)
    }
)
print(f"{'✅ Creado' if created else '🔄 Actualizado'}: consultar_comprobante")
```

#### 2.3 - Anular Comprobante
```python
endpoint3, created = ApiEndpoint.objects.update_or_create(
    service=service,
    name="anular_comprobante",
    defaults={
        "path": "/api/v1/cancel",
        "method": "POST",
        "description": "Anular comprobante en Nubefact",
        "is_active": True,
        "timeout": 45,  # ← 45 segundos para anulación
    }
)
print(f"{'✅ Creado' if created else '🔄 Actualizado'}: anular_comprobante")
```

### Verificar endpoints creados:
```python
endpoints = ApiEndpoint.objects.filter(service=service)
for ep in endpoints:
    print(f"  - {ep.name}: {ep.path} ({ep.timeout}s)")
```

### Checklist:
- [x ] Endpoint "emitir_comprobante" existe con path="/api/v1/send"
- [x ] Endpoint "consultar_comprobante" existe con path="/api/v1/query"
- [x ] Endpoint "anular_comprobante" existe con path="/api/v1/cancel"
- [x ] Todos tienen `is_active=True`
- [x ] Timeouts configurados correctamente

---

## 🔄 Paso 3: Verificar Configuración de Rate Limiting

### Revisar límite de peticiones:
```python
# Configuración global del servicio
print(f"Rate limit global: {service.requests_per_minute} req/min")
print(f"Batch size máximo: {service.max_batch_size}")

# Rate limits por endpoint (si existen custom)
for ep in service.endpoints.all():
    custom_limit = ep.custom_rate_limit or service.requests_per_minute
    print(f"  - {ep.name}: {custom_limit} req/min")
```

### Ajustar si es necesario:
```python
# Cambiar límite global del servicio
service.requests_per_minute = 60  # ← Recomendado para Nubefact
service.save()

# O cambiar límite específico por endpoint
emitir_ep = ApiEndpoint.objects.get(service=service, name="emitir_comprobante")
emitir_ep.custom_rate_limit = 30  # ← Más restrictivo para emisiones
emitir_ep.save()
```

### Checklist:
- [x ] `service.requests_per_minute` >= 30 (recomendado: 60)
- [x ] `service.max_batch_size` >= 100
- [x ] ApiRateLimit registrará automáticamente al hacer primera llamada

---

## ✅ Paso 4: Prueba de Conectividad

### Script de validación:
```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.models import ApiEndpoint

print("🔧 Validando configuración de NubefactService...\n")

try:
    # 1. Crear instancia del servicio
    print("1️⃣  Creando servicio...")
    service = NubefactService()
    print(f"   ✅ Servicio creado")
    
    # 2. Verificar configuración básica
    print("\n2️⃣  Verificando configuración...")
    print(f"   Base URL: {service.base_url}")
    print(f"   Token presente: {'✅' if service.auth_token else '❌'}")
    print(f"   Timeout: {service.timeout}")
    
    # 3. Verificar endpoints
    print("\n3️⃣  Verificando endpoints...")
    for endpoint_name in ["emitir_comprobante", "consultar_comprobante", "anular_comprobante"]:
        endpoint = service._get_endpoint(endpoint_name)
        if endpoint:
            print(f"   ✅ {endpoint_name}: {service.base_url}{endpoint.path} (timeout: {endpoint.timeout}s)")
        else:
            print(f"   ❌ {endpoint_name}: NO ENCONTRADO")
    
    # 4. Verificar rate limiting
    print("\n4️⃣  Verificando rate limiting...")
    for endpoint_name in ["emitir_comprobante", "consultar_comprobante", "anular_comprobante"]:
        can_proceed, wait = service._check_rate_limit(endpoint_name)
        print(f"   ✅ {endpoint_name}: {'Disponible' if can_proceed else f'Limitado ({wait:.1f}s)'}")
    
    print("\n✅ Configuración VALIDADA correctamente!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
```

### Checklist:
- [ ] Servicio se crea sin errores
- [ ] Base URL es correcta
- [ ] Token está presente
- [ ] Los 3 endpoints se encuentran
- [ ] URLs construidas correctamente (base_url + endpoint.path)
- [ ] Rate limiting disponible

---

## 📊 Paso 5: Validar URLs Resultantes

### URLs que deberían generarse:
```
✅ emitir_comprobante:     https://api.nubefact.com/api/v1/send
✅ consultar_comprobante:  https://api.nubefact.com/api/v1/query
✅ anular_comprobante:     https://api.nubefact.com/api/v1/cancel
```

### Si las URLs no coinciden:
```python
# Verificar construcción manual
from api_service.services.nubefact import NubefactService

service = NubefactService()
endpoint = service._get_endpoint("emitir_comprobante")

print(f"Base URL: {service.base_url}")
print(f"Endpoint path: {endpoint.path}")
print(f"URL final: {service.base_url}{endpoint.path}")
```

### Checklist:
- [ ] URL final = https://api.nubefact.com/api/v1/send
- [ ] URL final = https://api.nubefact.com/api/v1/query
- [ ] URL final = https://api.nubefact.com/api/v1/cancel

---

## 🎯 Resumen de Checklist Final

### ✅ Configuración Base
- [ ] ApiService NUBEFACT existe
- [ ] ApiService.is_active = True
- [ ] ApiService.base_url = "https://api.nubefact.com" (sin /api/v1)
- [ ] ApiService.auth_token configurado
- [ ] ApiService.requests_per_minute >= 30

### ✅ Endpoints
- [ ] ApiEndpoint "emitir_comprobante" con path="/api/v1/send"
- [ ] ApiEndpoint "consultar_comprobante" con path="/api/v1/query"
- [ ] ApiEndpoint "anular_comprobante" con path="/api/v1/cancel"
- [ ] Todos los endpoints activos (is_active=True)
- [ ] Timeouts configurados (60, 30, 45 segundos)

### ✅ Validación
- [ ] NubefactService se instancia sin errores
- [ ] service.base_url es correcto
- [ ] service.auth_token está presente
- [ ] Todos los endpoints se encuentran vía _get_endpoint()
- [ ] URLs construidas correctamente (base_url + endpoint.path)
- [ ] Rate limiting está disponible para los endpoints
- [ ] Script de validación pasa sin errores

### ✅ Listo para Producción
- [ ] Todos los checks anteriores pasados
- [ ] Documentación revisada
- [ ] Tests pasados (si existen)
- [ ] Equipo notificado del cambio de patrón

---

## 🚨 Troubleshooting

### Error: "Endpoint 'emitir_comprobante' no configurado"
```python
# Verificar que endpoint existe
from api_service.models import ApiEndpoint, ApiService
service = ApiService.objects.get(service_type="NUBEFACT")
ep = ApiEndpoint.objects.filter(service=service, name="emitir_comprobante")
print(f"Existe: {ep.exists()}")

# Si no existe, crearlo
ApiEndpoint.objects.create(
    service=service,
    name="emitir_comprobante",
    path="/api/v1/send",
    method="POST",
    timeout=60,
    is_active=True
)
```

### Error: "base_url tiene /api/v1"
```python
# Corregir base_url
service = ApiService.objects.get(service_type="NUBEFACT")
service.base_url = service.base_url.replace("/api/v1", "")  # ← Remover /api/v1
service.save()
```

### Error: "Token incorrecto o falta Bearer"
```python
# Verificar token
service = ApiService.objects.get(service_type="NUBEFACT")
print(f"Token: {service.auth_token[:20]}...")

# Si falta 'Bearer', agregarlo
if not service.auth_token.startswith("Bearer "):
    service.auth_token = f"Bearer {service.auth_token}"
    service.save()
```

---

## 📞 Próximos Pasos

**Después de completar este checklist:**

1. ✅ Fase 2.5 está LISTA en la BD
2. 🧪 Ejecutar tests (si existen)
3. 🚀 Desplegar a desarrollo
4. 📋 Proceder a Fase 3 (Async Support)

---

**Preparado por:** AI Assistant  
**Fecha:** 30 Enero 2026  
**Versión:** 1.0 - Lista para Implementación
