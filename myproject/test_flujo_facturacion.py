import os
import sys
import django
import json
import time
import hashlib
from datetime import datetime, date

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.core.cache import cache
from django.utils import timezone
from api_service.services import MigoAPIClient as MigoClient
from billing.models import Currency, CurrencyRate, Partner, Company

def obtener_tipo_cambio_dia(force_api=False):
    """
    Obtiene el tipo de cambio del día con cache en 3 niveles:
    1. Cache Django (15 minutos)
    2. Base de datos billing_currencyrate
    3. API MIGO
    
    Args:
        force_api: Si True, ignora cache y va directo a API
    
    Returns:
        dict con datos de tipo de cambio
    """
    
    print("\n💱 OBTENIENDO TIPO DE CAMBIO DEL DÍA")
    print("="*40)
    
    hoy = date.today()
    cache_key = f"tipo_cambio_{hoy.isoformat()}"
    
    # 1. Verificar cache Django (15 minutos)
    if not force_api:
        cached = cache.get(cache_key)
        print(f"🔍 Verificando cache Django para {cache_key}...")
        if cached:
            print(f"✅ Tipo cambio obtenido de cache Django")
            return cached
    
    # 2. Verificar base de datos
    try:
        # Buscar USD en Currency
        moneda_usd = Currency.objects.filter(name='USD').first()
        
        if moneda_usd:
            tipo_cambio_db = CurrencyRate.objects.filter(
                currency=moneda_usd,
                date_rate=hoy
            ).order_by('-date_rate').first()
            
            if tipo_cambio_db:
                print(f"✅ Tipo cambio obtenido de base de datos")
                resultado = {
                    'success': True,
                    'fecha': hoy.isoformat(), 
                    'compra': float(tipo_cambio_db.purchase_rate),
                    'venta': float(tipo_cambio_db.sale_rate),
                    'fuente': 'database',
                    'currency_rate_id': tipo_cambio_db.id
                }
                
                # Guardar en cache por 15 minutos
                cache.set(cache_key, resultado, 900)
                return resultado
    except Exception as e:
        print(f"⚠️  Error consultando BD: {str(e)}")
    
    # 3. Consultar API MIGO
    print(f"🔍 Consultando API MIGO para tipo de cambio...")
    client = MigoClient()
    
    try:
        # Primero intentar tipo_cambio_latest (más reciente)
        resultado = client.consultar_tipo_cambio_latest()
        
        if resultado.get('success'):
            print(f"✅ Tipo cambio obtenido de API MIGO (latest)")
            
            # Guardar en base de datos
            try:
                moneda_usd, _ = Currency.objects.get_or_create(
                    name='USD',
                    defaults={
                        'name': 'US Dollar',
                        'symbol': '$',
                        'active': True
                    }
                )
                company = Company.objects.first()
                currency_rate = CurrencyRate.objects.create(
                    currency=moneda_usd,
                    date_rate=hoy,
                    purchase_rate=resultado.get('precio_compra', 0),
                    sale_rate=resultado.get('precio_venta', 0),
                    company=company,
                )
                
                resultado['currency_rate_id'] = currency_rate.id
                resultado['fuente'] = 'api_migo_latest'
                
            except Exception as e:
                print(f"⚠️  Error guardando en BD: {str(e)}")
                resultado['fuente'] = 'api_migo_latest_no_save'
            
            # Guardar en cache por 15 minutos
            cache.set(cache_key, resultado, 900)
            return resultado
        
    except Exception as e:
        print(f"❌ Error API latest: {str(e)}")
    
    # Si latest falla, intentar con fecha específica
    try:
        resultado = client.consultar_tipo_cambio_fecha(hoy.isoformat())
        
        if resultado.get('success'):
            print(f"✅ Tipo cambio obtenido de API MIGO (fecha específica)")
            
            # Guardar en base de datos
            try:
                moneda_usd, _ = Currency.objects.get_or_create(
                    code='USD',
                    defaults={
                        'name': 'US Dollar',
                        'symbol': '$',
                        'active': True
                    }
                )
                
                currency_rate = CurrencyRate.objects.create(
                    currency=moneda_usd,
                    date=hoy,
                    rate_buy=resultado.get('compra', 0),
                    rate_sell=resultado.get('venta', 0),
                    source='MIGO API',
                    metadata={'api_response': resultado}
                )
                
                resultado['currency_rate_id'] = currency_rate.id
                resultado['fuente'] = 'api_migo_fecha'
                
            except Exception as e:
                print(f"⚠️  Error guardando en BD: {str(e)}")
                resultado['fuente'] = 'api_migo_fecha_no_save'
            
            # Guardar en cache
            cache.set(cache_key, resultado, 900)
            return resultado
        
    except Exception as e:
        print(f"❌ Error API fecha específica: {str(e)}")
    
    # Si todo falla, usar último disponible
    print(f"⚠️  Usando último tipo cambio disponible en BD")
    try:
        ultimo = CurrencyRate.objects.filter(
            currency__code='USD'
        ).order_by('-date').first()
        
        if ultimo:
            resultado = {
                'success': True,
                'fecha': ultimo.date.isoformat(),
                'compra': float(ultimo.rate_buy),
                'venta': float(ultimo.rate_sell),
                'fuente': 'ultimo_disponible',
                'currency_rate_id': ultimo.id,
                'advertencia': f'Tipo cambio del {ultimo.date}, no del día actual'
            }
            cache.set(cache_key, resultado, 900)
            return resultado
    except:
        pass
    
    # Último recurso: valor por defecto
    print(f"⚠️  Usando valor por defecto")
    return {
        'success': False,
        'fecha': hoy.isoformat(),
        'compra': 3.70,
        'venta': 3.75,
        'fuente': 'valor_por_defecto',
        'advertencia': 'No se pudo obtener tipo cambio real'
    }

