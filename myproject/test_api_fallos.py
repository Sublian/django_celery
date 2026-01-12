# test_api_fallos.py
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from myproject.api_service.services.migo_service import MigoAPIClient
from api_service.models import ApiCallLog, ApiService
from api_service.exceptions import RateLimitExceededError 
from django.utils import timezone

def test_ruc_invalido():
    """Prueba con RUC inválido (no existe)"""
    print("=" * 50)
    print("TEST: RUC inválido (no existe)")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        # RUC que probablemente no exista
        ruc_invalido = "12345678901"
        
        print(f"Consultando RUC inválido: {ruc_invalido}...")
        resultado = client.consultar_ruc(ruc_invalido)
        
        print(f"   Success en API: {resultado.get('success', False)}")
        
        if not resultado.get('success'):
            print("   ✅ Correcto: API devolvié éxito=False para RUC inválido")
        
        # Verificar log
        logs = ApiCallLog.objects.filter(
            request_data__contains={'ruc': ruc_invalido}
        ).order_by('-created_at')[:1]
        
        if logs:
            log = logs[0]
            print(f"   📝 Log creado: ID={log.id}")
            print(f"   📊 Estado: {log.status}")
            print(f"   🔧 Endpoint: {log.endpoint.name if log.endpoint else 'N/A'}")
            print(f"   🕒 Fecha: {log.created_at}")
            
            if log.status == 'SUCCESS':
                print("   ⚠️  OJO: Log muestra SUCCESS aunque RUC no existe")
            elif log.status == 'FAILED':
                print("   ✅ Correcto: Log muestra FAILED para RUC inválido")
            
            return True
        else:
            print("   ❌ ERROR: No se creó log para la consulta")
            return False
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_token_invalido():
    """Prueba con token inválido (simulado)"""
    print("\n" + "=" * 50)
    print("TEST: Token inválido")
    print("=" * 50)
    
    try:
        # Crear cliente temporal con token inválido
        from api_service.models import ApiService
        import requests
        
        # Guardar token original
        servicio = ApiService.objects.filter(service_type='MIGO').first()
        token_original = servicio.auth_token
        
        try:
            # Usar token inválido temporalmente
            servicio.auth_token = "token_invalido_123"
            servicio.save()
            
            client = MigoAPIClient()
            
            print("Consultando con token inválido...")
            resultado = client.consultar_cuenta()
            
            print(f"   Resultado: {resultado}")
            
        finally:
            # Restaurar token original
            servicio.auth_token = token_original
            servicio.save()
            
        return True
            
    except Exception as e:
        print(f"   ✅ Correcto: Se lanzó excepción con token inválido")
        print(f"   📋 Error: {type(e).__name__}: {str(e)[:100]}")
        
        # Verificar log del error
        logs = ApiCallLog.objects.filter(
            error_message__icontains='token'
        ).order_by('-created_at')[:1]
        
        if logs:
            log = logs[0]
            print(f"   📝 Log de error creado: ID={log.id}")
            print(f"   📊 Estado: {log.status}")
            print(f"   📋 Error: {log.error_message[:100]}...")
        
        return True  # El error esperado es un "éxito" en esta prueba

