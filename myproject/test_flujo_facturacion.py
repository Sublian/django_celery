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
from api_service.services.migo_service import MigoAPIClient as MigoClient
from api_service.services.cache_service import APICacheService
from billing.models import Currency, CurrencyRate, Partner, Company

def mostrar_contenido_cache():
    """
    Muestra el contenido actual del cache para depuración
    """
    print("\n" + "="*60)
    print("🔍 CONTENIDO DEL CACHE - DEBUG")
    print("="*60)
    
    from django.core.cache import cache
    import json
    
    # Obtener todas las claves del cache (esto depende del backend)
    # Para Redis: cache.keys('*')
    # Para memcached/local: no hay forma directa, necesitamos saber las claves
    
    # Como alternativa, podemos mostrar claves conocidas
    claves_conocidas = []
    
    # Claves de tipo de cambio (últimos 7 días)
    from datetime import date, timedelta
    for i in range(7):
        fecha = date.today() - timedelta(days=i)
        claves_conocidas.append(f"tipo_cambio_{fecha.isoformat()}")
    
    # También podemos intentar obtener stats del APICacheService
    try:
        stats = APICacheService.get_stats()
        print(f"\n📊 ESTADÍSTICAS DEL CACHE SERVICE:")
        print(f"  Configuración TTL: {stats.get('ttl_config', {})}")
        print(f"  Prefijos: {stats.get('prefixes', {})}")
    except Exception as e:
        print(f"⚠️  No se pudieron obtener estadísticas: {str(e)}")
    
    print(f"\n🔍 BUSCANDO CLAVES CONOCIDAS EN CACHE:")
    cache_hits = 0
    cache_misses = 0
    
    for clave in claves_conocidas:
        valor = cache.get(clave)
        if valor:
            cache_hits += 1
            print(f"\n✅ {clave}:")
            if isinstance(valor, dict):
                for k, v in valor.items():
                    if k not in ['cached_at', 'expires_at', 'metadata']:
                        print(f"   • {k}: {v}")
                if 'cached_at' in valor:
                    print(f"   • cached_at: {valor['cached_at']}")
                if 'expires_at' in valor:
                    print(f"   • expires_at: {valor['expires_at']}")
            else:
                print(f"   Tipo: {type(valor).__name__}, Valor: {str(valor)[:100]}...")
        else:
            cache_misses += 1
            print(f"❌ {clave}: NO EN CACHE")
    
    print(f"\n📊 RESUMEN:")
    print(f"  Encontradas en cache: {cache_hits}")
    print(f"  No encontradas: {cache_misses}")
    
    # Mostrar también algunas claves de RUC si existen
    print(f"\n🔍 BUSCANDO ALGUNAS CLAVES DE RUC (ejemplos):")
    
    # Intentar algunas claves de ejemplo
    ejemplos_ruc = [
        'ruc_20557425889',
        'ruc_20603274742', 
        'ruc_20100035370'
    ]
    
    for clave_ruc in ejemplos_ruc:
        valor = cache.get(clave_ruc)
        if valor:
            print(f"✅ {clave_ruc}: Existe en cache")
            if isinstance(valor, dict) and 'razon_social' in valor:
                print(f"   • Razon social: {valor['razon_social'][:50]}...")
                print(f"   • Estado: {valor.get('estado', 'N/A')}")
                print(f"   • Válido facturación: {valor.get('valido_facturacion', 'N/A')}")
        else:
            print(f"❌ {clave_ruc}: NO en cache")
    
    return {
        'cache_hits': cache_hits,
        'cache_misses': cache_misses,
        'claves_revisadas': len(claves_conocidas)
    }