def obtener_rucs_para_validacion():
    """
    Obtiene RUCs para validación combinando:
    1. Partners activos de la BD
    2. RUCs con casos especiales (fallidos)
    
    Returns:
        dict con listas de RUCs organizadas
    """
    print("\n🔍 OBTENIENDO RUCS PARA VALIDACIÓN")
    print("="*40)
    
    # 1. Partners activos de la BD
    partners_rucs = []
    try:
        
        partners = Partner.objects.filter(
            document_type='ruc',
            is_active=True
        ).values_list('num_document', flat=True)
        
        for ruc in partners:
            if ruc:
                ruc_str = str(ruc).strip()
                if len(ruc_str) == 11 and ruc_str.isdigit():
                    partners_rucs.append(ruc_str)
        
        print(f"✅ Partners activos: {len(partners_rucs)} RUCs")
        
    except Exception as e:
        print(f"⚠️  Error obteniendo partners: {str(e)}")
        # Datos de ejemplo si no hay BD
        partners_rucs = [
            "20557425889", "20607403903", "20546904106", "20603274742",
            "20100035370", "20100039155", "20100000902", "20131312955"
        ]
        print(f"⚠️  Usando RUCs de ejemplo: {len(partners_rucs)}")
    
    # 2. RUCs con casos especiales (fallidos)
    rucs_fallidos = [
        "20493957288", "20293910767", "20411305474", "20487486435", 
        "20494100186", "20490469797", "20493996429", "20491172216", 
        "20571445132", "20552103816", "20570812361", "20573858124", 
        "20600669207", "20613142038", "20613142046", "20613212435", 
        "20613212443", "20613221388", "20613243535", "20613309714",
        "20600669207", "20613142038", "20613142046", "20613212435", 
    ]
    
    # Eliminar duplicados y asegurar que sean únicos
    rucs_fallidos_unicos = list(set(rucs_fallidos))
    
    # Combinar todas las listas
    todos_rucs = list(set(partners_rucs + rucs_fallidos_unicos))
    
    print(f"📊 Total RUCs para validar: {len(todos_rucs)}")
    print(f"   • Partners: {len(partners_rucs)}")
    print(f"   • Casos especiales: {len(rucs_fallidos_unicos)}")
    print(f"   • Duplicados eliminados: {len(partners_rucs) + len(rucs_fallidos_unicos) - len(todos_rucs)}")
    
    return {
        'todos': todos_rucs,
        'partners': partners_rucs,
        'fallidos': rucs_fallidos_unicos,
        'total': len(todos_rucs)
    }

