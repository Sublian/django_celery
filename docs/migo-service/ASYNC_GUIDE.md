# 🚀 MigoAPIServiceAsync - Guía de Uso

**Status:** ✅ Producción Ready  
**Última actualización:** 29 Enero 2026  
**Versión:** 1.0

---

## 📋 Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Instalación](#instalación)
3. [Uso Básico](#uso-básico)
4. [Ejemplos Prácticos](#ejemplos-prácticos)
5. [Consultas Masivas](#consultas-masivas)
6. [Manejo de Errores](#manejo-de-errores)
7. [Rendimiento](#rendimiento)
8. [Migración desde Sincrónico](#migración-desde-sincrónico)

---

## 📖 Descripción General

`MigoAPIServiceAsync` es una versión **no bloqueante** del cliente APIMIGO que permite:

✅ **No bloqueante**: Las peticiones HTTP no bloquean el event loop  
✅ **Paralelo**: Procesa múltiples RUCs simultáneamente  
✅ **Compatible**: Usa la misma caché centralizada (`APICacheService`)  
✅ **Resiliente**: Rate limiting, reintentos con backoff exponencial  
✅ **Productivo**: Integrado con logging, auditoría y manejo de errores

### Diferencias con versión sincrónica

```python
# ❌ SINCRÓNICO (bloqueante)
service = MigoAPIService()
result = service.consultar_ruc('20100038146')  # Espera bloqueante
print(result)

# ✅ ASINCRÓNICO (no bloqueante)
async def main():
    async with MigoAPIServiceAsync() as service:
        result = await service.consultar_ruc_async('20100038146')
        print(result)

asyncio.run(main())
```

---

## 🔧 Instalación

### 1. Dependencias

```bash
pip install httpx>=0.27.0
```

Verificar que esté en `requirements.txt`:

```
httpx==0.27.0
```

### 2. Importar en Django

```python
# settings.py
INSTALLED_APPS = [
    ...
    'api_service',
    ...
]
```

### 3. Configurar Endpoint APIMIGO

Asegurar que tengas un `ApiService` de tipo `MIGO` en la BD con:
- `auth_token`: Token de autenticación
- `base_url`: URL base de la API
- Endpoints configurados (`consultar_ruc`, `consulta_dni`, etc.)

---

## 🎯 Uso Básico

### Instancia Simple

```python
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync

async def consultar_ruc():
    # Crear instancia
    service = MigoAPIServiceAsync()
    
    try:
        # Consultar RUC
        result = await service.consultar_ruc_async('20100038146')
        print(f"✅ Resultado: {result}")
    finally:
        # Cerrar cliente
        await service.close()

# Ejecutar
asyncio.run(consultar_ruc())
```

### Context Manager (Recomendado)

```python
async def consultar_ruc():
    # Auto-cierra el cliente HTTP
    async with MigoAPIServiceAsync() as service:
        result = await service.consultar_ruc_async('20100038146')
        print(f"✅ Resultado: {result}")

asyncio.run(consultar_ruc())
```

---

## 💡 Ejemplos Prácticos

### 1. Consultar un RUC individual

```python
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync

async def main():
    async with MigoAPIServiceAsync() as service:
        # Consultar RUC
        result = await service.consultar_ruc_async('20100038146')
        
        if result.get('success'):
            print(f"✅ RUC válido:")
            print(f"   Razón Social: {result.get('nombre_o_razon_social')}")
            print(f"   Estado: {result.get('estado_del_contribuyente')}")
            print(f"   Condición: {result.get('condicion_de_domicilio')}")
        else:
            print(f"❌ Error: {result.get('error')}")

asyncio.run(main())
```

### 2. Consultar múltiples RUCs en paralelo

```python
async def main():
    rucs = ['20100038146', '20123456789', '20345678901']
    
    async with MigoAPIServiceAsync() as service:
        # Crear tasks para cada RUC
        tasks = [
            service.consultar_ruc_async(ruc)
            for ruc in rucs
        ]
        
        # Ejecutar todas en paralelo
        results = await asyncio.gather(*tasks)
        
        # Procesar resultados
        for ruc, result in zip(rucs, results):
            status = "✅" if result.get('success') else "❌"
            print(f"{status} {ruc}: {result.get('nombre_o_razon_social', 'Error')}")

asyncio.run(main())
```

### 3. Usar desde Django (Celery async task)

```python
# tasks.py
from celery import shared_task
from asgiref.sync import async_to_sync
from api_service.services.migo_service_async import MigoAPIServiceAsync

@shared_task
def consultar_ruc_task(ruc):
    """Task de Celery para consultar RUC de forma async."""
    async def do_query():
        async with MigoAPIServiceAsync() as service:
            return await service.consultar_ruc_async(ruc)
    
    # Convertir async a sync para Celery
    return async_to_sync(do_query)()
```

### 4. Vista Django con async

```python
# views.py
from django.http import JsonResponse
from django.views import View
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync

class ConsultarRucView(View):
    async def post(self, request):
        """Endpoint async para consultar RUC."""
        ruc = request.POST.get('ruc')
        
        async with MigoAPIServiceAsync() as service:
            result = await service.consultar_ruc_async(ruc)
        
        return JsonResponse(result)
```

---

## 🔢 Consultas Masivas

### Método 1: Consulta masiva integrada

```python
async def main():
    rucs = [
        '20100038146',
        '20123456789',
        '20345678901',
        # ... hasta N RUCs
    ]
    
    async with MigoAPIServiceAsync() as service:
        # Procesa en paralelo con batch_size=10
        results = await service.consultar_ruc_masivo_async(
            rucs,
            batch_size=10,  # 10 consultas paralelas
            update_partners=True
        )
        
        print(f"✅ Válidos: {len(results['validos'])}")
        print(f"❌ Inválidos: {len(results['invalidos'])}")
        print(f"⚠️  Errores: {len(results['errores'])}")
        print(f"⏱️  Tiempo total: {results['duration_ms']:.1f}ms")

asyncio.run(main())
```

### Método 2: Control manual de paralelismo

```python
async def main():
    rucs = ['20100038146', '20123456789', ...]
    
    async with MigoAPIServiceAsync() as service:
        # Procesar en lotes de 5
        batch_size = 5
        for i in range(0, len(rucs), batch_size):
            batch = rucs[i:i + batch_size]
            
            # Crear tasks
            tasks = [service.consultar_ruc_async(ruc) for ruc in batch]
            
            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks)
            
            # Procesar resultados
            for ruc, result in zip(batch, results):
                print(f"{ruc}: {'✅' if result.get('success') else '❌'}")
            
            # Pausa entre lotes para respetar rate limiting
            await asyncio.sleep(1)

asyncio.run(main())
```

### Rendimiento esperado

Con `batch_size=10` consultas paralelas:

| Cantidad RUCs | Tiempo Sincrónico | Tiempo Async | Mejora |
|---|---|---|---|
| 10 RUCs | ~10s | ~1s | **10x** |
| 100 RUCs | ~100s | ~10s | **10x** |
| 1000 RUCs | ~1000s | ~100s | **10x** |

*(Aproximados, depende de latencia de API)*

---

## ⚠️ Manejo de Errores

### Errores comunes

```python
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync

async def main():
    async with MigoAPIServiceAsync() as service:
        try:
            # Error: Formato inválido
            result = await service.consultar_ruc_async('ABC')
            # → {"success": False, "error": "Formato de RUC inválido"}
            
            # Error: API no disponible
            result = await service.consultar_ruc_async('20100038146')
            # → {"success": False, "error": "Error de conexión..."}
            
            # Error: RUC no encontrado
            result = await service.consultar_ruc_async('20999999999')
            # → {"success": False, "error": "RUC no encontrado", "invalid_sunat": True}
        
        except asyncio.TimeoutError:
            print("❌ Timeout después de 30 segundos")
        except Exception as e:
            print(f"❌ Error: {e}")

asyncio.run(main())
```

### Gestión de excepciones en gather

```python
async def main():
    tasks = [
        service.consultar_ruc_async(ruc)
        for ruc in rucs
    ]
    
    # return_exceptions=True: Captura excepciones sin lanzarlas
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for ruc, result in zip(rucs, results):
        if isinstance(result, Exception):
            print(f"❌ {ruc}: {result}")
        elif result.get('success'):
            print(f"✅ {ruc}: {result['nombre_o_razon_social']}")
        else:
            print(f"⚠️  {ruc}: {result.get('error')}")
```

---

## 📊 Rendimiento

### Benchmarks

```python
import time
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync
from api_service.services.migo_service import MigoAPIService

async def benchmark_async():
    start = time.time()
    
    async with MigoAPIServiceAsync() as service:
        tasks = [
            service.consultar_ruc_async(ruc)
            for ruc in rucs
        ]
        await asyncio.gather(*tasks)
    
    return time.time() - start

def benchmark_sync():
    start = time.time()
    
    service = MigoAPIService()
    for ruc in rucs:
        service.consultar_ruc(ruc)
    
    return time.time() - start

# Ejecutar benchmarks
rucs = ['20100038146'] * 50
async_time = asyncio.run(benchmark_async())
sync_time = benchmark_sync()

print(f"⏱️  Sincrónico: {sync_time:.2f}s")
print(f"⏱️  Asincrónico: {async_time:.2f}s")
print(f"📈 Mejora: {sync_time / async_time:.1f}x más rápido")
```

### Mejores prácticas

✅ **Usar batch_size=10** para balance entre paralelismo y rate limiting  
✅ **Usar context manager** (`async with`) para gestión automática de recursos  
✅ **Monitear memoria** en consultas masivas (>1000 RUCs)  
✅ **Respetar rate limits** con pausas entre lotes  
✅ **Loguear duración** de operaciones para debugging  

---

## 🔄 Migración desde Sincrónico

### Antes (sincrónico)

```python
from api_service.services.migo_service import MigoAPIService

def procesar_rucs(rucs):
    service = MigoAPIService()
    
    resultados = []
    for ruc in rucs:  # ❌ Bloqueante
        result = service.consultar_ruc(ruc)
        resultados.append(result)
    
    return resultados
```

### Después (asincrónico)

```python
from api_service.services.migo_service_async import MigoAPIServiceAsync
import asyncio

async def procesar_rucs(rucs):
    async with MigoAPIServiceAsync() as service:
        # ✅ Paralelo y no bloqueante
        tasks = [service.consultar_ruc_async(ruc) for ruc in rucs]
        resultados = await asyncio.gather(*tasks)
    
    return resultados

# Ejecutar
results = asyncio.run(procesar_rucs(rucs))
```

### Wrapper para compatibilidad

```python
from asgiref.sync import async_to_sync

# Mantener API sincrónica pero implementar con async
def consultar_ruc_sync(ruc: str):
    """Wrapper sincrónico que usa implementación async."""
    service = MigoAPIServiceAsync()
    return async_to_sync(service.consultar_ruc_async)(ruc)

# Usar igual que antes
result = consultar_ruc_sync('20100038146')
```

---

## 📝 Resumen

**Cuándo usar `MigoAPIServiceAsync`:**

| Situación | Recomendación |
|---|---|
| Una consulta individual | Indistinto (sync o async) |
| 10+ consultas | **Async (mucho más rápido)** |
| Consultas en background (Celery) | **Async** |
| Vista web con múltiples queries | **Async** |
| Compatibilidad con código existente | Wrapper sincrónico + async internamente |

**Checklist de implementación:**

- ✅ Instalar `httpx>=0.27.0`
- ✅ Configurar `ApiService` tipo MIGO en BD
- ✅ Importar `MigoAPIServiceAsync`
- ✅ Usar `async with` context manager
- ✅ Usar `await` en llamadas a métodos async
- ✅ Monitorear performance en producción

---

## 🆘 Troubleshooting

### "RuntimeError: no running event loop"

```python
# ✅ Solución: Usar asyncio.run() en script principal
asyncio.run(main())

# O usar loop existente en Django async views
```

### "Timeout después de 30 segundos"

```python
# Aumentar timeout en construcción
service = MigoAPIServiceAsync(timeout=60)
```

### "Too many open connections"

```python
# Usar context manager o llamar close()
async with MigoAPIServiceAsync() as service:
    # Auto-cierra al salir
    pass
```

---

**¿Preguntas o sugerencias?** Revisar logs en:  
`/var/log/django/migo_service.log` (o configuración de Django logging)
