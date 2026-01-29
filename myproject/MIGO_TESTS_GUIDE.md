# 🧪 MigoAPIService - Guía de Uso de Tests

## Antes de Empezar

Los tests requieren:
- ✅ Django configurado (ya está via conftest.py)
- ✅ Database accesible
- ✅ ApiService "MIGO" en BD (se auto-crea si no existe)

---

## 📌 Ejecución Básica

### Ver todos los tests disponibles
```bash
pytest api_service/services/test_migo_service.py --co -q
```

**Output:**
```
myproject/api_service/services/test_migo_service.py::test_migo_service_initialization
myproject/api_service/services/test_migo_service.py::test_migo_service_database_config
myproject/api_service/services/test_migo_service.py::test_migo_validate_ruc_format
myproject/api_service/services/test_migo_service.py::test_migo_consultar_ruc_individual
... (18 total)
```

---

## ✅ Ejecutar Solo Tests Exitosos

```bash
pytest api_service/services/test_migo_service.py \
    -v \
    -k "not (tipo_cambio or representantes or complete_workflow)"
```

**Output esperado:**
```
collected 18 items / 5 deselected / 13 selected

✅ test_migo_service_initialization                           PASSED [  6%]
✅ test_migo_service_database_config                          PASSED [ 12%]
✅ test_migo_validate_ruc_format                              PASSED [ 18%]
✅ test_migo_consultar_ruc_individual                         PASSED [ 25%]
✅ test_migo_consultar_dni                                    PASSED [ 31%]
✅ test_migo_consultar_ruc_masivo_pequeño                     PASSED [ 37%]
✅ test_migo_consultar_ruc_masivo_completo                    PASSED [ 43%]
✅ test_migo_validar_ruc_facturacion                          PASSED [ 50%]
✅ test_migo_validar_rucs_masivo_facturacion                  PASSED [ 56%]
✅ test_migo_invalid_rucs_cache                               PASSED [ 62%]
✅ test_migo_rate_limiting                                    PASSED [ 68%]
✅ test_migo_api_call_logging                                 PASSED [ 75%]
✅ test_print_summary                                         PASSED [ 81%]

======================= 13 passed in 4.2s =======================
```

---

## 🔍 Test Individual con Output Verboso

### Test 1: Inicialización
```bash
pytest api_service/services/test_migo_service.py::test_migo_service_initialization -v -s
```

**Output:**
```
api_service\services\test_migo_service.py::test_migo_service_initialization

======================================================================
✓ TEST 1: Inicialización de MigoAPIService
======================================================================

  ✅ MigoAPIService instanciado correctamente
     Token: GLxGAQ92hQ...
     Base URL: https://api.migo.pe

  ✅ Instancia creada
  ✅ Token: GLxGAQ92hQIxusj...***
  ✅ Base URL: https://api.migo.pe
  ✅ Cache service disponible
  ✅ Constante INVALID_RUCS_CACHE_KEY definida
  ✅ TTL para RUCs inválidos: 24 horas

  Status: ✅ INICIALIZACIÓN OK

PASSED                                                              [100%]
```

---

### Test 3: Validación de RUC
```bash
pytest api_service/services/test_migo_service.py::test_migo_validate_ruc_format -v -s
```

**Output:**
```
======================================================================
✓ TEST 3: Validación de Formato de RUC
======================================================================

  ✅ RUC válido (20100038146): ACEPTADO
  ✅ RUC corto (201): RECHAZADO - RUC debe tener 11 dígitos, tiene 3
  ✅ RUC con letras (201000ABC46): RECHAZADO - RUC debe contener solo dígitos
  ✅ RUC vacío: RECHAZADO - RUC vacío
  ✅ Patrón sospechoso (11111111111): RECHAZADO - RUC con patrón inválido (todos dígitos iguales)

  Status: ✅ VALIDACIÓN FORMATO OK

PASSED                                                              [100%]
```

---

### Test 10: Consulta Masiva
```bash
pytest api_service/services/test_migo_service.py::test_migo_consultar_ruc_masivo_pequeño -v -s
```