def _consolidar_resultados(resultados, total_esperado, total_procesado_api=0):
    """
    Consolidar y analizar resultados de validación
    
    Args:
        resultados: Lista de diccionarios con resultados de validación
        total_esperado: Número total de RUCs que se intentaron validar
        total_procesado_api: RUCs para los que la API intentó dar respuesta
    
    Returns:
        dict con resultados consolidados y análisis
    """
    total = len(resultados)
    validos = [r for r in resultados if r.get('valido_facturacion')]
    no_validos = [r for r in resultados if not r.get('valido_facturacion')]
    
    # Analizar causas de no validación
    causas = {
        'estado_no_activo': 0,
        'condicion_no_habido': 0,
        'consulta_fallida': 0,
        'error_api': 0,
        'otros': 0,
        'direccion_invalida': 0,
        'tipo_contribuyente_no_valido': 0
    }
    
    for ruc in no_validos:
        estado = ruc.get('estado', '')
        condicion = ruc.get('condicion', '')
        error = ruc.get('error', '')
        fuente = ruc.get('fuente', '')
        
        # Analizar causas según el tipo de error
        if error:
            if 'api_error' in fuente or 'excepcion' in fuente:
                causas['error_api'] += 1
            elif 'consulta_fallida' in error.lower() or 'error en lote' in error:
                causas['consulta_fallida'] += 1
            else:
                causas['otros'] += 1
        elif estado != 'ACTIVO' and estado not in ['', 'ERROR', 'DESCONOCIDO']:
            causas['estado_no_activo'] += 1
        elif condicion != 'HABIDO' and condicion not in ['', 'ERROR', 'DESCONOCIDO']:
            causas['condicion_no_habido'] += 1
        elif ruc.get('tipo_contribuyente') in ['EXTRANJERO_NO_DOMICILIADO', 'NO_DOMICILIADO']:
            causas['tipo_contribuyente_no_valido'] += 1
        elif not ruc.get('direccion') or len(str(ruc.get('direccion', '')).strip()) < 10:
            causas['direccion_invalida'] += 1
        else:
            causas['otros'] += 1
    
    # Calcular estadísticas de cache
    de_cache = sum(1 for r in resultados if r.get('cacheado', False))
    de_api = sum(1 for r in resultados if not r.get('cacheado', True))
    
    # Crear mensaje de advertencia si hay discrepancias
    advertencia = ''
    if total_esperado > total:
        advertencia = f'Faltan {total_esperado - total} registros de RUCs en los resultados.'
    elif total_procesado_api > 0 and total_procesado_api < total_esperado:
        advertencia = f'Solo {total_procesado_api} de {total_esperado} RUCs fueron procesados por la API.'
    
    return {
        'total_esperado': total_esperado,
        'total_procesado_api': total_procesado_api,
        'total_validados': total,
        'validos_facturacion': {
            'cantidad': len(validos),
            'porcentaje': (len(validos) / total * 100) if total > 0 else 0,
            'items': validos[:50]  # Limitar para no hacer JSON muy grande
        },
        'no_validos_facturacion': {
            'cantidad': len(no_validos),
            'porcentaje': (len(no_validos) / total * 100) if total > 0 else 0,
            'items': no_validos[:50],  # Limitar para no hacer JSON muy grande
            'causas': causas,
            'detalle_causas': {
                'estado_no_activo': [r['ruc'] for r in no_validos 
                                   if r.get('estado', '') != 'ACTIVO' 
                                   and r.get('estado', '') not in ['', 'ERROR', 'DESCONOCIDO']][:10],
                'condicion_no_habido': [r['ruc'] for r in no_validos 
                                       if r.get('condicion', '') != 'HABIDO' 
                                       and r.get('condicion', '') not in ['', 'ERROR', 'DESCONOCIDO']][:10],
                'error_api': [r['ruc'] for r in no_validos 
                            if 'api_error' in r.get('fuente', '') 
                            or 'excepcion' in r.get('fuente', '')][:10],
                'consulta_fallida': [r['ruc'] for r in no_validos 
                                   if 'consulta_fallida' in str(r.get('error', '')).lower() 
                                   or 'error en lote' in str(r.get('error', ''))][:10]
            }
        },
        'estadisticas_cache': {
            'total': total,
            'de_cache': de_cache,
            'de_api': de_api,
            'porcentaje_cache': (de_cache / total * 100) if total > 0 else 0,
            'porcentaje_api': (de_api / total * 100) if total > 0 else 0
        },
        'distribucion_lotes': {
            'lote_1': sum(1 for r in resultados if r.get('lote') == 1),
            'lote_2': sum(1 for r in resultados if r.get('lote') == 2),
            'sin_lote': sum(1 for r in resultados if not r.get('lote'))
        },
        'timestamp': timezone.now().isoformat(),
        'advertencia': advertencia,
        'resumen_rapido': {
            'total_rucs_solicitados': total_esperado,
            'total_rucs_procesados': total,
            'diferencia': total_esperado - total,
            'validos': len(validos),
            'no_validos': len(no_validos),
            'tasa_exito': (len(validos) / total_esperado * 100) if total_esperado > 0 else 0
        }
    }

