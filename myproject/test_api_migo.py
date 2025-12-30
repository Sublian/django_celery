# test_api_migo.py
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

# Ahora importamos los modelos
from api_service.services import MigoAPIClient
from api_service.models import ApiCallLog

def test_conexion_basica():
    """Prueba básica de conexión con APIMIGO"""
    print("=" * 50)
    print("TEST: Conexión básica con APIMIGO")
    print("=" * 50)
    
    try:
        # 1. Crear cliente
        print("1. Creando cliente APIMIGO...")
        client = MigoAPIClient()
        
        # 2. Probar consulta de cuenta
        print("2. Probando consulta de cuenta...")
        resultado_cuenta = client.consultar_cuenta()
        
        if resultado_cuenta.get('success'):
            print(f"   ✅ Éxito! Cuenta: {resultado_cuenta.get('nombre')}")
            print(f"   📧 Email: {resultado_cuenta.get('email')}")
            print(f"   🔢 Consultas disponibles: {resultado_cuenta.get('consultas')}")
        else:
            print("   ❌ Falló la consulta de cuenta")
            return False
        
        # 3. Verificar logs creados
        print("\n3. Verificando logs en base de datos...")
        logs = ApiCallLog.objects.filter(service=client.service).order_by('-created_at')[:5]
        
        if logs:
            print(f"   ✅ Se crearon {len(logs)} registros de log")
            for log in logs:
                estado = "✅" if log.status == 'SUCCESS' else "❌"
                print(f"   {estado} {log.endpoint.name if log.endpoint else 'N/A'} - {log.status}")
        else:
            print("   ⚠️ No se encontraron logs")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_consulta_ruc():
    """Prueba consulta de RUC individual"""
    print("\n" + "=" * 50)
    print("TEST: Consulta RUC individual")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        # RUC de prueba (MIGO S.A.C.)
        ruc_test = "20603274742"
        
        print(f"Consultando RUC: {ruc_test}...")
        resultado = client.consultar_ruc(ruc_test)
        
        if resultado.get('success'):
            print(f"   ✅ RUC válido!")
            print(f"   📛 Razón Social: {resultado.get('nombre_o_razon_social')}")
            print(f"   🟢 Estado: {resultado.get('estado_del_contribuyente')}")
            print(f"   🏠 Condición: {resultado.get('condicion_de_domicilio')}")
            print(f"   📍 Dirección: {resultado.get('direccion_simple')}")
            return True
        else:
            print(f"   ❌ RUC no encontrado o error")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_consulta_dni():
    """Prueba consulta de DNI"""
    print("\n" + "=" * 50)
    print("TEST: Consulta DNI")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        # DNI de prueba (del ejemplo)
        dni_test = "71265310"
        
        print(f"Consultando DNI: {dni_test}...")
        resultado = client.consultar_dni(dni_test)
        
        if resultado.get('success'):
            print(f"   ✅ DNI válido!")
            print(f"   👤 Nombre: {resultado.get('nombre')}")
            return True
        else:
            print(f"   ❌ DNI no encontrado o error")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_validacion_facturacion():
    """Prueba validación para facturación"""
    print("\n" + "=" * 50)
    print("TEST: Validación para facturación")
    print("=" * 50)
    
    try:
        client = MigoAPIClient()
        
        ruc_test = "20603274742"  # MIGO S.A.C. - debería ser ACTIVO y HABIDO
        
        print(f"Validando RUC para facturación: {ruc_test}...")
        validacion = client.validar_ruc_para_facturacion (ruc_test)
        
        print(f"   ✅ Válido para facturar: {validacion['valido']}")
        print(f"   📛 Razón Social: {validacion['razon_social']}")
        print(f"   🟢 Estado: {validacion['estado']}")
        print(f"   🏠 Condición: {validacion['condicion']}")
        
        if validacion['errores']:
            print(f"   ❌ Errores: {', '.join(validacion['errores'])}")
        
        if validacion['advertencias']:
            print(f"   ⚠️ Advertencias: {', '.join(validacion['advertencias'])}")
        
        return validacion['valido']
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Ejecutar todas las pruebas"""
    print("🚀 Iniciando pruebas del módulo api_service")
    print("📞 API: APIMIGO")
    print("-" * 50)
    
    tests = [
        ("Conexión básica", test_conexion_basica),
        ("Consulta RUC", test_consulta_ruc),
        ("Consulta DNI", test_consulta_dni),
        ("Validación facturación", test_validacion_facturacion),
    ]
    
    resultados = []
    
    for nombre_test, funcion_test in tests:
        try:
            resultado = funcion_test()
            resultados.append((nombre_test, resultado))
        except Exception as e:
            print(f"\n💥 ERROR en test {nombre_test}: {e}")
            resultados.append((nombre_test, False))
    
    # Resumen
    print("\n" + "=" * 50)
    print("RESUMEN DE PRUEBAS")
    print("=" * 50)
    
    exitosos = sum(1 for _, resultado in resultados if resultado)
    total = len(resultados)
    
    for nombre, resultado in resultados:
        icono = "✅" if resultado else "❌"
        print(f"{icono} {nombre}: {'PASÓ' if resultado else 'FALLÓ'}")
    
    print(f"\n🎯 Resultado: {exitosos}/{total} pruebas exitosas")
    
    if exitosos == total:
        print("\n✨ ¡Todas las pruebas pasaron! El módulo api_service funciona correctamente.")
    else:
        print(f"\n⚠️  {total - exitosos} prueba(s) fallaron. Revisa los errores.")

if __name__ == "__main__":
    main()