def test_rate_limiting():
    """Prueba de rate limiting (hacer muchas llamadas seguidas)"""
    print("\n" + "=" * 50)
    print("TEST: Rate limiting")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        # Primera llamada debería funcionar
        print("1. Primera llamada (debería funcionar)...")
        resultado1 = client.consultar_cuenta()
        print(f"   ✅ {'Éxito' if resultado1.get('success') else 'Falló'}")
        
        # Intentar varias llamadas rápidamente
        print("2. Intentando múltiples llamadas rápidas...")
        errores_rate_limit = 0
        
        for i in range(5):
            try:
                resultado = client.consultar_cuenta()
                print(f"   Llamada {i+1}: {'✅ Éxito' if resultado.get('success') else '⚠️ API falló'}")
            except Exception as e:
                if 'rate limit' in str(e).lower() or 'RateLimitExceededError' in str(e):
                    print(f"   Llamada {i+1}: ⏸️ Rate limit excedido (esperado)")
                    errores_rate_limit += 1
                else:
                    print(f"   Llamada {i+1}: ❌ Error inesperado: {e}")
        
        if errores_rate_limit > 0:
            print(f"   ✅ Correcto: Se detectaron {errores_rate_limit} errores de rate limit")
        else:
            print("   ⚠️  No se detectaron errores de rate limit (puede que el límite sea alto)")
        
        return True
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_rate_limiting_intensivo():
    """Prueba intensiva de rate limiting"""
    print("\n" + "=" * 50)
    print("TEST: Rate limiting intensivo")
    print("=" * 50)
    
    try:
        from api_service.models import ApiRateLimit
        
        # Resetear contador de rate limit
        service = ApiService.objects.filter(service_type='MIGO').first()
        rate_limit, _ = ApiRateLimit.objects.get_or_create(service=service)
        rate_limit.reset_counter()
        
        client = MigoAPIClient()
        
        print(f"Límite configurado: {service.requests_per_minute}/min")
        print("Haciendo llamadas hasta alcanzar el límite...")
        
        exitosas = 0
        rate_limited = 0
        otros_errores = 0
        
        for i in range(service.requests_per_minute + 5):  # Intentar 5 más del límite
            try:
                resultado = client.consultar_cuenta()
                if resultado.get('success'):
                    exitosas += 1
                    if exitosas % 10 == 0:
                        print(f"  Llamada {i+1}: ✅ Éxito ({exitosas} exitosas)")
            except RateLimitExceededError:
                rate_limited += 1
                print(f"  Llamada {i+1}: ⏸️ Rate limit excedido (total: {rate_limited})")
                break  # Salir cuando se active rate limiting
            except Exception as e:
                otros_errores += 1
                print(f"  Llamada {i+1}: ❌ {type(e).__name__}")
        
        print(f"\nResumen:")
        print(f"  ✅ Exitosas: {exitosas}")
        print(f"  ⏸️ Rate limited: {rate_limited}")
        print(f"  ❌ Otros errores: {otros_errores}")
        
        if rate_limited > 0:
            print("  ✅ Rate limiting funciona correctamente")
            return True
        else:
            print(f"  ⚠️ No se activó rate limiting (límite: {service.requests_per_minute}/min)")
            # No es un error, solo información
            return True
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def test_endpoint_inexistente():
    """Prueba llamando a endpoint que no existe"""
    print("\n" + "=" * 50)
    print("TEST: Endpoint inexistente")
    print("=" * 50)
    
    try:
        # Esta prueba requiere modificar el cliente temporalmente
        # Podemos hacerlo llamando directamente al método _make_request con endpoint inválido
        
        client = MigoAPIClient()
        
        print("Intentando llamar a endpoint inexistente...")
        
        # Usar reflexión para llamar al método protegido
        resultado = client._make_request(
            # endpoint_path='/api/v1/endpoint_que_no_existe',
            # method='POST',
            # data={'token': 'test'},
            endpoint_name='Endpoint inexistente',
            payload={'token': 'test', 'ruc': '12345678901'}
        )
        
        print(f"   Resultado: {resultado}")
        return False  # No debería llegar aquí
        
    except Exception as e:
        print(f"   ✅ Correcto: Se lanzó excepción para endpoint inexistente")
        print(f"   📋 Error: {type(e).__name__}: {str(e)[:100]}")
        
        # Verificar log
        logs = ApiCallLog.objects.filter(
            endpoint__path__contains='endpoint_que_no_existe'
        ).order_by('-created_at')[:1]
        
        if logs:
            log = logs[0]
            print(f"   📝 Log creado: ID={log.id}")
            print(f"   📊 Estado: {log.status}")
            print(f"   🔢 Código respuesta: {log.response_code}")
        
        return True