def validar_rucs_con_cache(ruc_list, max_lotes=2):
    """
    Valida RUCs con cache en 3 niveles:
    1. Cache Django (por RUC individual y por lote)
    2. Validaciones previas en BD (si existe tabla de auditoría)
    3. API MIGO
    
    Args:
        ruc_list: Lista de RUCs a validar
        max_lotes: Máximo número de lotes a procesar
    
    Returns:
        dict con resultados de validación
    """
    print(f"\n🔍 VALIDANDO {len(ruc_list)} RUCS (máx {max_lotes} lotes)")
    print("="*50)

    client = MigoClient()
    resultados = []
    rucs_procesados_api = 0  # Contador para RUCs que llegaron de la API
    api_calls = 0

    # 1. Verificar cache del lote completo (igual que antes)
    ruc_list_sorted = sorted(ruc_list)
    lote_hash = hashlib.md5(json.dumps(ruc_list_sorted).encode()).hexdigest()
    cache_key_lote = f"validacion_lote_{lote_hash}"
    cached_lote = cache.get(cache_key_lote)
    if cached_lote:
        print(f"✅ Validación completa obtenida de cache (lote)")
        # Asegurar que el objeto del cache tiene la estructura esperada
        return cached_lote

    # 2. Verificar cache individual y preparar lista para API
    rucs_para_api = []
    for ruc in ruc_list:
        cache_key_individual = f"validacion_ruc_{ruc}"
        cached_individual = cache.get(cache_key_individual)
        if cached_individual:
            resultados.append(cached_individual)
        else:
            rucs_para_api.append(ruc)

    print(f"📊 Cache individual: {len(resultados)}/{len(ruc_list)} RUCs")

    if not rucs_para_api:
        consolidated = _consolidar_resultados(resultados, len(ruc_list), rucs_procesados_api)
        # GUARDAR EN CACHE: Asegurar que es serializable
        try:
            # Usar json.dumps/loads para forzar la serialización
            cache.set(cache_key_lote, consolidated, 3600)
            print("💾 Resultados consolidados guardados en cache (lote completo).")
        except Exception as e:
            print(f"⚠️  No se pudo guardar en cache: {e}")
        return consolidated

    # 3. Consultar API para RUCs faltantes
    print(f"🔍 Consultando API para {len(rucs_para_api)} RUCs...")
    tamano_lote = getattr(client.service, 'max_batch_size', 100)
    lotes = client._particionar_rucs_en_lotes(rucs_para_api, tamano_lote)
    lotes = lotes[:max_lotes]

    print(f"📦 Procesando {len(lotes)} lote(s)...")
    for i, lote in enumerate(lotes):
        print(f"  Lote {i+1}/{len(lotes)}: {len(lote)} RUCs")
        try:
            if i > 0:
                time.sleep(2)
            resultado_lote = client.consultar_ruc_masivo(lote)
            api_calls += 1

            if resultado_lote.get('success'):
                # ✅ CORRECCIÓN CRÍTICA: Contar RUCs en la respuesta
                resultados_api = resultado_lote.get('results', [])
                rucs_en_respuesta = len(resultados_api)
                rucs_procesados_api += rucs_en_respuesta
                print(f"    📄 API devolvió datos para {rucs_en_respuesta} RUCs")

                for ruc_data in resultados_api:
                    if isinstance(ruc_data, dict):
                        ruc = ruc_data.get('ruc', '')
                        if ruc:
                            es_valido = (
                                ruc_data.get('success', False) and
                                ruc_data.get('estado_del_contribuyente') == 'ACTIVO' and
                                ruc_data.get('condicion_de_domicilio') == 'HABIDO'
                            )
                            validacion = {
                                'ruc': ruc,
                                'razon_social': ruc_data.get('nombre_o_razon_social', ''),
                                'estado': ruc_data.get('estado_del_contribuyente', ''),
                                'condicion': ruc_data.get('condicion_de_domicilio', ''),
                                'valido_facturacion': es_valido,
                                'fuente': 'api_migo',
                                'cacheado': False,
                                'lote': i+1
                            }
                            resultados.append(validacion)
                            # ✅ GUARDAR EN CACHE INDIVIDUAL: Asegurar serialización
                            try:
                                # Crear una copia simple y serializable
                                cache_data = validacion.copy()
                                cache.set(f"validacion_ruc_{ruc}", cache_data, 86400)
                            except Exception as e:
                                print(f"       ⚠️  No se pudo cachear {ruc}: {e}")
            else:
                print(f"    ⚠️  Lote falló: {resultado_lote.get('error')}")
                # Crear entradas fallidas
                for ruc in lote:
                    resultados.append({
                        'ruc': ruc, 'valido_facturacion': False, 'error': 'Error en lote',
                        'fuente': 'api_error', 'cacheado': False, 'lote': i+1
                    })
                    rucs_procesados_api += 1  # Contar incluso los fallos

        except Exception as e:
            print(f"    ❌ Error en lote: {e}")
            for ruc in lote:
                resultados.append({
                    'ruc': ruc, 'valido_facturacion': False, 'error': str(e),
                    'fuente': 'excepcion', 'cacheado': False, 'lote': i+1
                })
                rucs_procesados_api += 1

    print(f"📊 API calls: {api_calls}. RUCs de API: {rucs_procesados_api}")

    # 4. Consolidar resultados
    resultados_consolidados = _consolidar_resultados(resultados, len(ruc_list), rucs_procesados_api)

    # ✅ GUARDAR LOTE EN CACHE: Preparar datos serializables
    try:
        # Estrategia: simplificar datos para cache
        cache_data = {
            'total_validados': resultados_consolidados['total_validados'],
            'validos_facturacion': {
                'cantidad': resultados_consolidados['validos_facturacion']['cantidad'],
                'porcentaje': resultados_consolidados['validos_facturacion']['porcentaje']
            },
            'no_validos_facturacion': {
                'cantidad': resultados_consolidados['no_validos_facturacion']['cantidad'],
                'porcentaje': resultados_consolidados['no_validos_facturacion']['porcentaje'],
                'causas': resultados_consolidados['no_validos_facturacion']['causas']
            },
            'timestamp': resultados_consolidados['timestamp']
        }
        cache.set(cache_key_lote, cache_data, 3600)
        print("💾 Resultados (versión cacheable) guardados en cache.")
    except Exception as e:
        print(f"⚠️  Error guardando lote en cache: {e}")

    return resultados_consolidados


