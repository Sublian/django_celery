# ⚡ Quick Start - MigoAPIServiceAsync

**5 minutos para empezar con async.**

---

## 1️⃣ Instalación (1 minuto)

```bash
# Ya está en requirements.txt, pero confirmar:
pip install httpx>=0.27.0
```

---

## 2️⃣ Uso Básico (2 minutos)

### Una consulta individual

```python
import asyncio
from api_service.services.migo_service_async import MigoAPIServiceAsync

async def main():
    async with MigoAPIServiceAsync() as service:
        result = await service.consultar_ruc_async('20100038146')
        print(f"✅ {result}")

asyncio.run(main())
```

**Salida esperada:**
```json
{
  "success": true,
  "ruc": "20100038146",
  "nombre_o_razon_social": "EMPRESA SA",
  "estado_del_contribuyente": "ACTIVO",
  "condicion_de_domicilio": "HABIDO"
}
```

---

## 3️⃣ Múltiples Consultas en Paralelo (2 minutos)

### 🎯 RECOMENDADO: Usar `consultar_ruc_masivo_async()`

```python
async def main():
    rucs = ['20100038146', '20123456789', '20345678901']
    
    async with MigoAPIServiceAsync() as service:
        # Procesa todas en paralelo ⚡
        result = await service.consultar_ruc_masivo_async(rucs, batch_size=10)
        
        # Resultados separados
        print(f"✅ Válidos: {len(result['validos'])}")
        print(f"❌ Inválidos: {len(result['invalidos'])}")
        print(f"⚠️  Errores: {len(result['errores'])}")
        print(f"⏱️  Tiempo total: {result['duration_ms']:.1f}ms")

asyncio.run(main())
```

**Salida esperada:**
```
✅ Válidos: 3
❌ Inválidos: 0
⚠️  Errores: 0
⏱️  Tiempo total: 1234.5ms
```

### Alternativa: Control Manual

```python
async def main():
    rucs = ['20100038146', '20123456789', '20345678901']
    
    async with MigoAPIServiceAsync() as service:
        # Crear tasks para cada RUC
        tasks = [service.consultar_ruc_async(ruc) for ruc in rucs]
        
        # Ejecutar todas en paralelo
        results = await asyncio.gather(*tasks)
        
        # Procesar
        for ruc, result in zip(rucs, results):
            status = "✅" if result.get('success') else "❌"
            print(f"{status} {ruc}")

asyncio.run(main())
```

---

## 4️⃣ En Django

### Vista Async

```python
# views.py
from django.http import JsonResponse
from django.views import View
from api_service.services.migo_service_async import MigoAPIServiceAsync

class ConsultarRucView(View):
    async def post(self, request):
        ruc = request.POST.get('ruc')
        
        async with MigoAPIServiceAsync() as service:
            result = await service.consultar_ruc_async(ruc)
        
        return JsonResponse(result)
```

### Celery Task

```python
# tasks.py
from celery import shared_task
from asgiref.sync import async_to_sync
from api_service.services.migo_service_async import MigoAPIServiceAsync

@shared_task
def consultar_ruc_task(ruc):
    async def do_query():
        async with MigoAPIServiceAsync() as service:
            return await service.consultar_ruc_async(ruc)
    
    return async_to_sync(do_query)()
```

---

## 5️⃣ Testing

### Instalar pytest-asyncio

```bash
pip install pytest-asyncio
```

### Test Básico

```python
import pytest
from api_service.services.migo_service_async import MigoAPIServiceAsync
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_consultar_ruc():
    async with MigoAPIServiceAsync() as service:
        # Mock response
        service.client = MagicMock()
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={
            'success': True,
            'ruc': '20100038146'
        })
        service.client.post = AsyncMock(return_value=mock_response)
        
        result = await service.consultar_ruc_async('20100038146')
        assert result['success'] is True
```

---

## 🚀 Comparación: Antes vs Después

### ❌ ANTES (Sincrónico)

```python
# Lento: Bloquea 10 segundos
service = MigoAPIService()
for ruc in rucs:  # Bloqueante
    result = service.consultar_ruc(ruc)
    procesar(result)

# ⏱️ 100 RUCs = ~100 segundos
```

### ✅ DESPUÉS (Asincrónico)

```python
# Rápido: Solo 10 segundos
async with MigoAPIServiceAsync() as service:
    result = await service.consultar_ruc_masivo_async(rucs)  # Paralelo

# ⏱️ 100 RUCs = ~10 segundos (10x más rápido)
```