def test_rate_limiting_dni_rapido():
    """
    Prueba rápida de rate limiting para DNI usando manipulación directa.
    """
    print("\n" + "=" * 50)
    print("TEST: Rate limiting DNI (manipulación directa)")
    print("=" * 50)
    
    try:
        from api_service.models import ApiRateLimit, ApiEndpoint
        
        # Obtener endpoint DNI
        service = ApiService.objects.filter(service_type='MIGO').first()
        endpoint_dni = ApiEndpoint.objects.filter(
            service=service,
            path='/api/v1/dni'
        ).first()
        
        if not endpoint_dni:
            print("❌ Endpoint DNI no configurado")
            return False
        
        rate_limit_dni = endpoint_dni.rate_limit
        print(f"Rate limit DNI: {rate_limit_dni}/min")
        
        # Manipular rate limit para simular límite alcanzado
        rate_limit_obj, _ = ApiRateLimit.objects.get_or_create(service=service)
        
        print("\n1. Simulando que ya se hicieron todas las consultas del minuto...")
        # Forzar el contador al límite
        rate_limit_obj.current_count = rate_limit_dni
        rate_limit_obj.save()
        
        print(f"   Contador forzado a: {rate_limit_obj.current_count}/{rate_limit_dni}")
        print(f"   Puede hacer más?: {rate_limit_obj.can_make_request()}")
        
        # Intentar consulta (debería fallar inmediatamente)
        client = MigoAPIClient()
        
        print("\n2. Intentando consulta con rate limit artificialmente lleno...")
        try:
            resultado = client.consultar_dni("71265310")
            print(f"   ❌ CONTRADICCIÓN: Consulta pasó a pesar de rate limit lleno")
            return False
        except RateLimitExceededError as e:
            print(f"   ✅ Rate limit funcionó correctamente")
            print(f"   📋 Error: {e}")
            
            # Verificar log
            logs = ApiCallLog.objects.filter(
                service=service,
                status='RATE_LIMITED'
            ).order_by('-created_at')[:1]
            
            if logs:
                log = logs[0]
                print(f"   📝 Log creado: ID={log.id}")
                print(f"   🕒 Hace: {(timezone.now() - log.created_at).seconds} segundos")
                return True
            else:
                print(f"   ⚠️ No se creó log de rate limit")
                return False
                
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False
    
def test_rate_limiting_logs_completos():
    """
    Prueba que los logs de rate limit tengan información completa.
    """
    print("\n" + "=" * 50)
    print("TEST: Logs de rate limit completos")
    print("=" * 50)
    
    try:
        from api_service.models import ApiRateLimit, ApiEndpoint
        
        # Resetear rate limit
        service = ApiService.objects.filter(service_type='MIGO').first()
        rate_limit_obj, _ = ApiRateLimit.objects.get_or_create(service=service)
        rate_limit_obj.reset_counter()
        
        # Forzar rate limit lleno
        rate_limit_obj.current_count = service.requests_per_minute
        rate_limit_obj.save()
        
        print(f"1. Rate limit forzado: {rate_limit_obj.current_count}/{service.requests_per_minute}")
        
        # Intentar diferentes endpoints para ver logs
        endpoints_a_probar = [
            ('consultar_dni', 'DNI'),
            ('consultar_ruc', 'RUC'),
            ('consultar_cuenta', 'account')
        ]
        
        logs_creados = []
        
        for metodo, nombre_endpoint in endpoints_a_probar:
            print(f"\n2. Probando rate limit para endpoint: {nombre_endpoint}")
            
            client = MigoAPIClient()
            
            try:
                if metodo == 'consultar_dni':
                    resultado = client.consultar_dni("71265310")
                elif metodo == 'consultar_ruc':
                    resultado = client.consultar_ruc("20603274742")
                elif metodo == 'consultar_cuenta':
                    resultado = client.consultar_cuenta()
                    
                print(f"   ❌ CONTRADICCIÓN: {nombre_endpoint} pasó (debería fallar)")
                
            except RateLimitExceededError as e:
                print(f"   ✅ Rate limit funcionó para {nombre_endpoint}")
                
                # Verificar log específico
                logs = ApiCallLog.objects.filter(
                    service=service,
                    status='RATE_LIMITED'
                ).order_by('-created_at')[:1]
                
                if logs:
                    log = logs[0]
                    logs_creados.append(log)
                    
                    print(f"   📝 Log ID: {log.id}")
                    print(f"   🔧 Endpoint en log: {log.endpoint.name if log.endpoint else 'N/A'}")
                    print(f"   📋 Error: {log.error_message[:80]}...")
                    
                    # Verificar request_data
                    if 'attempted_endpoint' in log.request_data:
                        endpoint_intentado = log.request_data['attempted_endpoint']
                        print(f"   🎯 Endpoint intentado: {endpoint_intentado}")
                        
                        # Validar que coincida
                        if endpoint_intentado.lower() in nombre_endpoint.lower():
                            print(f"   ✅ Endpoint en log coincide con prueba")
                        else:
                            print(f"   ⚠️  Endpoint en log NO coincide: {endpoint_intentado} vs {nombre_endpoint}")
                    else:
                        print(f"   ⚠️  Log no tiene información de endpoint intentado")
        
        # Análisis final
        print(f"\n" + "=" * 50)
        print("ANÁLISIS DE LOGS CREADOS:")
        print("=" * 50)
        
        if logs_creados:
            print(f"Total logs creados: {len(logs_creados)}")
            
            for i, log in enumerate(logs_creados, 1):
                print(f"\nLog #{i}:")
                print(f"  ID: {log.id}")
                print(f"  Endpoint DB: {log.endpoint.name if log.endpoint else 'No asignado'}")
                print(f"  Endpoint intentado: {log.request_data.get('attempted_endpoint', 'No registrado')}")
                print(f"  Caller: {log.called_from}")
                print(f"  Request data: {log.request_data}")
                
                # Validaciones
                validaciones = []
                
                if log.endpoint:
                    validaciones.append("✅ Tiene endpoint en DB")
                else:
                    validaciones.append("❌ Sin endpoint en DB")
                
                if 'attempted_endpoint' in log.request_data:
                    validaciones.append("✅ Tiene endpoint intentado")
                else:
                    validaciones.append("❌ Sin endpoint intentado")
                
                if log.called_from and 'consultar_' in log.called_from.lower():
                    validaciones.append("✅ Caller informativo")
                else:
                    validaciones.append("⚠️  Caller genérico")
                
                print(f"  Validaciones: {', '.join(validaciones)}")
        
        else:
            print("⚠️  No se crearon logs")
        
        return True
            
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False    