def generar_reporte_facturacion(tipo_cambio, validacion_rucs):
    """
    Genera reporte completo de facturación
    
    Args:
        tipo_cambio: Datos de tipo de cambio
        validacion_rucs: Resultados de validación de RUCs
    """
    print("\n📊 REPORTE DE FACTURACIÓN")
    print("="*50)
    
    # Información del tipo de cambio
    print(f"\n💱 TIPO DE CAMBIO DEL DÍA:")
    print(f"   Fecha: {tipo_cambio.get('fecha', 'N/A')}")
    print(f"   Compra: S/ {tipo_cambio.get('compra', 0):.3f}")
    print(f"   Venta: S/ {tipo_cambio.get('venta', 0):.3f}")
    print(f"   Fuente: {tipo_cambio.get('fuente', 'N/A')}")
    
    if not tipo_cambio.get('success'):
        print(f"   ⚠️  ADVERTENCIA: {tipo_cambio.get('advertencia', '')}")
    
    # Resumen de validación de RUCs
    validos = validacion_rucs['validos_facturacion']
    no_validos = validacion_rucs['no_validos_facturacion']
    
    print(f"\n👥 VALIDACIÓN DE CLIENTES (RUCs):")
    print(f"   Total validados: {validacion_rucs['total_validados']}")
    print(f"   ✅ Válidos para facturación: {validos['cantidad']} ({validos['porcentaje']:.1f}%)")
    print(f"   ❌ No válidos: {no_validos['cantidad']} ({no_validos['porcentaje']:.1f}%)")
    
    if no_validos['cantidad'] > 0:
        print(f"\n🔍 CAUSAS DE NO VALIDACIÓN:")
        causas = no_validos.get('causas', {})
        for causa, cantidad in causas.items():
            if cantidad > 0:
                causa_formatted = causa.replace('_', ' ').title()
                print(f"   • {causa_formatted}: {cantidad}")
    
    # Estadísticas de cache
    stats = validacion_rucs.get('estadisticas_cache', {})
    if stats.get('de_cache', 0) > 0:
        print(f"\n💾 ESTADÍSTICAS DE CACHE:")
        print(f"   • De cache: {stats.get('de_cache', 0)}")
        print(f"   • De API: {stats.get('de_api', 0)}")
        porcentaje_cache = (stats.get('de_cache', 0) / stats.get('total', 1)) * 100
        print(f"   • Eficiencia cache: {porcentaje_cache:.1f}%")
    
    # Ejemplos de RUCs no válidos
    if no_validos['items']:
        print(f"\n📋 EJEMPLOS DE RUCS NO VÁLIDOS:")
        for i, ruc in enumerate(no_validos['items'][:5]):  # Mostrar primeros 5
            razon = ruc.get('razon_social', 'Sin razón social')[:40]
            estado = ruc.get('estado', 'DESCONOCIDO')
            condicion = ruc.get('condicion', 'DESCONOCIDO')
            
            print(f"   {i+1}. {ruc.get('ruc', '')}: {razon}...")
            print(f"      Estado: {estado}, Condición: {condicion}")
            
            if ruc.get('error'):
                print(f"      Error: {ruc['error'][:60]}...")
    
    # Cálculo de facturación hipotética
    if validos['cantidad'] > 0 and tipo_cambio.get('success'):
        print(f"\n💰 CÁLCULO HIPOTÉTICO DE FACTURACIÓN:")
        print(f"   Suponiendo factura promedio de USD 1,000 por cliente válido...")
        
        tc_compra = tipo_cambio.get('compra', 3.7)
        facturas_totales = validos['cantidad'] * 1000  # USD
        total_soles = facturas_totales * tc_compra
        igv_total = total_soles * 0.18
        
        print(f"   • Clientes válidos: {validos['cantidad']}")
        print(f"   • Facturación total: USD {facturas_totales:,.0f}")
        print(f"   • En Soles: S/ {total_soles:,.2f}")
        print(f"   • IGV (18%): S/ {igv_total:,.2f}")
        print(f"   • Total con IGV: S/ {total_soles + igv_total:,.2f}")