**Output:**
```
======================================================================
✓ TEST 10: Consulta Masiva - Lote Pequeño
======================================================================

  📋 Consultando 3 RUCs en lote
  ----------------------------------------------------------
  RUCs a consultar:
    - 20100038146
    - 20000000001
    - 20123456789

  📊 Resultados de consulta masiva:
    - Total solicitados: 3
    - Únicos: 3
    - Válidos: 1
    - Inválidos: 2
    - Errores: 0
    - Hits cache: 0
    - Llamadas API: 1
    - Lotes procesados: 1

  Status: ✅ CONSULTA MASIVA PEQUEÑO OK

PASSED                                                              [100%]
```

---

### Test 12: Validación para Facturación
```bash
pytest api_service/services/test_migo_service.py::test_migo_validar_ruc_facturacion -v -s
```

**Output:**
```
======================================================================
✓ TEST 12: Validación para Facturación
======================================================================

  📋 Validando RUC 20100038146 para facturación
  ----------------------------------------------------------

  📊 Resultado de validación:
    - Válido para facturación: True
    - RUC: 20100038146
    - Razón Social: CONTINENTAL S.A.C.
    - Estado: ACTIVO
    - Condición: HABIDO
    - Dirección: JIRÓN RIO DE JANEIRO NRO 342 PISO 4 URB....

  Status: ✅ VALIDACIÓN FACTURACIÓN OK

PASSED                                                              [100%]
```

---

### Test 14: Cache de Inválidos
```bash
pytest api_service/services/test_migo_service.py::test_migo_invalid_rucs_cache -v -s
```

**Output:**
```
======================================================================
✓ TEST 14: Cache de RUCs Inválidos
======================================================================

  📋 Paso 1: Marcar RUC como inválido
  ----------------------------------------------------------
  ✅ RUC 20999999999 marcado como inválido
     Razón: NO_EXISTE_SUNAT

  📋 Paso 2: Verificar si está marcado como inválido
  ----------------------------------------------------------
  ✅ Verificación exitosa: RUC está marcado como inválido

  📋 Paso 3: Obtener reporte de inválidos
  ----------------------------------------------------------
  📊 Reporte:
    - Total inválidos en cache: 1
    - RUCs inválidos:
      * RUC: 20999999999
        Razón: NO_EXISTE_SUNAT
        TTL: 24 horas

  📋 Paso 4: Limpiar cache de un RUC específico
  ----------------------------------------------------------
  ✅ Cache limpiado para RUC 20999999999

  Status: ✅ CACHE INVÁLIDOS OK

PASSED                                                              [100%]
```

---

## 🎯 Patrones de Ejecución Comunes

### Para Debugging
```bash
# Un test con mucho detalle
pytest api_service/services/test_migo_service.py::test_migo_validate_ruc_format -vvs

# Ver exactamente qué se imprime
pytest api_service/services/test_migo_service.py::test_migo_validate_ruc_format -s --capture=no
```

### Para Verificación Rápida
```bash
# Sin output verboso
pytest api_service/services/test_migo_service.py -q

# Solo mostrar resultados finales
pytest api_service/services/test_migo_service.py --tb=no
```

### Para Documentación
```bash
# Ver docstrings de tests
pytest api_service/services/test_migo_service.py --collect-only -v

# Con descripción completa
pytest api_service/services/test_migo_service.py --collect-only -q
```

---

## 🔧 Corregir Tests Fallidos

Los 5 tests fallidos tienen el mismo error. Para corregirlos:

### Bug Location
Archivo: `api_service/services/migo_service.py`

### Corregir Línea 732 (consultar_tipo_cambio_latest)
```python
# ANTES (INCORRECTO)
return self._make_request(
    endpoint_name="tipo_cambio_latest",
    payload={"token": self.token},  # ❌ Parámetro incorrecto
    endpoint_name_display="Consulta tipo cambio más reciente",
)

# DESPUÉS (CORRECTO)
return self._make_request(
    endpoint_name="tipo_cambio_latest",
    data={"token": self.token},  # ✅ Parámetro correcto
)
```

### Líneas a Corregir
1. **Línea 732** - `consultar_tipo_cambio_latest()`
2. **Línea 747** - `consultar_tipo_cambio_fecha()`
3. **Línea 763** - `consultar_tipo_cambio_rango()`
4. **Línea 782** - `consultar_representantes_legales()`