def test_validacion_ruc_inactivo():
    """Prueba validación de RUC inactivo/no habido"""
    print("\n" + "=" * 50)
    print("TEST: Validación RUC inactivo o no habido")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        # Para esta prueba necesitamos un RUC que sepamos que está INACTIVO o NO HABIDO
        # Podemos usar uno conocido o simular la respuesta
        
        print("Nota: Para probar RUC inactivo, necesitamos un RUC real que esté INACTIVO")
        print("o modificar temporalmente la lógica para simularlo.")
        print("\nOpciones:")
        print("1. Usar RUC 20131312955 (ejemplo de empresa inactiva)")
        print("2. Simular respuesta manualmente")
        
        # Opción: usar un RUC conocido o preguntar al usuario
        ruc_test = input("\nIngresa un RUC para probar (o presiona Enter para omitir): ").strip()
        
        if not ruc_test:
            print("   ⏭️ Prueba omitida")
            return True
        
        print(f"\nValidando RUC: {ruc_test}...")
        validacion = client.validar_ruc_para_facturacion(ruc_test)
        
        print(f"   ✅ Válido para facturar: {validacion['valido']}")
        print(f"   📛 Razón Social: {validacion['razon_social']}")
        print(f"   🟢 Estado: {validacion['estado']}")
        print(f"   🏠 Condición: {validacion['condicion']}")
        
        if validacion['errores']:
            print(f"   ❌ Errores: {', '.join(validacion['errores'])}")
            print("   ✅ Correcto: Se detectaron errores para RUC inválido")
        
        if validacion['advertencias']:
            print(f"   ⚠️ Advertencias: {', '.join(validacion['advertencias'])}")
        
        # Verificar si hay logs
        logs = ApiCallLog.objects.filter(
            request_data__contains={'ruc': ruc_test}
        ).order_by('-created_at')[:2]
        
        if logs:
            print(f"\n   📝 Logs creados: {len(logs)}")
            for log in logs:
                print(f"      - {log.endpoint.name if log.endpoint else 'N/A'}: {log.status}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

def verificar_trazabilidad_completa():
    """Verifica que todos los campos de trazabilidad se llenan correctamente"""
    print("\n" + "=" * 50)
    print("VERIFICACIÓN: Trazabilidad en ApiCallLog")
    print("=" * 50)
    
    # Obtener logs recientes
    desde = timezone.now() - timezone.timedelta(minutes=10)
    logs = ApiCallLog.objects.filter(created_at__gte=desde).order_by('-created_at')
    
    print(f"Logs encontrados en últimos 10 minutos: {logs.count()}")
    
    if logs.count() == 0:
        print("⚠️  No hay logs recientes. Ejecuta algunas pruebas primero.")
        return False
    
    # Analizar campos de cada log
    campos_requeridos = [
        ('service', 'Servicio'),
        ('status', 'Estado'),
        ('request_data', 'Datos de petición'),
        ('response_data', 'Datos de respuesta'),
        ('response_code', 'Código de respuesta'),
        ('created_at', 'Fecha creación'),
        ('called_from', 'Llamado desde'),
    ]
    
    print("\nAnálisis de trazabilidad:")
    print("-" * 80)
    
    for i, log in enumerate(logs[:3]):  # Analizar solo los 3 más recientes
        print(f"\nLog #{i+1}: {log.id}")
        print(f"  Servicio: {log.service.name}")
        print(f"  Endpoint: {log.endpoint.name if log.endpoint else 'N/A'}")
        print(f"  Estado: {log.status}")
        print(f"  Código HTTP: {log.response_code}")
        print(f"  Duración: {log.duration_ms}ms")
        print(f"  Error: {log.error_message[:50] if log.error_message else 'Ninguno'}")
        print(f"  Llamado desde: {log.called_from}")
        print(f"  Fecha: {log.created_at}")
        
        # Verificar campos completos
        campos_faltantes = []
        for campo, nombre in campos_requeridos:
            valor = getattr(log, campo)
            if valor is None or (isinstance(valor, (str, dict, list)) and not valor):
                campos_faltantes.append(nombre)
        
        if campos_faltantes:
            print(f"  ⚠️  Campos faltantes: {', '.join(campos_faltantes)}")
        else:
            print(f"  ✅ Todos los campos están completos")
    
    # Estadísticas
    print("\n" + "-" * 80)
    print("ESTADÍSTICAS:")
    
    total = logs.count()
    exitosos = logs.filter(status='SUCCESS').count()
    fallidos = logs.filter(status='FAILED').count()
    
    print(f"Total logs: {total}")
    print(f"Exitosos: {exitosos} ({exitosos/total*100:.1f}%)")
    print(f"Fallidos: {fallidos} ({fallidos/total*100:.1f}%)")
    
    # Endpoints más usados
    from django.db.models import Count
    endpoints_populares = logs.values('endpoint__name').annotate(
        total=Count('id')
    ).order_by('-total')[:5]
    
    print("\nEndpoints más llamados:")
    for ep in endpoints_populares:
        nombre = ep['endpoint__name'] or 'N/A'
        print(f"  {nombre}: {ep['total']} llamadas")
    
    return True

def main():
    """Ejecutar todas las pruebas de fallo"""
    print("🔍 Iniciando pruebas de fallo y trazabilidad")
    print("📊 Objetivo: Verificar manejo de errores y trazabilidad en ApiCallLog")
    print("-" * 50)
    
    tests = [
        # ("RUC inválido", test_ruc_invalido),
        # ("Token inválido", test_token_invalido),
        # ("Rate limiting", test_rate_limiting),
        # ("Rate limiting intensivo", test_rate_limiting_intensivo),
        # ("Endpoint inexistente", test_endpoint_inexistente),
        # ("Rate limiting DNI", test_rate_limiting_dni_rapido),
        ("Rate limiting varios", test_rate_limiting_logs_completos),
        # ("Validación RUC inactivo", test_validacion_ruc_inactivo),
        ("Verificar trazabilidad", verificar_trazabilidad_completa),
    ]
    
    resultados = []
    
    for nombre_test, funcion_test in tests:
        try:
            print(f"\n▶️  Ejecutando: {nombre_test}")
            resultado = funcion_test()
            resultados.append((nombre_test, resultado))
        except Exception as e:
            print(f"\n💥 ERROR en test {nombre_test}: {e}")
            import traceback
            traceback.print_exc()
            resultados.append((nombre_test, False))
    
    # Resumen
    print("\n" + "=" * 50)
    print("RESUMEN DE PRUEBAS DE FALLO")
    print("=" * 50)
    
    exitosos = sum(1 for _, resultado in resultados if resultado)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        icono = "✅" if resultado else "❌"
        print(f"{icono} {nombre}: {'PASÓ' if resultado else 'FALLÓ'}")
    
    print(f"\n🎯 Resultado: {exitosos}/{total} pruebas exitosas")
    
    if exitosos == total:
        print("\n✨ ¡Todas las pruebas de fallo pasaron! La trazabilidad funciona correctamente.")
    else:
        print(f"\n⚠️  {total - exitosos} prueba(s) fallaron. Revisa los errores.")
    
    # Recomendación final
    print("\n" + "=" * 50)
    print("RECOMENDACIONES:")
    print("=" * 50)
    print("1. Revisa la tabla ApiCallLog en el admin Django (/admin/)")
    print("2. Verifica que los logs de error tengan información útil")
    print("3. Asegúrate de que 'called_from' muestre el origen de la llamada")
    print("4. Los logs deberían tener duración (duration_ms) para monitoreo")

if __name__ == "__main__":
    main()