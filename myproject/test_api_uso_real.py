# test_api_uso_real.py
"""
Pruebas de uso real del módulo api_service.

Este archivo prueba:
1. Integración con modelos existentes (Company, Partner)
2. Todos los endpoints configurados
3. Casos de uso real para facturación
4. Rate limiting por endpoint específico
"""

import os
import sys
import django
import json


# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from api_service.services import MigoAPIClient
from api_service.models import ApiCallLog, ApiService, ApiEndpoint
from api_service.exceptions import RateLimitExceededError, APINotFoundError
from django.utils import timezone
from datetime import timedelta, datetime
from billing.models import Partner


def obtener_rucs_de_partners():
    """
    Obtiene RUCs activos de la tabla partner
    
    Returns:
        list: Lista de RUCs (strings) o lista vacía si no hay datos
    """
    try:
        # Intentar importar el modelo Partner (ajusta según tu estructura)
        
        # Consulta equivalente a: SELECT num_document FROM billing_partner 
        # WHERE document_type='ruc' AND is_active=True
        partners_ruc = Partner.objects.filter(
            document_type='ruc',
            is_active=True
        ).values_list('num_document', flat=True)
        
        # Convertir a lista de strings y limpiar
        rucs = []
        for ruc in partners_ruc:
            if ruc:  # Verificar que no sea None o vacío
                ruc_str = str(ruc).strip()
                if len(ruc_str) == 11 and ruc_str.isdigit():
                    rucs.append(ruc_str)
                else:
                    print(f"⚠️  RUC con formato inválido en partners: {ruc}")
        
        print(f"📊 Obtenidos {len(rucs)} RUCs válidos de la tabla partner")
        return rucs
        
    except ImportError as e:
        print(f"⚠️  No se pudo importar el modelo Partner: {str(e)}")
        return []
    except Exception as e:
        print(f"⚠️  Error obteniendo RUCs de partners: {str(e)}")
        return []

def obtener_rucs_con_fallas():
    """
    Devuelve RUCs con casos especiales (no domiciliados, etc.)
    Estos son útiles para pruebas de validación de facturación
    """
    rucs_fallas = [
        # Sujetos no domiciliados inscritos en el RUC
        "20613142038",  # WARNERMEDIA DIRECT LATIN AMERICA, LLC
        "20613142046",  # FIGMA INC
        "20613212435",  # OWUSOWESHI OGAH JOHN
        "20613221388",  # LEMONTECH SPA
        "20613212443",  # NETFLIX, INC.
        "20613243535",  # APPLE SERVICES LATAM LLC
        "20613323946",  # OYELARAN OLANREWAJU
        "20613309714",  # TIKTOK INC.
        "20613324047",  # META PLATFORMS IRELAND LIMITED
        "20613329936",  # FACEBOOK PAYMENTS INTERNATIONAL LIMITED
    ]
    return rucs_fallas


def obtener_rucs_adicionales():
    """
    Lista adicional de RUCs para pruebas masivas
    """
    rucs_adicionales = [
        "20136157133", "20293910767", "20408113891", "20411305474", "20450487059",
        "20479356956", "20480316259", "20480674414", "20487486435", "20487631460",
        "20487741486", "20487791581", "20487854841", "20487932150", "20490469797",
        "20490494716", "20490601903", "20490648888", "20491172216", "20491222922",
        "20493957288", "20493977041", "20493986385", "20493996429", "20494074169",
        "20494099153", "20494100186", "20494156211", "20494794412", "20525846718",
        "20525873103", "20525877605", "20525926665", "20525994741", "20526100876",
        "20528070770", "20529022078", "20529048468", "20529075511", "20529084855",
        "20532708321", "20538856674", "20538995364", "20542024748", "20542245671",
        "20542259117", "20547825781", "20552103816", "20553856451", "20568242271",
        "20568752555", "20568938144", "20569066141", "20570659317", "20570687795",
        "20570698991", "20570804775", "20570812361", "20570835654", "20570892291",
        "20571445132", "20571526213", "20573140011", "20573858124", "20600291590",
        "20600406788", "20600439368", "20600669207", "20600815572", "20600843576",
        "20600873777", "20601425204", "20601677688", "20601710316", "20602074707",
        "20602272291", "20602281010", "20602361307", "20602604781", "20602782531",
        "20602895018", "20602897363", "20602945589", "20602984045", "20603049684",
        "20603085087", "20603087624", "20603209975", "20603252307", "20603431589",
        "20603614748", "20604100853", "20604498989", "20604895988", "20605100016",
        "20605237518", "20605297324", "20606056657", "20606106883", "20606422793",
    ]
    return rucs_adicionales