### Cambio Simple
En los 4 métodos, cambiar:
```python
payload=   →   data=
```

Luego ejecutar:
```bash
pytest api_service/services/test_migo_service.py -v
```

Y todos los 18 tests deberían pasar ✅

---

## 📚 Estructura de Tests

### Agrupación de Tests
```
1️⃣ Inicialización (2 tests)
   - test_migo_service_initialization
   - test_migo_service_database_config

2️⃣ Validaciones (1 test)
   - test_migo_validate_ruc_format

3️⃣ Endpoints Individuales (2 tests)
   - test_migo_consultar_ruc_individual
   - test_migo_consultar_dni

4️⃣ Tipo de Cambio (3 tests) - Requieren fix
   - test_migo_tipo_cambio_latest
   - test_migo_tipo_cambio_fecha
   - test_migo_tipo_cambio_rango

5️⃣ Representantes (1 test) - Requiere fix
   - test_migo_representantes_legales

6️⃣ Consultas Masivas (2 tests)
   - test_migo_consultar_ruc_masivo_pequeño
   - test_migo_consultar_ruc_masivo_completo

7️⃣ Validación Facturación (2 tests)
   - test_migo_validar_ruc_facturacion
   - test_migo_validar_rucs_masivo_facturacion

8️⃣ Cache (1 test)
   - test_migo_invalid_rucs_cache

9️⃣ Rate Limiting (1 test)
   - test_migo_rate_limiting

🔟 Logging (1 test)
   - test_migo_api_call_logging

1️⃣1️⃣ Integración (1 test) - Requiere fix
   - test_migo_complete_workflow

1️⃣2️⃣ Resumen (1 test)
   - test_print_summary
```

---

## 🎓 Ejemplos de Uso para Colaboradores

### Verificar que un RUC es válido
```bash
# Correr solo el test de validación de RUC
pytest api_service/services/test_migo_service.py::test_migo_validate_ruc_format -s
```

### Verificar consulta masiva
```bash
# Correr tests de consulta masiva
pytest api_service/services/test_migo_service.py -k "masivo" -v
```

### Verificar validación de facturación
```bash
# Correr tests de facturación
pytest api_service/services/test_migo_service.py -k "facturacion" -v
```

### Verificar cache
```bash
# Correr test de cache
pytest api_service/services/test_migo_service.py::test_migo_invalid_rucs_cache -v -s
```

---

## 💡 Tips para Desarrollo

1. **Usar `-s` para ver prints**
   - Todos los tests tienen output verboso
   - `-s` flag lo muestra
   - Útil para debugging

2. **Usar `-k` para filtrar tests**
   - `-k "ruc"` - todos los tests con "ruc"
   - `-k "not tipo_cambio"` - excluir tipo_cambio

3. **Usar `--tb` para control de errores**
   - `--tb=short` - traceback corto
   - `--tb=no` - sin traceback
   - `--tb=long` - traceback completo

4. **Ejecutar en orden**
   - Los tests son independientes
   - Pero algunos usan datos de otros
   - Orden sugerido: de inicialización a integración

---

## ✅ Checklist de Uso

- [ ] He instalado pytest
- [ ] He corrido los tests exitosos (13)
- [ ] He visto el output verboso
- [ ] Entiendo estructura de tests
- [ ] Sé cómo corregir los 5 tests fallidos
- [ ] Puedo ejecutar tests con filtros
- [ ] Sé dónde están los tests (api_service/services/test_migo_service.py)
- [ ] Entiendo cómo agregar nuevos tests

---

## 📞 Preguntas Frecuentes

**P: ¿Por qué algunos tests fallan?**  
R: Bug en migo_service.py líneas 732, 747, 763, 782. Cambiar `payload=` por `data=`

**P: ¿Los tests requieren API real?**  
R: No todos. Tests de validación y cache funcionan localmente. API es opcional.

**P: ¿Puedo agregar más tests?**  
R: Sí, copiar estructura de tests existentes. Usar mismo patrón de output.

**P: ¿Cuánto tardan los tests?**  
R: ~5 segundos los 18 tests. Muy rápido para desarrollo.

**P: ¿Necesito datos especiales en BD?**  
R: No, fixture `api_service_migo` los auto-crea si faltan.