def obtener_tipo_cambio_dia(force_api=False):
    """
    Obtiene el tipo de cambio del día con cache en 3 niveles:
    1. APICacheService (15 minutos)
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
    fecha_str = hoy.isoformat()
    
    # 1. Verificar APICacheService (15 minutos)
    if not force_api:
        cache_data = APICacheService.get_tipo_cambio(fecha_str)
        if cache_data:
            print(f"✅ Tipo cambio obtenido de cache service")
            return cache_data
    
    # 2. Verificar base de datos
    try:
        # Buscar USD en Currency - Ajustado según tu modelo
        moneda_usd = Currency.objects.filter(name='USD').first()
        
        if moneda_usd:
            # Usar el campo correcto según tu modelo: date_rate
            tipo_cambio_db = CurrencyRate.objects.filter(
                currency=moneda_usd,
                date_rate=hoy
            ).order_by('-date_rate').first()
            
            if tipo_cambio_db:
                print(f"✅ Tipo cambio obtenido de base de datos")
                resultado = {
                    'success': True,
                    'fecha': fecha_str, 
                    'compra': float(tipo_cambio_db.purchase_rate),
                    'venta': float(tipo_cambio_db.sale_rate),
                    'fuente': 'database',
                    'currency_rate_id': tipo_cambio_db.id
                }
                
                # Guardar en APICacheService
                APICacheService.set_tipo_cambio(fecha_str, resultado)
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
            
            # Normalizar nombres de campos de la API
            # La API puede devolver 'precio_compra'/ 'precio_venta' o 'compra'/'venta'
            compra = resultado.get('precio_compra') or resultado.get('compra', 0)
            venta = resultado.get('precio_venta') or resultado.get('venta', 0)
            
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
                
                # Verificar que existe una Company
                company = Company.objects.first()
                if not company:
                    raise Exception("No hay compañía configurada en la base de datos")
                
                currency_rate = CurrencyRate.objects.create(
                    currency=moneda_usd,
                    date_rate=hoy,
                    purchase_rate=compra,
                    sale_rate=venta,
                    company=company,
                )
                
                resultado = {
                    'success': True,
                    'fecha': fecha_str,
                    'compra': float(compra),
                    'venta': float(venta),
                    'fuente': 'api_migo_latest',
                    'currency_rate_id': currency_rate.id
                }
                
            except Exception as e:
                print(f"⚠️  Error guardando en BD: {str(e)}")
                # Aún así devolver los datos de la API
                resultado = {
                    'success': True,
                    'fecha': fecha_str,
                    'compra': float(compra),
                    'venta': float(venta),
                    'fuente': 'api_migo_latest_no_save',
                    'advertencia': f'No se guardó en BD: {str(e)}'
                }
            
            # Guardar en APICacheService
            APICacheService.set_tipo_cambio(fecha_str, resultado)
            return resultado
        
    except Exception as e:
        print(f"❌ Error API latest: {str(e)}")
    
    # Si latest falla, intentar con fecha específica
    try:
        resultado_api = client.consultar_tipo_cambio_fecha(fecha_str)
        
        if resultado_api.get('success'):
            print(f"✅ Tipo cambio obtenido de API MIGO (fecha específica)")
            
            # Normalizar campos
            compra = resultado_api.get('precio_compra') or resultado_api.get('compra', 0)
            venta = resultado_api.get('precio_venta') or resultado_api.get('venta', 0)
            
            resultado = {
                'success': True,
                'fecha': fecha_str,
                'compra': float(compra),
                'venta': float(venta),
                'fuente': 'api_migo_fecha'
            }
            
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
                if company:
                    currency_rate = CurrencyRate.objects.create(
                        currency=moneda_usd,
                        date_rate=hoy,
                        purchase_rate=compra,
                        sale_rate=venta,
                        company=company,
                    )
                    resultado['currency_rate_id'] = currency_rate.id
                else:
                    resultado['fuente'] = 'api_migo_fecha_no_company'
                    
            except Exception as e:
                print(f"⚠️  Error guardando en BD: {str(e)}")
                resultado['fuente'] = 'api_migo_fecha_no_save'
            
            # Guardar en APICacheService
            APICacheService.set_tipo_cambio(fecha_str, resultado)
            return resultado
        
    except Exception as e:
        print(f"❌ Error API fecha específica: {str(e)}")
    
    # Si todo falla, usar último disponible en BD
    print(f"⚠️  Usando último tipo cambio disponible en BD")
    try:
        # Buscar por nombre 'USD' en lugar de code
        moneda_usd = Currency.objects.filter(name='USD').first()
        if moneda_usd:
            ultimo = CurrencyRate.objects.filter(
                currency=moneda_usd
            ).order_by('-date_rate').first()
            
            if ultimo:
                resultado = {
                    'success': True,
                    'fecha': ultimo.date_rate.isoformat(),
                    'compra': float(ultimo.purchase_rate),
                    'venta': float(ultimo.sale_rate),
                    'fuente': 'ultimo_disponible',
                    'currency_rate_id': ultimo.id,
                    'advertencia': f'Tipo cambio del {ultimo.date_rate}, no del día actual'
                }
                APICacheService.set_tipo_cambio(fecha_str, resultado)
                return resultado
    except Exception as e:
        print(f"⚠️  Error buscando último en BD: {str(e)}")
    
    # Último recurso: valor por defecto
    print(f"⚠️  Usando valor por defecto")
    resultado_default = {
        'success': False,
        'fecha': fecha_str,
        'compra': 3.70,
        'venta': 3.75,
        'fuente': 'valor_por_defecto',
        'advertencia': 'No se pudo obtener tipo cambio real'
    }
    APICacheService.set_tipo_cambio(fecha_str, resultado_default)
    return resultado_default

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

def _consolidar_resultados(resultados, total_esperado, total_procesado_api, rucs_omitidos=None):
    """
    Consolidar resultados con manejo de RUCs omitidos
    """
    rucs_omitidos = rucs_omitidos or []
    
    # ... (código existente para contar y clasificar) ...
    
    # Agregar sección para RUCs omitidos
    resultados_consolidados = {
        # ... (tus campos existentes) ...
        'rucs_omitidos': {
            'cantidad': len(rucs_omitidos),
            'items': rucs_omitidos[:20],  # Limitar para no hacer muy grande
            'porcentaje': (len(rucs_omitidos) / total_esperado * 100) if total_esperado > 0 else 0
        },
        'resumen_ejecucion': {
            'total_solicitado': total_esperado,
            'total_procesado': len(resultados),
            'diferencia': total_esperado - len(resultados),
            'cache_hits': sum(1 for r in resultados if r.get('cacheado', False)),
            'api_calls_efectivas': total_procesado_api - len(rucs_omitidos),
            'rucs_omitidos_finales': len(rucs_omitidos)
        }
    }
    
    return resultados_consolidados

def validar_rucs_con_cache(ruc_list, max_lotes=2, max_reintentos=2):
    """
    Valida RUCs con cache y reintentos resilientes para RUCs omitidos con cache en 3 niveles:
    1. Cache Django (por RUC individual y por lote)
    2. Validaciones previas en BD (si existe tabla de auditoría)
    3. API MIGO
    Args:
        ruc_list: Lista de RUCs a validar
        max_lotes: Máximo número de lotes a procesar
        max_reintentos: Máximo número de reintentos para RUCs problemáticos
    Returns:
        dict con resultados de validación
    """
    print(f"\n🔍 VALIDANDO {len(ruc_list)} RUCS (máx {max_lotes} lotes, {max_reintentos} reintentos)")
    print("="*50)

    client = MigoClient()
    resultados = []
    rucs_procesados_api = 0  # Contador para RUCs que llegaron de la API
    api_calls = 0
    reintentos_realizados = 0

    # 1. Verificar cache del lote completo
    cache_lote = APICacheService.get_ruc_lote(ruc_list)
    if cache_lote:
        print(f"✅ Validación completa obtenida de cache (lote)")
        return cache_lote.get('results')

    # 2. Verificar cache individual
    rucs_para_api = []
    cache_hits = 0
    
    for ruc in ruc_list:
        cache_data = APICacheService.get_ruc_individual(ruc)
        if cache_data:
            cache_hits += 1
            resultados.append({
                **cache_data,
                'cacheado': True,
                'fuente': 'cache_individual'
            })
        else:
            rucs_para_api.append(ruc)
    
    print(f"📊 Cache individual: {cache_hits}/{len(ruc_list)} RUCs")
    
     # Si todos estaban en cache, guardar y retornar
    if not rucs_para_api:
        consolidated = _consolidar_resultados(resultados, len(ruc_list), 0)
        APICacheService.set_ruc_lote(ruc_list, consolidated)
        return consolidated
    
    # 3. Procesar lotes iniciales
    tamano_lote = getattr(client.service, 'max_batch_size', 100)
    lotes = client._particionar_rucs_en_lotes(rucs_para_api, tamano_lote)
    lotes = lotes[:max_lotes]
    
    print(f"📦 Procesando {len(lotes)} lote(s) inicial(es)...")

    # RUCs que fueron enviados pero no recibidos (para reintento)
    rucs_omitidos = []
    
    for i, lote in enumerate(lotes):
        print(f"  Lote {i+1}/{len(lotes)}: {len(lote)} RUCs")
        
        try:
            if i > 0:
                time.sleep(3)  # Rate limit más corto para lotes iniciales
            
            resultado_lote = client.consultar_ruc_masivo(lote)
            api_calls += 1
            
            if resultado_lote.get('success'):
                # Procesar RUCs recibidos
                rucs_recibidos = set()
                for ruc_data in resultado_lote.get('results', []):
                    if isinstance(ruc_data, dict):
                        ruc = ruc_data.get('ruc')
                        if ruc:
                            rucs_recibidos.add(ruc)
                            
                            # Validar y crear registro
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
                                'direccion': ruc_data.get('direccion', ''),
                                'actualizado_en': ruc_data.get('actualizado_en', ''),
                                'valido_facturacion': es_valido,
                                'fuente': 'api_migo',
                                'cacheado': False,
                                'lote': f"inicial_{i+1}"
                            }
                            
                            resultados.append(validacion)
                            rucs_procesados_api += 1
                            
                            # Guardar en cache individual
                            APICacheService.set_ruc_individual(ruc, validacion)
                
                # Identificar RUCs omitidos en este lote
                for ruc_enviado in lote:
                    if ruc_enviado not in rucs_recibidos:
                        print(f"    ⚠️  RUC omitido: {ruc_enviado}")
                        rucs_omitidos.append(ruc_enviado)
                        
                        # Crear registro de error
                        resultados.append({
                            'ruc': ruc_enviado,
                            'razon_social': '',
                            'estado': 'OMITIDO',
                            'condicion': 'OMITIDO',
                            'valido_facturacion': False,
                            'error': 'RUC omitido en respuesta inicial de API',
                            'fuente': 'api_omitido',
                            'cacheado': False,
                            'lote': f"inicial_{i+1}"
                        })
            
            else:
                # Si falla todo el lote, agregar todos como fallidos
                print(f"    ❌ Lote falló: {resultado_lote.get('error')}")
                for ruc in lote:
                    resultados.append({
                        'ruc': ruc,
                        'razon_social': '',
                        'estado': 'ERROR_LOTE',
                        'condicion': 'ERROR_LOTE',
                        'valido_facturacion': False,
                        'error': resultado_lote.get('error', 'Error en lote'),
                        'fuente': 'error_lote',
                        'cacheado': False,
                        'lote': f"inicial_{i+1}_error"
                    })
        
        except Exception as e:
            print(f"    ❌ Excepción en lote: {str(e)}")
            for ruc in lote:
                resultados.append({
                    'ruc': ruc,
                    'razon_social': '',
                    'estado': 'EXCEPCION',
                    'condicion': 'EXCEPCION',
                    'valido_facturacion': False,
                    'error': str(e),
                    'fuente': 'excepcion',
                    'cacheado': False,
                    'lote': f"inicial_{i+1}_excepcion"
                })
    
    # 4. FASE RESILIENTE: Reintentar RUCs omitidos
    if rucs_omitidos and reintentos_realizados < max_reintentos:
        print(f"\n🔄 FASE RESILIENTE: Reintentando {len(rucs_omitidos)} RUCs omitidos")
        print("="*40)
        
        # Estrategia: intentar en lotes más pequeños o individualmente
        estrategias = [
            {'nombre': 'lote_5', 'tamano': 5, 'desc': 'Lotes de 5'},
            {'nombre': 'individual', 'tamano': 1, 'desc': 'Individual'}
        ]
        
        for estrategia in estrategias:
            if not rucs_omitidos:
                break
                
            print(f"\n  🔧 Estrategia: {estrategia['desc']}")
            
            # Particionar RUCs omitidos según estrategia
            lotes_reintento = client._particionar_rucs_en_lotes(
                rucs_omitidos, 
                estrategia['tamano']
            )
            
            for i, lote_reintento in enumerate(lotes_reintento):
                if reintentos_realizados >= max_reintentos:
                    break
                    
                print(f"    Reintento {reintentos_realizados + 1}: {len(lote_reintento)} RUCs")
                
                try:
                    time.sleep(2)  # Esperar más entre reintentos
                    
                    resultado_reintento = client.consultar_ruc_masivo(lote_reintento)
                    api_calls += 1
                    reintentos_realizados += 1
                    
                    if resultado_reintento.get('success'):
                        rucs_exitosos = []
                        
                        for ruc_data in resultado_reintento.get('results', []):
                            if isinstance(ruc_data, dict):
                                ruc = ruc_data.get('ruc')
                                if ruc and ruc in rucs_omitidos:
                                    # Encontrar y actualizar el registro existente
                                    for idx, resultado in enumerate(resultados):
                                        if resultado.get('ruc') == ruc:
                                            # Actualizar con datos exitosos
                                            es_valido = (
                                                ruc_data.get('success', False) and
                                                ruc_data.get('estado_del_contribuyente') == 'ACTIVO' and
                                                ruc_data.get('condicion_de_domicilio') == 'HABIDO'
                                            )
                                            
                                            resultados[idx] = {
                                                'ruc': ruc,
                                                'razon_social': ruc_data.get('nombre_o_razon_social', ''),
                                                'estado': ruc_data.get('estado_del_contribuyente', ''),
                                                'condicion': ruc_data.get('condicion_de_domicilio', ''),
                                                'direccion': ruc_data.get('direccion', ''),
                                                'actualizado_en': ruc_data.get('actualizado_en', ''),
                                                'valido_facturacion': es_valido,
                                                'fuente': 'api_migo_reintento',
                                                'cacheado': False,
                                                'lote': f"reintento_{reintentos_realizados}"
                                            }
                                            
                                            rucs_exitosos.append(ruc)
                                            rucs_procesados_api += 1
                                            
                                            # Guardar en cache
                                            APICacheService.set_ruc_individual(ruc, resultados[idx])
                                            break
                        
                        # Remover RUCs exitosos de la lista de omitidos
                        rucs_omitidos = [r for r in rucs_omitidos if r not in rucs_exitosos]
                        
                        if rucs_exitosos:
                            print(f"      ✅ Exitosos: {len(rucs_exitosos)} RUCs")
                    
                    else:
                        print(f"      ⚠️  Reintento falló")
                
                except Exception as e:
                    print(f"      ❌ Error en reintento: {str(e)}")
                    reintentos_realizados += 1
        
        # Si aún quedan RUCs omitidos después de los reintentos
        if rucs_omitidos:
            print(f"\n⚠️  {len(rucs_omitidos)} RUCs permanecen omitidos después de {max_reintentos} reintentos")
            for ruc in rucs_omitidos[:10]:
                print(f"  • {ruc}")
    
    print(f"\n📊 RESUMEN EJECUCIÓN:")
    print(f"  • API calls totales: {api_calls}")
    print(f"  • Reintentos realizados: {reintentos_realizados}")
    print(f"  • RUCs procesados por API: {rucs_procesados_api}")
    print(f"  • RUCs de cache: {cache_hits}")
    print(f"  • RUCs omitidos persistentes: {len(rucs_omitidos)}")
    
    # 5. Consolidar resultados finales
    resultados_consolidados = _consolidar_resultados(
        resultados, 
        len(ruc_list), 
        rucs_procesados_api,
        rucs_omitidos
    )
    
    # 6. Guardar lote completo en cache
    APICacheService.set_ruc_lote(ruc_list, resultados_consolidados)
    
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
    print("6. Mostrar contenido del cache (DEBUG)")
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
                
        elif opcion == "6":
            print("\n🔍 MOSTRANDO CONTENIDO DEL CACHE...")
            resultado = mostrar_contenido_cache()
            print(f"\n✅ Revisión de cache completada")
                
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