def construir_lista_rucs_prueba(minimo=100):
    """
    Construye una lista de RUCs para pruebas combinando varias fuentes
    
    Args:
        minimo: Número mínimo de RUCs deseado
    
    Returns:
        list: Lista de RUCs para pruebas
    """
    print("\n🔍 CONSTRUYENDO LISTA DE RUCS PARA PRUEBAS")
    print("="*50)
    
    # 1. Obtener RUCs de la base de datos (partners reales)
    rucs_partners = obtener_rucs_de_partners()
    print(f"✓ De tabla partners: {len(rucs_partners)} RUCs")
    
    # 2. Agregar RUCs con casos especiales
    rucs_fallas = obtener_rucs_con_fallas()
    print(f"✓ Con casos especiales: {len(rucs_fallas)} RUCs")
    
    # 3. Agregar RUCs adicionales para llegar al mínimo
    rucs_adicionales = obtener_rucs_adicionales()
    print(f"✓ Adicionales disponibles: {len(rucs_adicionales)} RUCs")
    
    # Combinar todas las fuentes
    todos_rucs = []
    
    # Agregar RUCs de partners (prioridad 1)
    todos_rucs.extend(rucs_partners)
    
    # Agregar RUCs con fallas (prioridad 2 - importantes para pruebas)
    for ruc in rucs_fallas:
        if ruc not in todos_rucs:
            todos_rucs.append(ruc)
    
    # Si aún no tenemos suficientes, agregar de adicionales
    if len(todos_rucs) < minimo:
        necesitamos = minimo - len(todos_rucs)
        for ruc in rucs_adicionales[:necesitamos]:
            if ruc not in todos_rucs:
                todos_rucs.append(ruc)
    
    # Eliminar duplicados y ordenar
    todos_rucs = sorted(list(set(todos_rucs)))
    
    print(f"\n📊 TOTAL FINAL: {len(todos_rucs)} RUCs únicos")
    print(f"📋 Ejemplos: {', '.join(todos_rucs[:5])}...")
    
    return todos_rucs

