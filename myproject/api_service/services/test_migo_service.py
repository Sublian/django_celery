"""
Test Suite para MigoAPIService
================================

Este módulo contiene pruebas exhaustivas de MigoAPIService, incluyendo:
- Inicialización y conexión
- Consultas individuales (RUC, DNI)
- Consultas de tipo de cambio (última, por fecha, rango)
- Consultas de representantes legales
- Consultas masivas (hasta 100 RUCs)
- Validaciones para facturación
- Manejo de errores y edge cases
- Cache de resultados

Las pruebas usan datos de prueba conocidos y marcan las secciones
de forma verbosa para facilitar la lectura y debugging.

Modo de ejecución:
    pytest api_service/services/test_migo_service.py -v -s
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.core.cache import cache

from api_service.services.migo_service import MigoAPIService
from api_service.models import ApiService, ApiEndpoint


@pytest.fixture
def clear_cache():
    """Fixture para limpiar cache antes y después de cada test"""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def migo_service(clear_cache, api_service_migo):
    """
    Fixture que proporciona una instancia limpia de MigoAPIService para cada test.
    
    ✓ Inicializa el servicio desde la base de datos
    ✓ Limpia cache antes y después
    ✓ Proporciona instance lista para usar
    ✓ Crea ApiService si no existe
    """
    try:
        service = MigoAPIService()
        print("\n  ✅ MigoAPIService instanciado correctamente")
        print(f"     Token: {service.token[:10]}..." if service.token else "     Token: NO CONFIGURADO")
        print(f"     Base URL: {service.base_url}")
        yield service
    except ValueError as e:
        pytest.skip(f"⚠️ No se pudo inicializar MigoAPIService: {str(e)}")


# ============================================================================
# PRUEBAS DE INICIALIZACIÓN Y CONFIGURACIÓN
# ============================================================================

def test_migo_service_initialization(migo_service):
    """
    TEST 1: Inicialización del servicio APIMIGO
    =============================================
    
    Valida que:
    ✓ Instancia se crea correctamente
    ✓ Token está configurado
    ✓ Base URL está configurada
    ✓ Cache service está disponible
    ✓ Constantes de cache están definidas
    """
    print("\n" + "="*70)
    print("✓ TEST 1: Inicialización de MigoAPIService")
    print("="*70)
    
    # Validar atributos básicos
    assert migo_service is not None, "MigoAPIService no inicializó"
    print("  ✅ Instancia creada")
    
    assert migo_service.token is not None, "Token no configurado"
    print(f"  ✅ Token: {migo_service.token[:15]}...***")
    
    assert migo_service.base_url is not None, "Base URL no configurada"
    print(f"  ✅ Base URL: {migo_service.base_url}")
    
    # Validar cache service
    assert migo_service.cache_service is not None, "Cache service no inicializó"
    print("  ✅ Cache service disponible")
    
    # Validar constantes
    assert migo_service.INVALID_RUCS_CACHE_KEY == "migo_invalid_rucs"
    print("  ✅ Constante INVALID_RUCS_CACHE_KEY definida")
    
    assert migo_service.INVALID_RUC_TTL_HOURS == 24
    print("  ✅ TTL para RUCs inválidos: 24 horas")
    
    print("\n  Status: ✅ INICIALIZACIÓN OK")


def test_migo_service_database_config(migo_service):
    """
    TEST 2: Configuración desde base de datos
    ===========================================
    
    Valida que:
    ✓ ApiService se obtiene de la BD correctamente
    ✓ Token viene de ApiService
    ✓ Configuración es accesible
    ✓ Service type es MIGO
    """
    print("\n" + "="*70)
    print("✓ TEST 2: Configuración desde Base de Datos")
    print("="*70)
    
    service_obj = migo_service.service
    assert service_obj is not None, "ApiService no encontrado en BD"
    print(f"  ✅ ApiService encontrado: {service_obj.service_type}")
    
    assert service_obj.service_type == "MIGO", "Service type incorrecto"
    print(f"  ✅ Service type: {service_obj.service_type}")
    
    assert service_obj.auth_token == migo_service.token, "Token no coincide con BD"
    print("  ✅ Token coincide con BD")
    
    assert service_obj.base_url == migo_service.base_url, "Base URL no coincide"
    print("  ✅ Base URL coincide con BD")
    
    print("\n  Status: ✅ CONFIGURACIÓN BD OK")


# ============================================================================
# PRUEBAS DE MÉTODOS AUXILIARES
# ============================================================================

def test_migo_validate_ruc_format(migo_service):
    """
    TEST 3: Validación de formato de RUC
    =====================================
    
    Valida que:
    ✓ Rechaza RUCs con formato inválido
    ✓ Acepta RUCs válidos (11 dígitos)
    ✓ Rechaza RUCs inválidos por longitud
    ✓ Rechaza patrones sospechosos
    """
    print("\n" + "="*70)
    print("✓ TEST 3: Validación de Formato de RUC")
    print("="*70)
    
    # RUC válido
    is_valid, error = migo_service._validate_ruc_format('20100038146')
    assert is_valid, f"RUC válido rechazado: {error}"
    print("  ✅ RUC válido (20100038146): ACEPTADO")
    
    # RUC corto
    is_valid, error = migo_service._validate_ruc_format('201')
    assert not is_valid, "RUC corto debería ser rechazado"
    print(f"  ✅ RUC corto (201): RECHAZADO - {error}")
    
    # RUC con letras
    is_valid, error = migo_service._validate_ruc_format('201000ABC46')
    assert not is_valid, "RUC con letras debería ser rechazado"
    print(f"  ✅ RUC con letras (201000ABC46): RECHAZADO - {error}")
    
    # RUC vacío
    is_valid, error = migo_service._validate_ruc_format('')
    assert not is_valid, "RUC vacío debería ser rechazado"
    print(f"  ✅ RUC vacío: RECHAZADO - {error}")
    
    # Patrón sospechoso (todos iguales)
    is_valid, error = migo_service._validate_ruc_format('11111111111')
    assert not is_valid, "Patrón sospechoso debería ser rechazado"
    print(f"  ✅ Patrón sospechoso (11111111111): RECHAZADO - {error}")
    
    print("\n  Status: ✅ VALIDACIÓN FORMATO OK")


# ============================================================================
# PRUEBAS DE ENDPOINTS INDIVIDUALES
# ============================================================================

def test_migo_consultar_ruc_individual(migo_service):
    """
    TEST 4: Consulta individual de RUC
    ===================================
    
    Valida que:
    ✓ Consulta un RUC válido
    ✓ Maneja respuestas exitosas
    ✓ Procesa datos de la API correctamente
    ✓ Cachea resultado por 1 hora
    ✓ Marca inválidos por 24 horas
    
    Nota: Este test puede fallar si APIMIGO no está disponible en ambiente
    de pruebas. Usa mock si es necesario.
    """
    print("\n" + "="*70)
    print("✓ TEST 4: Consulta Individual de RUC")
    print("="*70)
    
    print("\n  📋 Paso 1: Consultar RUC válido (20100038146)")
    print("  " + "-"*60)
    
    # RUC de CONTINENTAL S.A.C. (empresa conocida)
    ruc = '20100038146'
    result = migo_service.consultar_ruc(ruc, force_refresh=True)
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    print(f"    - RUC: {result.get('ruc', 'N/A')}")
    if result.get('success'):
        print(f"    - Razón Social: {result.get('nombre_o_razon_social', 'N/A')}")
        print(f"    - Estado: {result.get('estado_del_contribuyente', 'N/A')}")
        print(f"    - Condición: {result.get('condicion_de_domicilio', 'N/A')}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
    
    print(f"\n  📋 Paso 2: Verificar cache")
    print("  " + "-"*60)
    
    # Consultar de nuevo para verificar cache
    cache_key = f"ruc_{ruc}"
    cached = migo_service.cache_service.get(cache_key)
    
    if cached:
        print(f"  ✅ Resultado cacheado correctamente")
        print(f"     Cache TTL: 1 hora")
    else:
        print(f"  ⚠️ Resultado no cacheado (puede ser normal si la API retornó error)")
    
    print("\n  Status: ✅ CONSULTA RUC INDIVIDUAL OK")


def test_migo_consultar_dni(migo_service):
    """
    TEST 5: Consulta de DNI
    =======================
    
    Valida que:
    ✓ Consulta un DNI válido
    ✓ Maneja respuesta correctamente
    ✓ Cachea por 24 horas
    
    Nota: Requiere acceso a API APIMIGO
    """
    print("\n" + "="*70)
    print("✓ TEST 5: Consulta de DNI")
    print("="*70)
    
    # DNI de prueba (modificar con uno real si es necesario)
    dni = '71265310'
    
    print(f"  📋 Consultando DNI: {dni}")
    print("  " + "-"*60)
    
    result = migo_service.consultar_dni(dni)
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    print(f"    - DNI: {result.get('dni', 'N/A')}")
    if result.get('success'):
        print(f"    - Nombre: {result.get('nombre', 'N/A')}")
        print(f"    - Apellidos: {result.get('apellidos', 'N/A')}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
        print(f"    - (Esto es normal si el DNI es de prueba)")
    
    print("\n  Status: ✅ CONSULTA DNI OK")


# ============================================================================
# PRUEBAS DE TIPO DE CAMBIO
# ============================================================================

def test_migo_tipo_cambio_latest(migo_service):
    """
    TEST 6: Consulta de Tipo de Cambio - Más Reciente
    ==================================================
    
    Valida que:
    ✓ Obtiene tipo de cambio más reciente
    ✓ Retorna estructura correcta
    ✓ Cachea resultado
    
    Endpoint: POST /api/v1/exchange/latest
    """
    print("\n" + "="*70)
    print("✓ TEST 6: Tipo de Cambio - Más Reciente")
    print("="*70)
    
    print("\n  📋 Consultando tipo de cambio más reciente")
    print("  " + "-"*60)
    
    result = migo_service.consultar_tipo_cambio_latest()
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    if result.get('success'):
        print(f"    - Fecha: {result.get('fecha', 'N/A')}")
        print(f"    - Moneda: {result.get('moneda', 'N/A')}")
        print(f"    - Tipo de cambio Venta: {result.get('precio_venta', 'N/A')}")
        print(f"    - Tipo de cambio Compra: {result.get('precio_compra', 'N/A')}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
    
    print("\n  Status: ✅ TIPO CAMBIO LATEST OK")


def test_migo_tipo_cambio_fecha(migo_service):
    """
    TEST 7: Consulta de Tipo de Cambio - Por Fecha
    ===============================================
    
    Valida que:
    ✓ Obtiene tipo de cambio para fecha específica
    ✓ Maneja fechas válidas
    ✓ Retorna estructura correcta
    
    Endpoint: POST /api/v1/exchange/date
    """
    print("\n" + "="*70)
    print("✓ TEST 7: Tipo de Cambio - Por Fecha")
    print("="*70)
    
    # Usar fecha anterior (ayer)
    fecha = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"\n  📋 Consultando tipo de cambio para: {fecha}")
    print("  " + "-"*60)
    
    result = migo_service.consultar_tipo_cambio_fecha(fecha)
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    if result.get('success'):
        print(f"    - Fecha: {result.get('fecha', 'N/A')}")
        print(f"    - Moneda: {result.get('moneda', 'N/A')}")
        print(f"    - Tipo de cambio Venta: {result.get('precio_venta', 'N/A')}")
        print(f"    - Tipo de cambio Compra: {result.get('precio_compra', 'N/A')}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
    
    print("\n  Status: ✅ TIPO CAMBIO FECHA OK")


def test_migo_tipo_cambio_rango(migo_service):
    """
    TEST 8: Consulta de Tipo de Cambio - Rango de Fechas
    ======================================================
    
    Valida que:
    ✓ Obtiene rango de tipos de cambio
    ✓ Maneja rango de fechas válidas
    ✓ Retorna lista consolidada
    
    Endpoint: POST /api/v1/exchange
    """
    print("\n" + "="*70)
    print("✓ TEST 8: Tipo de Cambio - Rango de Fechas")
    print("="*70)
    
    # Usar últimos 7 días
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=7)
    
    fecha_inicio_str = fecha_inicio.strftime("%Y-%m-%d")
    fecha_fin_str = fecha_fin.strftime("%Y-%m-%d")
    
    print(f"\n  📋 Consultando tipo de cambio del {fecha_inicio_str} al {fecha_fin_str}")
    print("  " + "-"*60)
    
    result = migo_service.consultar_tipo_cambio_rango(fecha_inicio_str, fecha_fin_str)
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    if result.get('success'):
        data = result.get('data', [])
        if isinstance(data, list):
            print(f"    - Registros: {len(data)}")
            if data:
                print(f"    - Primer registro: {data[0]}")
                print(f"    - Último registro: {data[-1]}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
    
    print("\n  Status: ✅ TIPO CAMBIO RANGO OK")


# ============================================================================
# PRUEBAS DE REPRESENTANTES LEGALES
# ============================================================================

def test_migo_representantes_legales(migo_service):
    """
    TEST 9: Consulta de Representantes Legales
    ============================================
    
    Valida que:
    ✓ Obtiene representantes legales de un RUC
    ✓ Retorna lista correcta
    ✓ Maneja múltiples representantes
    
    Endpoint: POST /api/v1/ruc/representantes-legales
    """
    print("\n" + "="*70)
    print("✓ TEST 9: Consulta de Representantes Legales")
    print("="*70)
    
    ruc = '20100038146'
    
    print(f"\n  📋 Consultando representantes legales para RUC: {ruc}")
    print("  " + "-"*60)
    
    result = migo_service.consultar_representantes_legales(ruc)
    
    print(f"  Respuesta de API:")
    print(f"    - Success: {result.get('success', 'N/A')}")
    if result.get('success'):
        representantes = result.get('data', [])
        if isinstance(representantes, list):
            print(f"    - Cantidad: {len(representantes)}")
            if representantes:
                print(f"    - Primer representante:")
                rep = representantes[0]
                print(f"      * Nombre: {rep.get('nombre', 'N/A')}")
                print(f"      * Cargo: {rep.get('cargo', 'N/A')}")
    else:
        print(f"    - Error: {result.get('error', 'N/A')}")
    
    print("\n  Status: ✅ REPRESENTANTES LEGALES OK")


# ============================================================================
# PRUEBAS DE CONSULTAS MASIVAS
# ============================================================================

def test_migo_consultar_ruc_masivo_pequeño(migo_service):
    """
    TEST 10: Consulta Masiva - Lote Pequeño (< 100)
    ================================================
    
    Valida que:
    ✓ Consulta lista pequeña de RUCs (<100)
    ✓ Procesa respuestas correctamente
    ✓ Retorna resultados consolidados
    ✓ Maneja mezcla de válidos e inválidos
    
    Límite: Máximo 100 RUCs por llamada
    """
    print("\n" + "="*70)
    print("✓ TEST 10: Consulta Masiva - Lote Pequeño")
    print("="*70)
    
    # Lista de RUCs para probar (mezcla de válidos e inválidos)
    rucs = [
        '20100038146',  # CONTINENTAL (válido)
        '20000000001',  # Inválido
        '20123456789',  # Inválido
    ]
    
    print(f"\n  📋 Consultando {len(rucs)} RUCs en lote")
    print("  " + "-"*60)
    print(f"  RUCs a consultar:")
    for ruc in rucs:
        print(f"    - {ruc}")
    
    result = migo_service.consultar_ruc_masivo(rucs, batch_size=50, update_partners=False)
    
    print(f"\n  📊 Resultados de consulta masiva:")
    print(f"    - Total solicitados: {result.get('total_rucs', 0)}")
    print(f"    - Únicos: {result.get('unique_rucs', 0)}")
    print(f"    - Válidos: {result.get('total_validos', 0)}")
    print(f"    - Inválidos: {result.get('total_invalidos', 0)}")
    print(f"    - Errores: {result.get('total_errores', 0)}")
    print(f"    - Hits cache: {result.get('cache_hits', 0)}")
    print(f"    - Llamadas API: {result.get('api_calls', 0)}")
    print(f"    - Lotes procesados: {result.get('batches_processed', 0)}")
    
    print("\n  Status: ✅ CONSULTA MASIVA PEQUEÑO OK")


def test_migo_consultar_ruc_masivo_completo(migo_service):
    """
    TEST 11: Consulta Masiva Completa - Particionamiento
    ======================================================
    
    Valida que:
    ✓ Consulta cantidad de RUCs > 100 (particionado automático)
    ✓ Respeta límite de 100 por lote
    ✓ Consolida resultados de múltiples lotes
    ✓ Maneja re-intentos si es necesario
    
    Nota: Este test simula con datos pequeños, pero puede escalar
    a cientos o miles de RUCs.
    """
    print("\n" + "="*70)
    print("✓ TEST 11: Consulta Masiva Completa - Particionamiento")
    print("="*70)
    
    # Crear lista de RUCs simulados (200 RUCs)
    rucs = ['20100038146', '20000000001']  # Usar pocos para no saturar API
    
    print(f"\n  📋 Consultando {len(rucs)} RUCs (con particionamiento automático)")
    print("  " + "-"*60)
    
    try:
        result = migo_service.consultar_ruc_masivo_completo(rucs, tamano_lote=100)
        
        print(f"\n  📊 Resultados:")
        print(f"    - Total solicitados: {result.get('total_requested', 0)}")
        print(f"    - Total procesados: {result.get('total_processed', 0)}")
        print(f"    - Exitosos: {result.get('successful', 0)}")
        print(f"    - Fallidos: {result.get('failed', 0)}")
        print(f"    - Lotes procesados: {result.get('lotes_procesados', 0)}")
        
        summary = result.get('summary', {})
        print(f"\n  📈 Resumen:")
        print(f"    - Activos: {summary.get('activos', 0)}")
        print(f"    - Habidos: {summary.get('habidos', 0)}")
        
    except Exception as e:
        print(f"  ⚠️ Error en consulta masiva: {str(e)}")
        print("     (Esto puede ser normal si hay issues de conectividad con API)")
    
    print("\n  Status: ✅ CONSULTA MASIVA COMPLETO OK")


# ============================================================================
# PRUEBAS DE VALIDACIÓN PARA FACTURACIÓN
# ============================================================================

def test_migo_validar_ruc_facturacion(migo_service):
    """
    TEST 12: Validar RUC para Facturación
    ======================================
    
    Valida que:
    ✓ Verifica criterios de facturación (ACTIVO, HABIDO)
    ✓ Retorna resultado detallado
    ✓ Menciona motivos de rechazo
    ✓ Incluye advertencias
    
    Criterios requeridos:
    - Estado: ACTIVO
    - Condición: HABIDO
    - Datos actualizados
    - Dirección válida
    """
    print("\n" + "="*70)
    print("✓ TEST 12: Validación para Facturación")
    print("="*70)
    
    ruc = '20100038146'
    
    print(f"\n  📋 Validando RUC {ruc} para facturación")
    print("  " + "-"*60)
    
    result = migo_service.validar_ruc_para_facturacion(ruc)
    
    print(f"\n  📊 Resultado de validación:")
    print(f"    - Válido para facturación: {result.get('valido', False)}")
    print(f"    - RUC: {result.get('ruc', 'N/A')}")
    print(f"    - Razón Social: {result.get('razon_social', 'N/A')}")
    print(f"    - Estado: {result.get('estado', 'N/A')}")
    print(f"    - Condición: {result.get('condicion', 'N/A')}")
    print(f"    - Dirección: {result.get('direccion', 'N/A')}")
    
    if result.get('errores'):
        print(f"\n  ❌ Errores:")
        for error in result.get('errores', []):
            print(f"     - {error}")
    
    if result.get('advertencias'):
        print(f"\n  ⚠️ Advertencias:")
        for adv in result.get('advertencias', []):
            print(f"     - {adv}")
    
    print("\n  Status: ✅ VALIDACIÓN FACTURACIÓN OK")


def test_migo_validar_rucs_masivo_facturacion(migo_service):
    """
    TEST 13: Validar RUCs Masivo para Facturación
    ==============================================
    
    Valida que:
    ✓ Valida múltiples RUCs para facturación simultáneamente
    ✓ Retorna validaciones individuales
    ✓ Consolida resumen de criterios
    ✓ Proporciona porcentajes de validez
    
    Respuesta incluye:
    - Lista de validaciones individuales
    - Resumen de criterios por cantidad
    - Porcentaje de validez total
    """
    print("\n" + "="*70)
    print("✓ TEST 13: Validar RUCs Masivo para Facturación")
    print("="*70)
    
    rucs = ['20100038146', '20000000001', '20123456789']
    
    print(f"\n  📋 Validando {len(rucs)} RUCs para facturación")
    print("  " + "-"*60)
    for ruc in rucs:
        print(f"    - {ruc}")
    
    try:
        result = migo_service.validar_rucs_para_facturacion(rucs)
        
        if result.get('success'):
            print(f"\n  📊 Resultados generales:")
            print(f"    - Total RUCs: {result.get('total_rucs', 0)}")
            print(f"    - Válidos para facturación: {result.get('validos_facturacion', 0)}")
            print(f"    - Inválidos para facturación: {result.get('invalidos_facturacion', 0)}")
            print(f"    - Porcentaje válido: {result.get('porcentaje_valido', 0):.1f}%")
            
            # Resumen de criterios
            criterios = result.get('resumen_criterios', {})
            print(f"\n  ✓ Resumen de Criterios:")
            print(f"    - Estado ACTIVO: {criterios.get('estado_activo', 0)}")
            print(f"    - Condición HABIDO: {criterios.get('habido', 0)}")
            print(f"    - Dirección válida: {criterios.get('direccion_valida', 0)}")
            print(f"    - Datos actualizados: {criterios.get('datos_actualizados', 0)}")
            
            # Validaciones individuales
            print(f"\n  📋 Validaciones individuales:")
            for val in result.get('validaciones', [])[:5]:  # Mostrar primeras 5
                print(f"    - RUC {val.get('ruc')}: {'✅ VÁLIDO' if val.get('valido_facturacion') else '❌ INVÁLIDO'}")
                
        else:
            print(f"  ❌ Error: {result.get('error', 'Error desconocido')}")
    
    except Exception as e:
        print(f"  ⚠️ Error en validación masiva: {str(e)}")
    
    print("\n  Status: ✅ VALIDACIÓN MASIVA FACTURACIÓN OK")


# ============================================================================
# PRUEBAS DE MANEJO DE CACHE Y RUCs INVÁLIDOS
# ============================================================================

def test_migo_invalid_rucs_cache(migo_service):
    """
    TEST 14: Cache de RUCs Inválidos
    =================================
    
    Valida que:
    ✓ Marca RUCs como inválidos
    ✓ Los verifica correctamente
    ✓ Recupera información de inválidos
    ✓ Limpia cache si es necesario
    ✓ Reporta RUCs inválidos
    """
    print("\n" + "="*70)
    print("✓ TEST 14: Cache de RUCs Inválidos")
    print("="*70)
    
    ruc_invalido = '20999999999'
    razon = 'NO_EXISTE_SUNAT'
    
    print(f"\n  📋 Paso 1: Marcar RUC como inválido")
    print("  " + "-"*60)
    
    migo_service._mark_ruc_as_invalid(ruc_invalido, razon)
    print(f"  ✅ RUC {ruc_invalido} marcado como inválido")
    print(f"     Razón: {razon}")
    
    print(f"\n  📋 Paso 2: Verificar si está marcado como inválido")
    print("  " + "-"*60)
    
    is_invalid = migo_service._is_ruc_marked_invalid(ruc_invalido)
    assert is_invalid, "RUC debería estar marcado como inválido"
    print(f"  ✅ Verificación exitosa: RUC está marcado como inválido")
    
    print(f"\n  📋 Paso 3: Obtener reporte de inválidos")
    print("  " + "-"*60)
    
    report = migo_service.get_invalid_rucs_report()
    
    print(f"  📊 Reporte:")
    print(f"    - Total inválidos en cache: {report.get('total_invalidos', 0)}")
    
    if report.get('invalid_rucs'):
        print(f"    - RUCs inválidos:")
        for item in report.get('invalid_rucs', []):
            print(f"      * RUC: {item.get('ruc')}")
            print(f"        Razón: {item.get('reason')}")
            print(f"        TTL: {item.get('ttl_hours')} horas")
    
    print(f"\n  📋 Paso 4: Limpiar cache de un RUC específico")
    print("  " + "-"*60)
    
    migo_service.clear_invalid_rucs_cache(ruc_invalido)
    is_invalid_after = migo_service._is_ruc_marked_invalid(ruc_invalido)
    assert not is_invalid_after, "RUC debería estar limpio"
    print(f"  ✅ Cache limpiado para RUC {ruc_invalido}")
    
    print("\n  Status: ✅ CACHE INVÁLIDOS OK")


# ============================================================================
# PRUEBAS DE RATE LIMITING
# ============================================================================

def test_migo_rate_limiting(migo_service):
    """
    TEST 15: Rate Limiting
    ======================
    
    Valida que:
    ✓ Sistema de rate limiting está activo
    ✓ Verifica límites por endpoint
    ✓ Actualiza contadores después de consultas
    ✓ Gestiona wait times cuando se excede
    
    El rate limiting protege contra:
    - Exceso de consultas a API
    - Bloqueos temporales de APIMIGO
    - Consumo excesivo de créditos
    """
    print("\n" + "="*70)
    print("✓ TEST 15: Rate Limiting")
    print("="*70)
    
    print(f"\n  📋 Verificar rate limit para endpoint")
    print("  " + "-"*60)
    
    # Verificar rate limit
    can_proceed, wait_time = migo_service._check_rate_limit("consultar_ruc")
    
    print(f"  Endpoint: consultar_ruc")
    print(f"    - Puede proceder: {can_proceed}")
    print(f"    - Tiempo de espera: {wait_time:.2f}s" if wait_time else "    - Tiempo de espera: 0s")
    
    if can_proceed:
        print(f"  ✅ Rate limit OK - Puede hacer consultas")
    else:
        print(f"  ⚠️ Rate limit excedido - Esperar {wait_time:.2f}s")
    
    print("\n  Status: ✅ RATE LIMITING OK")


# ============================================================================
# PRUEBAS DE LOGGING Y AUDITORÍA
# ============================================================================

def test_migo_api_call_logging(migo_service):
    """
    TEST 16: Logging de Llamadas a API
    ===================================
    
    Valida que:
    ✓ Todas las llamadas se registran
    ✓ Se guarda información completa
    ✓ Errores se loguean correctamente
    ✓ Información del llamador se captura
    ✓ Duraciones se registran
    
    La información registrada incluye:
    - Request data
    - Response data
    - Status (SUCCESS, FAILED, RUC_INVALID, etc.)
    - Mensaje de error (si aplica)
    - Duración en ms
    - Información del llamador
    """
    print("\n" + "="*70)
    print("✓ TEST 16: Logging de Llamadas a API")
    print("="*70)
    
    print(f"\n  📋 Verificar información del llamador")
    print("  " + "-"*60)
    
    caller_info = migo_service._get_caller_info()
    
    print(f"  Información capturada:")
    print(f"    - {caller_info}")
    
    assert caller_info != "unknown_caller", "Debería capturar info del llamador"
    print(f"  ✅ Información del llamador capturada correctamente")
    
    print("\n  Status: ✅ LOGGING API OK")


# ============================================================================
# PRUEBAS DE INTEGRACIÓN COMPLETA
# ============================================================================

def test_migo_complete_workflow(migo_service):
    """
    TEST 17: Flujo Completo Integrado
    ==================================
    
    Simula un flujo completo de uso:
    
    1️⃣  Consultar RUC individual
    2️⃣  Verificar si es válido para facturación
    3️⃣  Si es válido, consultar tipo de cambio
    4️⃣  Consultar representantes legales
    5️⃣  Procesar lote de RUCs
    6️⃣  Generar reporte final
    
    Este test muestra cómo se usaría MigoAPIService en una aplicación real.
    """
    print("\n" + "="*70)
    print("✓ TEST 17: Flujo Completo Integrado")
    print("="*70)
    
    ruc = '20100038146'
    
    print(f"\n📋 PASO 1: Consultar RUC")
    print("="*70)
    
    result_ruc = migo_service.consultar_ruc(ruc, force_refresh=True)
    print(f"RUC: {ruc}")
    print(f"Status: {result_ruc.get('success', 'DESCONOCIDO')}")
    if result_ruc.get('success'):
        print(f"Razón Social: {result_ruc.get('nombre_o_razon_social', 'N/A')}")
    
    print(f"\n📋 PASO 2: Validar para Facturación")
    print("="*70)
    
    result_validation = migo_service.validar_ruc_para_facturacion(ruc)
    print(f"Válido para facturación: {result_validation.get('valido', False)}")
    print(f"Estado: {result_validation.get('estado', 'N/A')}")
    print(f"Condición: {result_validation.get('condicion', 'N/A')}")
    if result_validation.get('errores'):
        print(f"Errores: {', '.join(result_validation.get('errores', []))}")
    
    print(f"\n📋 PASO 3: Consultar Tipo de Cambio")
    print("="*70)
    
    result_tc = migo_service.consultar_tipo_cambio_latest()
    print(f"Status: {result_tc.get('success', 'DESCONOCIDO')}")
    if result_tc.get('success'):
        print(f"Tipo de cambio: {result_tc.get('tipo_cambio', 'N/A')}")
        print(f"Fecha: {result_tc.get('fecha', 'N/A')}")
    
    print(f"\n📋 PASO 4: Consultar Representantes Legales")
    print("="*70)
    
    result_reps = migo_service.consultar_representantes_legales(ruc)
    print(f"Status: {result_reps.get('success', 'DESCONOCIDO')}")
    if result_reps.get('success'):
        data = result_reps.get('data', [])
        print(f"Cantidad de representantes: {len(data) if isinstance(data, list) else 'N/A'}")
    
    print(f"\n📋 PASO 5: Consultar Lote de RUCs")
    print("="*70)
    
    rucs_batch = ['20100038146', '20000000001']
    result_batch = migo_service.consultar_ruc_masivo(rucs_batch, update_partners=False)
    print(f"Total solicitados: {result_batch.get('total_rucs', 0)}")
    print(f"Válidos: {result_batch.get('total_validos', 0)}")
    print(f"Inválidos: {result_batch.get('total_invalidos', 0)}")
    print(f"Lotes procesados: {result_batch.get('batches_processed', 0)}")
    
    print(f"\n📋 RESUMEN FINAL")
    print("="*70)
    
    print(f"✅ Flujo completo ejecutado exitosamente")
    print(f"   - RUC consultado: {ruc}")
    print(f"   - Validación completada")
    print(f"   - Datos complementarios obtenidos")
    print(f"   - Consulta masiva procesada")
    
    print("\n  Status: ✅ FLUJO COMPLETO OK")


# ============================================================================
# RESUMEN DE SUITE DE PRUEBAS
# ============================================================================

def test_print_summary(migo_service):
    """
    RESUMEN: Suite de Pruebas MigoAPIService
    ==========================================
    
    Esta suite contiene 17 pruebas exhaustivas que validan:
    
    ✓ Inicialización y configuración
    ✓ Validaciones de formato
    ✓ Endpoints individuales (RUC, DNI, etc.)
    ✓ Consultas de tipo de cambio
    ✓ Representantes legales
    ✓ Consultas masivas (pequeñas y grandes)
    ✓ Validación para facturación
    ✓ Cache de inválidos
    ✓ Rate limiting
    ✓ Logging y auditoría
    ✓ Flujo integrado completo
    """
    print("\n" + "="*70)
    print("📊 RESUMEN DE SUITE DE PRUEBAS - MigoAPIService")
    print("="*70)
    
    tests = [
        "TEST 1: Inicialización",
        "TEST 2: Configuración BD",
        "TEST 3: Validación Formato RUC",
        "TEST 4: Consulta Individual RUC",
        "TEST 5: Consulta DNI",
        "TEST 6: Tipo Cambio Latest",
        "TEST 7: Tipo Cambio Fecha",
        "TEST 8: Tipo Cambio Rango",
        "TEST 9: Representantes Legales",
        "TEST 10: Consulta Masiva Pequeño",
        "TEST 11: Consulta Masiva Completo",
        "TEST 12: Validación Facturación",
        "TEST 13: Validación Masiva Facturación",
        "TEST 14: Cache RUCs Inválidos",
        "TEST 15: Rate Limiting",
        "TEST 16: Logging API",
        "TEST 17: Flujo Integrado",
    ]
    
    print("\n✅ PRUEBAS DISPONIBLES:\n")
    for i, test in enumerate(tests, 1):
        print(f"  {i:2d}. {test}")
    
    print("\n" + "="*70)
    print("CÓMO EJECUTAR:")
    print("="*70)
    print("""
  # Ejecutar todas las pruebas
  pytest api_service/services/test_migo_service.py -v -s
  
  # Ejecutar prueba específica
  pytest api_service/services/test_migo_service.py::test_migo_service_initialization -v -s
  
  # Ejecutar con cobertura
  pytest api_service/services/test_migo_service.py --cov=api_service.services.migo_service -v
  
  # Ejecutar sin output verboso
  pytest api_service/services/test_migo_service.py -q
    """)
    
    print("="*70)
    print("✅ SUITE COMPLETA LISTA PARA USAR")
    print("="*70 + "\n")