def guardar_resultados_json(tipo_cambio, validacion_rucs, filename=None):
    """
    Guarda todos los resultados en un archivo JSON
    
    Args:
        tipo_cambio: Datos de tipo de cambio
        validacion_rucs: Resultados de validación
        filename: Nombre personalizado del archivo
    """
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_facturacion_{timestamp}.json"
    
    results_dir = "api_test_results"
    os.makedirs(results_dir, exist_ok=True)
    
    filepath = os.path.join(results_dir, filename)
    
    datos_completos = {
        'metadata': {
            'generado_en': datetime.now().isoformat(),
            'proceso': 'validacion_facturacion',
            'version': '1.0'
        },
        'tipo_cambio': tipo_cambio,
        'validacion_rucs': validacion_rucs,
        'resumen': {
            'total_clientes_validados': validacion_rucs['total_validados'],
            'clientes_validos': validacion_rucs['validos_facturacion']['cantidad'],
            'clientes_no_validos': validacion_rucs['no_validos_facturacion']['cantidad'],
            'tipo_cambio_compra': tipo_cambio.get('compra'),
            'tipo_cambio_venta': tipo_cambio.get('venta')
        }
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(datos_completos, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Reporte guardado en: {filepath}")
    return filepath

def flujo_completo_facturacion(max_lotes=2):
    """
    Flujo completo de facturación:
    1. Obtener tipo de cambio del día (con cache)
    2. Obtener RUCs para validar (partners + casos especiales)
    3. Validar RUCs (con cache y máximo de lotes)
    4. Generar reporte
    5. Guardar resultados
    
    Args:
        max_lotes: Máximo número de lotes para consulta API
    """
    print("\n" + "="*60)
    print("🚀 FLUJO COMPLETO DE FACTURACIÓN")
    print("="*60)
    
    start_time = time.time()
    
    try:
        # 1. Obtener tipo de cambio
        print("\n📈 PASO 1: Tipo de cambio")
        tipo_cambio = obtener_tipo_cambio_dia()
        
        if not tipo_cambio.get('success'):
            print("⚠️  ADVERTENCIA: Usando tipo de cambio por defecto")
        
        # 2. Obtener RUCs para validar
        print("\n📋 PASO 2: Obteniendo RUCs para validación")
        rucs_data = obtener_rucs_para_validacion()
        
        if rucs_data['total'] == 0:
            print("❌ No hay RUCs para validar")
            return
        
        # 3. Validar RUCs con cache y límite de lotes
        print(f"\n✅ PASO 3: Validando RUCs (máx {max_lotes} lotes)")
        validacion_rucs = validar_rucs_con_cache(
            rucs_data['todos'], 
            max_lotes=max_lotes
        )
        
        # 4. Generar reporte
        print("\n📊 PASO 4: Generando reporte")
        generar_reporte_facturacion(tipo_cambio, validacion_rucs)
        
        # 5. Guardar resultados
        print("\n💾 PASO 5: Guardando resultados")
        archivo = guardar_resultados_json(tipo_cambio, validacion_rucs)
        
        elapsed_time = time.time() - start_time
        
        print(f"\n✅ FLUJO COMPLETADO EN {elapsed_time:.1f} SEGUNDOS")
        print(f"📁 Resultados en: {archivo}")
        
        return {
            'success': True,
            'tiempo_total': elapsed_time,
            'tipo_cambio': tipo_cambio.get('success', False),
            'rucs_validados': validacion_rucs['total_validados'],
            'rucs_validos': validacion_rucs['validos_facturacion']['cantidad'],
            'archivo_resultados': archivo
        }
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ ERROR EN EL FLUJO DESPUÉS DE {elapsed_time:.1f}s")
        print(f"   Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'tiempo_total': elapsed_time
        }

def main():
    """Función principal con menú interactivo"""
    print("\n" + "="*60)
    print("🏦 SISTEMA DE VALIDACIÓN PARA FACTURACIÓN")
    print("="*60)
    
    print("\n🔧 OPCIONES DISPONIBLES:")
    print("1. Flujo completo de facturación (con límite de 2 lotes)")
    print("2. Solo obtener tipo de cambio")
    print("3. Solo validar RUCs")
    print("4. Generar reporte desde archivo JSON")
    print("5. Limpiar cache")
    print("0. Salir")
    
    try:
        opcion = input("\nSeleccione opción (0-5): ").strip()
        
        if opcion == "1":
            print("\n▶️  INICIANDO FLUJO COMPLETO DE FACTURACIÓN")
            resultado = flujo_completo_facturacion(max_lotes=2)
            
            if resultado.get('success'):
                print(f"\n🎉 ¡Proceso completado exitosamente!")
                print(f"⏱️  Tiempo total: {resultado['tiempo_total']:.1f}s")
            else:
                print(f"\n❌ Proceso falló: {resultado.get('error', 'Error desconocido')}")
                
        elif opcion == "2":
            print("\n💱 OBTENIENDO TIPO DE CAMBIO")
            tipo_cambio = obtener_tipo_cambio_dia()
            print(f"\n✅ Resultado:")
            print(json.dumps(tipo_cambio, indent=2, ensure_ascii=False))
            
        elif opcion == "3":
            print("\n🔍 VALIDANDO RUCS")
            rucs_data = obtener_rucs_para_validacion()
            validacion = validar_rucs_con_cache(rucs_data['todos'], max_lotes=2)
            print(f"\n✅ Resultado de validación:")
            print(f"Total: {validacion['total_validados']}")
            print(f"Válidos: {validacion['validos_facturacion']['cantidad']}")
            print(f"No válidos: {validacion['no_validos_facturacion']['cantidad']}")
            
        elif opcion == "4":
            import glob
            results_dir = "api_test_results"
            json_files = glob.glob(f"{results_dir}/reporte_facturacion_*.json")
            
            if json_files:
                latest = max(json_files, key=os.path.getctime)
                print(f"\n📄 Cargando archivo más reciente: {os.path.basename(latest)}")
                
                with open(latest, 'r', encoding='utf-8') as f:
                    datos = json.load(f)
                
                generar_reporte_facturacion(
                    datos['tipo_cambio'],
                    datos['validacion_rucs']
                )
            else:
                print("❌ No se encontraron archivos de reporte")
                
        elif opcion == "5":
            print("\n🧹 LIMPIANDO CACHE...")
            try:
                cache.clear()
                print("✅ Cache limpiado exitosamente")
            except Exception as e:
                print(f"❌ Error limpiando cache: {str(e)}")
                
        elif opcion == "0":
            print("\n👋 Saliendo...")
            
        else:
            print("❌ Opción no válida")
            
    except KeyboardInterrupt:
        print("\n\n👋 Operación cancelada por el usuario")
    except Exception as e:
        print(f"\n❌ Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Verificar que Django esté configurado
    try:
        from django.conf import settings
        if not settings.configured:
            print("❌ Django no está configurado")
            sys.exit(1)
    except:
        print("❌ Error al verificar configuración de Django")
        sys.exit(1)
    
    main()