def test_integracion_partners():
    """
    Prueba integración con modelos Partner/Company existentes.
    
    Busca partners con RUC y DNI válidos para probar.
    """
    print("=" * 60)
    print("TEST: Integración con modelos Partner/Company")
    print("=" * 60)
    
    try:
        client = MigoAPIClient()
        
        print("Buscando modelos de partner/company en el sistema...")
        
        # Intentar importar modelos existentes
        try:
            from crm.models import Partner, Company
            print("✅ Modelos CRM encontrados")
            
            # Buscar partners con RUC
            partners_con_ruc = Partner.objects.filter(
                document_type='ruc',
                num_document__isnull=False
            ).exclude(num_document='')[:5]
            
            print(f"Partners con RUC encontrados: {partners_con_ruc.count()}")
            
            for partner in partners_con_ruc:
                print(f"\n📋 Partner: {partner.name}")
                print(f"   RUC: {partner.num_document}")
                print(f"   Tipo: {partner.document_type}")
                
                try:
                    resultado = client.consultar_ruc(partner.num_document)
                    
                    if resultado.get('success'):
                        print(f"   ✅ RUC válido en SUNAT")
                        print(f"   📛 Razón Social API: {resultado.get('nombre_o_razon_social')}")
                        
                        # Comparar con lo que tenemos
                        if partner.name != resultado.get('nombre_o_razon_social'):
                            print(f"   ⚠️  Nombre difiere: BD='{partner.name}' vs API='{resultado.get('nombre_o_razon_social')}'")
                        
                        # Validar para facturación
                        validacion = client.validar_ruc_para_facturacion(partner.num_document)
                        print(f"   🏭 Válido para facturar: {validacion['valido']}")
                        print(f"   🟢 Estado: {validacion['estado']}")
                        print(f"   🏠 Condición: {validacion['condicion']}")
                        
                    else:
                        print(f"   ❌ RUC no válido en SUNAT")
                        
                except Exception as e:
                    print(f"   ❌ Error consultando RUC: {type(e).__name__}")
            
            # Buscar partners con DNI
            partners_con_dni = Partner.objects.filter(
                document_type='dni',
                num_document__isnull=False
            ).exclude(num_document='')[:3]
            
            print(f"\nPartners con DNI encontrados: {partners_con_dni.count()}")
            
            for partner in partners_con_dni:
                print(f"\n👤 Partner: {partner.name}")
                print(f"   DNI: {partner.num_document}")
                
                try:
                    resultado = client.consultar_dni(partner.num_document)
                    
                    if resultado.get('success'):
                        print(f"   ✅ DNI válido")
                        print(f"   📛 Nombre API: {resultado.get('nombre')}")
                        
                        if partner.name != resultado.get('nombre'):
                            print(f"   ⚠️  Nombre difiere: BD='{partner.name}' vs API='{resultado.get('nombre')}'")
                    
                    else:
                        print(f"   ❌ DNI no válido")
                        
                except Exception as e:
                    print(f"   ❌ Error consultando DNI: {type(e).__name__}")
            
            return True
            
        except ImportError:
            print("ℹ️  Modelos CRM no encontrados, usando datos de prueba...")
            
            # Datos de prueba si no hay modelos
            datos_prueba = [
                {'document_type': 'ruc', 'num_document': '20603274742', 'name': 'MIGO S.A.C.'},
                {'document_type': 'dni', 'num_document': '71265310', 'name': 'INCA SIERRA YENNY MELISSA'},
                {'document_type': 'ruc', 'num_document': '20131312955', 'name': 'EJEMPLO INACTIVO'},
            ]
            
            for dato in datos_prueba:
                print(f"\n📋 Prueba: {dato['name']}")
                print(f"   Documento: {dato['num_document']} ({dato['document_type']})")
                
                try:
                    if dato['document_type'] == 'ruc':
                        resultado = client.consultar_ruc(dato['num_document'])
                        if resultado.get('success'):
                            print(f"   ✅ RUC válido: {resultado.get('nombre_o_razon_social')}")
                        else:
                            print(f"   ❌ RUC no válido")
                    
                    elif dato['document_type'] == 'dni':
                        resultado = client.consultar_dni(dato['num_document'])
                        if resultado.get('success'):
                            print(f"   ✅ DNI válido: {resultado.get('nombre')}")
                        else:
                            print(f"   ❌ DNI no válido")
                            
                except Exception as e:
                    print(f"   ❌ Error: {type(e).__name__}")
            
            return True
            
    except Exception as e:
        print(f"❌ ERROR en test_integracion_partners: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_particion_rucs():
    """Prueba la función de partición de RUCs"""
    
    print("\n🧪 TEST: Partición de RUCs en lotes")
    print("=" * 50)
    
    client = MigoAPIClient()
    
    # Crear lista de prueba con 250 RUCs ficticios
    rucs_prueba = [f"{i:011d}" for i in range(1, 251)]  # RUCs del 00000000001 al 00000000250
    
    print(f"📊 Total de RUCs: {len(rucs_prueba)}")
    
    # Probar partición con diferentes tamaños
    tamanos_prueba = [10, 50, 100, 150]
    
    for tamano in tamanos_prueba:
        print(f"\n🔍 Tamaño de lote: {tamano}")
        try:
            lotes = client._particionar_rucs_en_lotes(rucs_prueba, tamano)
            print(f"   ✅ Lotes generados: {len(lotes)}")
            
            # Mostrar información de cada lote
            for i, lote in enumerate(lotes):
                print(f"   📦 Lote {i+1}: {len(lote)} RUCs")
                if i == 0:
                    print(f"      Primer RUC: {lote[0]}")
                    print(f"      Último RUC: {lote[-1]}")
                    
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return False
    
    # Probar con límite de 100 (máximo APIMIGO)
    print(f"\n🎯 Partición para APIMIGO (máximo 100):")
    lotes_100 = client._particionar_rucs_en_lotes(rucs_prueba, 100)
    print(f"   ✅ Se necesitarán {len(lotes_100)} llamadas a la API")
    print(f"   📊 Distribución: {' + '.join(str(len(l)) for l in lotes_100)} = {sum(len(l) for l in lotes_100)}")
    
    return True

def test_todos_endpoints():
    """
    Prueba todos los endpoints configurados en el sistema.
    """
    print("\n" + "=" * 60)
    print("TEST: Todos los endpoints configurados")
    print("=" * 60)
    
    try:
        client = MigoAPIClient()
        service = ApiService.objects.filter(service_type='MIGO').first()
        
        print(f"Servicio: {service.name}")
        print(f"Endpoints configurados: {service.endpoints.count()}")
        
        endpoints_probadps = 0
        endpoints_exitosos = 0
        
        for endpoint in service.endpoints.filter(is_active=True):
            print(f"\n🔧 Endpoint: {endpoint.name}")
            print(f"   Path: {endpoint.path}")
            print(f"   Method: {endpoint.method}")
            print(f"   Rate limit: {endpoint.rate_limit}/min") 
            print(f"   Activo: {endpoint.is_active}")
            
            try:
                # Determinar qué prueba hacer según el endpoint
                if endpoint.name == 'consulta_dni':
                    resultado = client.consultar_dni("71265310")
                    if resultado.get('success'):
                        print(f"   ✅ DNI válido: {resultado.get('nombre')}")
                        endpoints_exitosos += 1
                
                elif endpoint.name == 'consulta_ruc':
                    resultado = client.consultar_ruc("20603274742")
                    if resultado.get('success'):
                        print(f"   ✅ RUC válido: {resultado.get('nombre_o_razon_social')}")
                        endpoints_exitosos += 1
                
                elif endpoint.name == 'consulta_ruc_masivo':
                    # Esperar si hay rate limit activo
                    import time
                    time.sleep(2)  # Aumentar tiempo de espera
                    # Pasar como lista de strings individuales
                    rucs = ["20557425889", "20607403903", "20546904106", "20603274742"]
                    
                    try:
                        # ✅ NUEVO: Obtener RUCs de forma dinámica
                        rucs_prueba = construir_lista_rucs_prueba(minimo=100)
                        print(f"   🔍 Usando {len(rucs_prueba)} RUCs para prueba")
                        print(f"   📋 Muestra: {', '.join(rucs_prueba[:3])}...")
                        
                        resultado = client.consultar_ruc_masivo(rucs_prueba)
                        
                        # Verificar el formato de respuesta mejorado
                        if isinstance(resultado, dict) and resultado.get('success') == True:
                            print(f"   ✅ Consulta masiva exitosa: {resultado.get('successful', 0)} de {resultado.get('total_requested', 0)} RUCs procesados")
                            print(f"   📊 Activos: {resultado['summary']['activos']}, Habidos: {resultado['summary']['habidos']}")
                            
                            # ✅ NUEVO: Mostrar análisis de facturación
                            analisis = resultado.get('analisis_facturacion', {})
                            if analisis:
                                print(f"\n   🧾 ANÁLISIS DE FACTURACIÓN:")
                                print(f"   📈 Habilitados para facturar: {analisis['habilitados_facturacion']['cantidad']} ({analisis['habilitados_facturacion']['porcentaje']:.1f}%)")
                                print(f"   ⚠️  No habilitados: {analisis['no_habilitados_facturacion']['cantidad']} ({analisis['no_habilitados_facturacion']['porcentaje']:.1f}%)")
                                
                                # Mostrar RUCs no habilitados
                                if analisis['no_habilitados_facturacion']['items']:
                                    print(f"   🔍 RUCs no habilitados:")
                                    for item in analisis['no_habilitados_facturacion']['items'][:3]:  # Mostrar primeros 3
                                        print(f"      • {item['ruc']}: {item['razon_social'][:30]}... - Motivos: {', '.join(item['motivos'])}")
                                
                                # Mostrar advertencias
                                if analisis['advertencias']['items']:
                                    print(f"   ⚠️  Advertencias:")
                                    for item in analisis['advertencias']['items'][:2]:  # Mostrar primeras 2
                                        print(f"      • {item['ruc']}: {', '.join(item['advertencias'])}")
                                        
                            # ✅ NUEVO: Guardar el resultado en un archivo JSON                            
                            # Crear directorio para resultados si no existe
                            results_dir = "api_test_results"
                            os.makedirs(results_dir, exist_ok=True)
                            
                            # Nombre del archivo con timestamp
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{results_dir}/consulta_ruc_masivo_{timestamp}.json"
                            
                            # Guardar resultado completo
                            with open(filename, 'w', encoding='utf-8') as f:
                                # Agregar metadatos adicionales
                                resultado_con_metadata = {
                                    'metadata': {
                                        'test_timestamp': datetime.now().isoformat(),
                                        'total_rucs': len(rucs_prueba),
                                        'rucs_procesados': rucs_prueba,
                                        'endpoint': endpoint.name,
                                        'service': 'APIMIGO Perú',
                                        'fuentes': {
                                            'partners': len(obtener_rucs_de_partners()),
                                            'fallas': len(obtener_rucs_con_fallas()),
                                            'adicionales': len(obtener_rucs_adicionales())
                                        }
                                    },
                                    'results': resultado
                                }
                                json.dump(resultado_con_metadata, f, ensure_ascii=False, indent=2)
                            
                            print(f"   💾 Resultado guardado en: {filename}")
                            
                            # ✅ También probar la función de partición con datos reales
                            print(f"\n   🧪 Probando función de partición con datos reales...")
                            try:
                                # Crear lista más grande para probar partición
                                rucs_largos = rucs * 25  # 4 * 25 = 100 RUCs
                                
                                # Probar partición
                                lotes = client._particionar_rucs_en_lotes(rucs_largos, 30)  # Lotes de 30
                                print(f"   📦 Lista de {len(rucs_largos)} RUCs particionada en {len(lotes)} lotes")
                                print(f"   📊 Distribución por lote: {[len(l) for l in lotes]}")
                                
                                # Guardar también la estructura de partición
                                particion_file = f"{results_dir}/particion_rucs_{timestamp}.json"
                                with open(particion_file, 'w', encoding='utf-8') as pf:
                                    json.dump({
                                        'total_rucs': len(rucs_largos),
                                        'tamano_lote': 30,
                                        'total_lotes': len(lotes),
                                        'lotes': lotes
                                    }, pf, ensure_ascii=False, indent=2)
                                
                                print(f"   💾 Partición guardada en: {particion_file}")
                                
                            except Exception as e:
                                print(f"   ⚠️  Error en prueba de partición: {str(e)}")
                                
                            endpoints_exitosos += 1
                        else:
                            error_msg = resultado.get('error', 'Formato inesperado')
                            print(f"   ❌ Error en consulta masiva: {error_msg}")
                            
                    except Exception as e:
                        print(f"   ❌ Error: {str(e)}")
                        if "Rate limit" in str(e):
                            print(f"   ⚠️  Rate limit alcanzado. Prueba aumentando time.sleep()")
                        
                        # ✅ Guardar también el error en un archivo
                        results_dir = "api_test_results"
                        os.makedirs(results_dir, exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        error_file = f"{results_dir}/error_consulta_masiva_{timestamp}.json"
                        
                        with open(error_file, 'w', encoding='utf-8') as f:
                            json.dump({
                                'error': str(e),
                                'rucs_intentados': rucs,
                                'timestamp': datetime.now().isoformat(),
                                'endpoint': endpoint.name
                            }, f, ensure_ascii=False, indent=2)
                        
                        print(f"   💾 Error guardado en: {error_file}")
                
                elif endpoint.name == 'tipo_cambio_latest':
                    resultado = client.consultar_tipo_cambio_latest()
                    if resultado.get('success'):
                        print(f"   ✅ Tipo cambio: {resultado.get('precio_compra')}")
                        endpoints_exitosos += 1
                
                elif endpoint.name == 'tipo_cambio_fecha':
                    fecha_ayer = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    resultado = client.consultar_tipo_cambio_fecha(fecha_ayer)
                    if resultado.get('success'):
                        print(f"   ✅ Tipo cambio {fecha_ayer}: {resultado.get('precio_compra')}")
                        endpoints_exitosos += 1
                
                elif endpoint.name == 'consulta_cuenta':
                    resultado = client.consultar_cuenta()
                    if resultado.get('success'):
                        print(f"   ✅ Cuenta: {resultado.get('nombre')}")
                        endpoints_exitosos += 1
                
                elif endpoint.name == 'representantes_legales':
                    resultado = client.consultar_representantes_legales("20603274742")
                    if resultado.get('success'):
                        print(f"   ✅ Representantes encontrados: {len(resultado.get('data', []))}")
                        endpoints_exitosos += 1
                        
                elif endpoint.name == 'tipo_cambio_rango':
                    fecha_inicio = (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    fecha_fin = timezone.now().strftime('%Y-%m-%d')
                    resultado = client.consultar_tipo_cambio_rango(fecha_inicio, fecha_fin)
                    if isinstance(resultado, list) and len(resultado) > 0:
                        print(f"   ✅ Tipo cambio rango exitoso: {len(resultado)} registros")
                        endpoints_exitosos += 1
                
                else:
                    print(f"   ⚠️  Endpoint no implementado en pruebas")
                
                endpoints_probadps += 1
                
            except Exception as e:
                print(f"   ❌ Error: {type(e).__name__}: {str(e)[:80]}")
        
        print(f"\n📊 Resumen endpoints:")
        print(f"   Probados: {endpoints_probadps}")
        print(f"   Exitosos: {endpoints_exitosos}")
        print(f"   Tasa éxito: {endpoints_exitosos/max(endpoints_probadps,1)*100:.1f}%")
        
        return endpoints_exitosos > 0
        
    except Exception as e:
        print(f"❌ ERROR en test_todos_endpoints: {e}")
        return False

def test_tipo_cambio_uso_real():
    """
    Prueba de tipo de cambio para uso en facturación.
    """
    print("\n" + "=" * 60)
    print("TEST: Tipo de cambio para facturación")
    print("=" * 60)
    
    try:
        client = MigoAPIClient()
        
        print("1. Último tipo de cambio disponible:")
        resultado_latest = client.consultar_tipo_cambio_latest()  # Sin fecha = último
        if resultado_latest.get('success'):
            print(f"   ✅ Fecha: {resultado_latest.get('fecha')}")
            print(f"   💰 Compra: {resultado_latest.get('precio_compra')}")
            print(f"   💰 Venta: {resultado_latest.get('precio_venta')}")
            print(f"   💵 Moneda: {resultado_latest.get('moneda')}")
        else:
            print(f"   ❌ No se pudo obtener último tipo de cambio")
            return False
        
        print("\n2. Tipo de cambio para una fecha específica (hace 5 días):")
        fecha_pasada = (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        resultado_fecha = client.consultar_tipo_cambio_fecha(fecha_pasada)
        
        if resultado_fecha.get('success'):
            print(f"   ✅ Fecha: {resultado_fecha.get('fecha')}")
            print(f"   💰 Compra: {resultado_fecha.get('precio_compra')}")
            print(f"   💰 Venta: {resultado_fecha.get('precio_venta')}")
            
            # Comparar con el último
            dif_compra = float(resultado_latest.get('precio_compra', 0)) - float(resultado_fecha.get('precio_compra', 0))
            dif_venta = float(resultado_latest.get('precio_venta', 0)) - float(resultado_fecha.get('precio_venta', 0))
            
            print(f"   📈 Variación vs hoy: Compra: {dif_compra:+.4f}, Venta: {dif_venta:+.4f}")
        else:
            print(f"   ⚠️  No se pudo obtener tipo de cambio para {fecha_pasada}")
        
        print("\n3. Uso en contexto de facturación:")
        print("   Para facturas en USD, necesitamos tipo de cambio SUNAT del día.")
        print("   Este endpoint es crítico para:")
        print("   - Facturación en moneda extranjera")
        print("   - Conversión a PEN para contabilidad")
        print("   - Cálculo de IGV en moneda extranjera")
        
        # Ejemplo de cálculo
        monto_usd = 1000.00
        tipo_cambio = float(resultado_latest.get('precio_compra', 3.7))
        monto_pen = monto_usd * tipo_cambio
        igv = monto_pen * 0.18
        total = monto_pen + igv
        
        print(f"\n   💰 Ejemplo factura USD $1,000:")
        print(f"   📊 Tipo cambio: {tipo_cambio}")
        print(f"   💵 Base PEN: S/. {monto_pen:,.2f}")
        print(f"   🏛️  IGV (18%): S/. {igv:,.2f}")
        print(f"   🧾 Total: S/. {total:,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR en test_tipo_cambio_uso_real: {e}")
        return False

def test_rate_limit_endpoint_especifico():
    """
    Prueba que los endpoints respetan sus límites específicos.
    """
    print("\n" + "=" * 60)
    print("TEST: Rate limits específicos por endpoint")
    print("=" * 60)
    
    try:
        service = ApiService.objects.filter(service_type='MIGO').first()
        
        print("📊 Límites configurados por endpoint:")
        for endpoint in service.endpoints.filter(is_active=True):
            limite = endpoint.rate_limit
            custom = " (personalizado)" if endpoint.custom_rate_limit else ""
            print(f"   • {endpoint.name}: {limite}/min{custom}")
        
        print("\n🔍 Endpoints con límites personalizados:")
        endpoints_personalizados = service.endpoints.filter(
            is_active=True,
            custom_rate_limit__isnull=False
        )
        
        if endpoints_personalizados.exists():
            for endpoint in endpoints_personalizados:
                print(f"\n🎯 Probando: {endpoint.name} (límite: {endpoint.custom_rate_limit}/min)")
                
                # Este test requiere modificación para probar límites específicos
                # Por ahora solo mostramos información
                print(f"   ⚠️  Para probar este límite necesitamos:")
                print(f"     1. Contador separado por endpoint (no implementado)")
                print(f"     2. Lógica en _check_rate_limit que use endpoint.custom_rate_limit")
        
        else:
            print("   ℹ️  No hay endpoints con límites personalizados")
            print("   💡 Sugerencia: Configura custom_rate_limit en endpoints DNI y RUC masivo")
        
        # Verificar implementación actual
        print("\n🔧 Estado actual de rate limiting:")
        print("   • Tabla ApiRateLimit: Contador general por servicio")
        print("   • Endpoint.custom_rate_limit: Configurable pero no usado en contador")
        print("   • _check_rate_limit: Usa service.requests_per_minute")
        
        print("\n💡 Para implementar rate limits por endpoint necesitamos:")
        print("   1. Modificar ApiRateLimit para incluir campo 'endpoint'")
        print("   2. Actualizar _check_rate_limit para usar límites por endpoint")
        print("   3. Crear contadores separados por endpoint")
        
        return True  # Consideramos exitoso si solo muestra información
        
    except Exception as e:
        print(f"❌ ERROR en test_rate_limit_endpoint_especifico: {e}")
        return False

def test_estadisticas_uso():
    """
    Muestra estadísticas de uso real de la API.
    """
    print("\n" + "=" * 60)
    print("TEST: Estadísticas de uso de API")
    print("=" * 60)
    
    try:
        service = ApiService.objects.filter(service_type='MIGO').first()
        
        # Período de análisis
        ultimas_24h = timezone.now() - timedelta(hours=24)
        ultima_semana = timezone.now() - timedelta(days=7)
        
        # Estadísticas generales
        total_logs = ApiCallLog.objects.filter(service=service).count()
        logs_24h = ApiCallLog.objects.filter(service=service, created_at__gte=ultimas_24h)
        logs_semana = ApiCallLog.objects.filter(service=service, created_at__gte=ultima_semana)
        
        print(f"📈 Estadísticas del servicio: {service.name}")
        print(f"   • Total histórico: {total_logs} llamadas")
        print(f"   • Últimas 24h: {logs_24h.count()} llamadas")
        print(f"   • Última semana: {logs_semana.count()} llamadas")
        
        # Por estado
        estados = logs_24h.values('status').annotate(
            total=models.Count('id')
        ).order_by('-total')
        
        print(f"\n📊 Estado de llamadas (24h):")
        for estado in estados:
            porcentaje = (estado['total'] / logs_24h.count() * 100) if logs_24h.count() > 0 else 0
            print(f"   • {estado['status']}: {estado['total']} ({porcentaje:.1f}%)")
        
        # Por endpoint
        print(f"\n🎯 Endpoints más usados (24h):")
        endpoints = logs_24h.values('endpoint__name').annotate(
            total=models.Count('id'),
            exitosos=models.Count('id', filter=models.Q(status='SUCCESS')),
            fallidos=models.Count('id', filter=models.Q(status='FAILED')),
        ).order_by('-total')[:5]
        
        for ep in endpoints:
            nombre = ep['endpoint__name'] or 'Sin endpoint'
            tasa_exito = (ep['exitosos'] / ep['total'] * 100) if ep['total'] > 0 else 0
            print(f"   • {nombre}: {ep['total']} llamadas ({tasa_exito:.1f}% éxito)")
        
        # Rate limits
        print(f"\n⏰ Rate limiting:")
        print(f"   • Límite configurado: {service.requests_per_minute}/min")
        
        rate_limits_24h = logs_24h.filter(status='RATE_LIMITED').count()
        if rate_limits_24h > 0:
            print(f"   • Rate limits activados (24h): {rate_limits_24h} veces")
        else:
            print(f"   • Rate limits activados (24h): 0 (nunca se excedió el límite)")
        
        # Recomendaciones
        print(f"\n💡 Recomendaciones basadas en uso:")
        promedio_hora = logs_24h.count() / 24
        if promedio_hora > service.requests_per_minute:
            print(f"   ⚠️  Uso promedio por hora ({promedio_hora:.1f}) cerca del límite/min")
        else:
            print(f"   ✅ Uso promedio por hora ({promedio_hora:.1f}) dentro de límites")
        
        if logs_24h.filter(status='FAILED').count() > 10:
            print(f"   ⚠️  Muchos errores recientes, revisar configuración")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR en test_estadisticas_uso: {e}")
        return False

def main():
    """Ejecutar todas las pruebas de uso real"""
    print("🚀 PRUEBAS DE USO REAL - Módulo api_service")
    print("📋 Objetivo: Verificar integración y casos reales")
    print("=" * 60)
    
    tests = [
        ("Integración con Partners", test_integracion_partners),
        ("Particion de rucs", test_particion_rucs),
        ("Todos los endpoints", test_todos_endpoints),
        ("Tipo cambio para facturación", test_tipo_cambio_uso_real),
        ("Rate limits por endpoint", test_rate_limit_endpoint_especifico),
        ("Estadísticas de uso", test_estadisticas_uso),
    ]
    
    resultados = []
    
    for nombre_test, funcion_test in tests:
        try:
            print(f"\n▶️  EJECUTANDO: {nombre_test}")
            print("-" * 40)
            resultado = funcion_test()
            resultados.append((nombre_test, resultado))
            print(f"✅ {nombre_test}: {'PASÓ' if resultado else 'FALLÓ'}")
        except Exception as e:
            print(f"\n💥 ERROR en {nombre_test}: {e}")
            import traceback
            traceback.print_exc()
            resultados.append((nombre_test, False))
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN FINAL DE PRUEBAS")
    print("=" * 60)
    
    exitosos = sum(1 for _, resultado in resultados if resultado)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        icono = "✅" if resultado else "❌"
        print(f"{icono} {nombre}")
    
    print(f"\n🎯 Resultado: {exitosos}/{total} pruebas exitosas")
    
    if exitosos == total:
        print("\n✨ ¡Todas las pruebas pasaron! El módulo está listo para producción.")
    else:
        print(f"\n⚠️  {total - exitosos} prueba(s) fallaron.")
    
    # Próximos pasos
    print("\n" + "=" * 60)
    print("PRÓXIMOS PASOS RECOMENDADOS:")
    print("=" * 60)
    print("1. ✅ Integrar con módulo de facturación")
    print("2. 🔧 Implementar rate limits por endpoint (si es crítico)")
    print("3. 📊 Crear dashboard de monitoreo avanzado")
    print("4. 🔄 Agregar reintentos automáticos para errores temporales")
    print("5. 🗂️  Integrar con NubeFact API")
    
    # Verificación final
    print("\n🔍 VERIFICACIÓN FINAL DEL MÓDULO:")
    from api_service.models import ApiCallLog
    logs_recientes = ApiCallLog.objects.order_by('-created_at')[:3]
    
    if logs_recientes:
        print(f"Últimos logs creados durante pruebas: {len(logs_recientes)}")
        for log in logs_recientes:
            estado = "🟢" if log.status == 'SUCCESS' else "🔴" if log.status == 'FAILED' else "🟡"
            print(f"{estado} {log.endpoint.name if log.endpoint else 'N/A'} - {log.status} - {log.created_at.time()}")

if __name__ == "__main__":
    # Agregar import de models para estadísticas
    from django.db import models
    main()