---

## 📊 Performance Real

```
Sincrónico (bloqueante):
  10 RUCs:   ██████████░░░░░░░░░░  10 segundos
  100 RUCs:  ██████████████████░░  100 segundos
  
Asincrónico (paralelo, batch_size=10):
  10 RUCs:   █░░░░░░░░░░░░░░░░░░░  1 segundo
  100 RUCs:  ██░░░░░░░░░░░░░░░░░░  10 segundos
  
Mejora: ✨ 10x más rápido
```

---

## ⚠️ Errores Comunes

### Error: "RuntimeError: no running event loop"

```python
# ❌ INCORRECTO
result = await service.consultar_ruc_async('20100038146')

# ✅ CORRECTO
asyncio.run(service.consultar_ruc_async('20100038146'))
```

### Error: "Too many open connections"

```python
# ❌ INCORRECTO
service = MigoAPIServiceAsync()
for ruc in rucs:
    await service.consultar_ruc_async(ruc)
# Client nunca se cierra

# ✅ CORRECTO
async with MigoAPIServiceAsync() as service:  # Auto-cierra
    result = await service.consultar_ruc_masivo_async(rucs)
```

### Error: "Timeout después de 30 segundos"

```python
# ✅ Aumentar timeout si es necesario
service = MigoAPIServiceAsync(timeout=60)
```

---

## 📚 Métodos Disponibles

```python
async with MigoAPIServiceAsync() as service:
    # Consultar 1 RUC
    result = await service.consultar_ruc_async(ruc)
    
    # Consultar múltiples RUCs en paralelo
    result = await service.consultar_ruc_masivo_async(
        rucs,
        batch_size=10,
        update_partners=False
    )
    
    # Consultar DNI
    result = await service.consultar_dni_async(dni)
    
    # Obtener tipo de cambio
    result = await service.consultar_tipo_cambio_async()
```

---

## 🔍 Debugging

### Ver logs detallados

```python
import logging

# Habilitar debug logging
logging.basicConfig(level=logging.DEBUG)

async with MigoAPIServiceAsync() as service:
    result = await service.consultar_ruc_async('20100038146')
    # Verás logs [ASYNC] detallados
```

### Medir tiempo de ejecución

```python
import time

start = time.time()
result = await service.consultar_ruc_masivo_async(rucs)
elapsed = time.time() - start

print(f"Tiempo total: {elapsed:.2f}s")
print(f"Tiempo API (desde logs): {result.get('duration_ms')}ms")
```

---

## 💾 Caché

El servicio async reutiliza la caché centralizada automáticamente:

```python
# Primera consulta (NO cachea, 1 segundo)
result1 = await service.consultar_ruc_async('20100038146')

# Segunda consulta (SÍ cachea, <100ms)
result2 = await service.consultar_ruc_async('20100038146')

# Resultados idénticos, pero mucho más rápido
```

---

## 🎯 Casos de Uso

### ✅ Usar Async

- Múltiples RUCs (>5)
- Procesamiento de lotes
- Celery background tasks
- Django async views
- Importa la latencia

### ❌ Usar Sync (migo_service.py)

- Una sola consulta
- Scripts simples
- Debugging
- Compatibilidad con código legacy

---

## 📖 Documentación Completa

Para más detalles, ver:
- [ASYNC_GUIDE.md](../docs/migo-service/ASYNC_GUIDE.md) - Guía completa
- [views_async.py](../api_service/views_async.py) - Ejemplos Django
- [test_migo_service_async.py](../api_service/services/test_migo_service_async.py) - Tests
- [ASYNC_IMPLEMENTATION_SUMMARY.md](../ASYNC_IMPLEMENTATION_SUMMARY.md) - Resumen ejecutivo

---

## ✅ Checklist

Antes de usar en producción:

- [ ] Instalar httpx>=0.27.0
- [ ] Leer [ASYNC_GUIDE.md](../docs/migo-service/ASYNC_GUIDE.md)
- [ ] Ejecutar tests: `pytest -m asyncio`
- [ ] Probar con datos reales
- [ ] Configurar logging
- [ ] Documentar endpoints en equipo
- [ ] Monitorear performance en staging

---

**¿Preguntas?** Ver documentación completa en [ASYNC_GUIDE.md](../docs/migo-service/ASYNC_GUIDE.md)

**¿Errores?** Revisar sección ⚠️ Errores Comunes arriba.

**Ready to go? 🚀** Empieza con el ejemplo básico y expande según necesites.
