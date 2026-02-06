#!/usr/bin/env python
"""
Test Flujo Facturación V2
==========================
Script para probar el funcionamiento de los servicios mejorados:
- MigoAPIService (con manejo de RUCs inválidos)
- APICacheService (con cache para RUCs inválidos)

Este script reemplaza/actualiza test_flujo_facturacion.py con las nuevas funciones.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django

django.setup()

# Ahora importamos los servicios Django
from api_service.services.migo_service import MigoAPIService
from api_service.services.cache_service import APICacheService

from billing.models import Partner
from api_service.models import ApiService, ApiEndpoint

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestFlujoFacturacionV2:
    """
    Clase para probar el flujo de facturación con servicios mejorados.
    """

    def __init__(self):
        """Inicializa los servicios de prueba."""
        self.migo_service = MigoAPIService()
        self.cache_service = APICacheService()
        self.test_results = []

    def log_test(self, test_name: str, status: str, details: str = ""):
        """Registra el resultado de un test."""
        result = {
            "test": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.test_results.append(result)

        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {test_name}: {status}")
        if details:
            print(f"   📝 {details}")

    def print_header(self, title: str):
        """Imprime un encabezado bonito."""
        print("\n" + "=" * 60)
        print(f"🧪 {title}")
        print("=" * 60)

    def print_summary(self):
        """Imprime resumen de todos los tests."""
        self.print_header("RESUMEN DE TESTS")

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        warnings = sum(1 for r in self.test_results if r["status"] == "WARNING")

        print(f"📊 Total tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")

        if failed > 0:
            print("\n🔍 Tests fallidos:")
            for test in self.test_results:
                if test["status"] == "FAIL":
                    print(f"   • {test['test']}: {test.get('details', 'Sin detalles')}")

        # Guardar resultados en archivo
        self.save_results_to_file()

    def save_results_to_file(self):
        """Guarda resultados en archivo JSON."""
        filename = f"test_results_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(self.test_results),
                "passed": sum(1 for r in self.test_results if r["status"] == "PASS"),
                "failed": sum(1 for r in self.test_results if r["status"] == "FAIL"),
                "warnings": sum(
                    1 for r in self.test_results if r["status"] == "WARNING"
                ),
            },
            "tests": self.test_results,
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n📁 Resultados guardados en: {filename}")

    # ============================================================================
    # TESTS DEL CACHE SERVICE
    # ============================================================================

    def test_cache_basico(self):
        """Test básico de funciones del cache."""
        self.print_header("TEST CACHE BÁSICO")

        try:
            # Test 1: Set y Get básico
            test_key = "test_cache_key"
            test_value = {"data": "test", "timestamp": datetime.now().isoformat()}

            set_result = self.cache_service.set(test_key, test_value, ttl=60)
            get_result = self.cache_service.get(test_key)

            if set_result and get_result == test_value:
                self.log_test(
                    "Cache Set/Get básico",
                    "PASS",
                    f"Clave: {test_key}, Valor: {test_value}",
                )
            else:
                self.log_test(
                    "Cache Set/Get básico",
                    "FAIL",
                    f"Set: {set_result}, Get: {get_result}",
                )

            # Test 2: Delete
            delete_result = self.cache_service.delete(test_key)
            after_delete = self.cache_service.get(test_key)

            if delete_result and after_delete is None:
                self.log_test("Cache Delete", "PASS", "Clave eliminada correctamente")
            else:
                self.log_test(
                    "Cache Delete",
                    "FAIL",
                    f"Delete: {delete_result}, Get después: {after_delete}",
                )

            # Test 3: Tipo de cambio
            fecha = datetime.now().date().isoformat()
            tc_data = {"fecha": fecha, "compra": 3.75, "venta": 3.80, "source": "test"}

            tc_set = self.cache_service.set_tipo_cambio(fecha, tc_data, ttl=300)
            tc_get = self.cache_service.get_tipo_cambio(fecha)

            if tc_set and tc_get and tc_get.get("compra") == 3.75:
                self.log_test(
                    "Cache Tipo Cambio",
                    "PASS",
                    f"Fecha: {fecha}, Compra: {tc_get.get('compra')}",
                )
            else:
                self.log_test(
                    "Cache Tipo Cambio",
                    "WARNING" if tc_get else "FAIL",
                    f"Set: {tc_set}, Get: {bool(tc_get)}",
                )

        except Exception as e:
            self.log_test("Cache Básico", "FAIL", f"Error: {str(e)}")

    def test_cache_rucs_invalidos(self):
        """Test de funciones para RUCs inválidos."""
        self.print_header("TEST CACHE RUCS INVALIDOS")

        try:
            # RUCs de prueba
            ruc_valido = "20100038146"  # RUC conocido válido
            ruc_invalido_1 = "20678901234"  # RUC inválido conocido
            ruc_invalido_2 = "99999999999"  # RUC inválido genérico

            # Test 1: Agregar RUC inválido
            add_result = self.cache_service.add_invalid_ruc(
                ruc_invalido_1, reason="RUC_PRUEBA_SECUENCIA", ttl_hours=1
            )

            if add_result:
                self.log_test(
                    "Add Invalid RUC",
                    "PASS",
                    f"RUC {ruc_invalido_1} agregado como inválido",
                )
            else:
                self.log_test(
                    "Add Invalid RUC", "FAIL", "No se pudo agregar RUC inválido"
                )

            # Test 2: Verificar RUC inválido
            is_invalid = self.cache_service.is_ruc_invalid(ruc_invalido_1)
            is_valid_ruc_invalid = self.cache_service.is_ruc_invalid(ruc_valido)

            if is_invalid and not is_valid_ruc_invalid:
                self.log_test(
                    "Is RUC Invalid",
                    "PASS",
                    f"{ruc_invalido_1}: {is_invalid}, {ruc_valido}: {is_valid_ruc_invalid}",
                )
            else:
                self.log_test(
                    "Is RUC Invalid",
                    "FAIL",
                    f"Esperado: True para {ruc_invalido_1}, False para {ruc_valido}",
                )

            # Test 3: Obtener información de RUC inválido
            ruc_info = self.cache_service.get_invalid_ruc_info(ruc_invalido_1)

            if ruc_info and ruc_info.get("reason") == "RUC_PRUEBA_SECUENCIA":
                self.log_test(
                    "Get Invalid RUC Info", "PASS", f"Razón: {ruc_info.get('reason')}"
                )
            else:
                self.log_test(
                    "Get Invalid RUC Info", "FAIL", f"Info obtenida: {bool(ruc_info)}"
                )

            # Test 4: Agregar segundo RUC inválido
            self.cache_service.add_invalid_ruc(ruc_invalido_2, reason="RUC_INEXISTENTE")

            # Test 5: Obtener todos los RUCs inválidos
            all_invalid = self.cache_service.get_all_invalid_rucs()

            if len(all_invalid) >= 2 and ruc_invalido_1 in all_invalid:
                self.log_test(
                    "Get All Invalid RUCs",
                    "PASS",
                    f"Total inválidos: {len(all_invalid)}",
                )
            else:
                self.log_test(
                    "Get All Invalid RUCs",
                    "WARNING",
                    f"Esperados 2+, obtenidos: {len(all_invalid)}",
                )

            # Test 6: Remover RUC inválido
            remove_result = self.cache_service.remove_invalid_ruc(ruc_invalido_1)
            after_remove = self.cache_service.is_ruc_invalid(ruc_invalido_1)

            if remove_result and not after_remove:
                self.log_test(
                    "Remove Invalid RUC",
                    "PASS",
                    f"RUC {ruc_invalido_1} removido correctamente",
                )
            else:
                self.log_test(
                    "Remove Invalid RUC",
                    "WARNING",
                    f"Remove: {remove_result}, Still invalid: {after_remove}",
                )

            # Test 7: Estadísticas del cache
            stats = self.cache_service.get_cache_stats()

            if stats and "invalid_rucs_count" in stats:
                self.log_test(
                    "Cache Stats",
                    "PASS",
                    f"Estadísticas obtenidas: {stats.get('invalid_rucs_count')} inválidos",
                )
            else:
                self.log_test("Cache Stats", "WARNING", "Estadísticas no disponibles")

            # Limpiar cache de inválidos al final
            self.cache_service.clear_invalid_rucs()

        except Exception as e:
            self.log_test("Cache RUCs Inválidos", "FAIL", f"Error: {str(e)}")

    # ============================================================================
    # TESTS DEL MIGO SERVICE
    # ============================================================================

    def test_migo_ruc_individual(self):
        """Test de consulta individual de RUC."""
        self.print_header("TEST CONSULTA RUC INDIVIDUAL")

        try:
            # RUCs de prueba
            rucs_prueba = [
                ("20100038146", "RUC válido conocido"),  # RUC válido
                ("20678901234", "RUC inválido conocido (secuencia)"),  # RUC inválido
                ("123", "RUC formato inválido (corto)"),  # Formato inválido
                ("20100000000", "RUC posiblemente inválido"),  # Posible inválido
            ]

            for ruc, descripcion in rucs_prueba:
                print(f"\n🔍 Probando RUC: {ruc} ({descripcion})")

                # Consultar RUC
                start_time = datetime.now()
                resultado = self.migo_service.consultar_ruc(
                    ruc, force_refresh=False, update_partner=True
                )
                elapsed = (datetime.now() - start_time).total_seconds() * 1000

                # Analizar resultado
                if resultado.get("success"):
                    data = resultado.get("data", {})
                    estado = data.get("estado_del_contribuyente", "DESCONOCIDO")
                    razon_social = data.get("nombre_o_razon_social", "NO DISPONIBLE")[
                        :50
                    ]

                    self.log_test(
                        f"RUC Individual - {ruc}",
                        "PASS",
                        f"✅ VÁLIDO: {razon_social} | Estado: {estado} | Tiempo: {elapsed:.0f}ms",
                    )

                    # Verificar si se actualizó el partner
                    try:
                        partner = Partner.objects.filter(
                            Q(ruc=ruc) | Q(num_document=ruc)
                        ).first()
                        if partner and partner.sunat_valid:
                            print(f"   👤 Partner actualizado: {partner.sunat_state}")
                    except:
                        pass

                elif resultado.get("invalid_format"):
                    self.log_test(
                        f"RUC Individual - {ruc}",
                        "PASS",
                        f"❌ FORMATO INVÁLIDO: {resultado.get('error')}",
                    )

                elif resultado.get("invalid_sunat"):
                    self.log_test(
                        f"RUC Individual - {ruc}",
                        "PASS",
                        f"❌ NO EXISTE EN SUNAT: {resultado.get('error')}",
                    )

                    # Verificar que se marcó como inválido en cache
                    if self.cache_service.is_ruc_invalid(ruc):
                        print(f"   💾 RUC marcado en cache de inválidos")

                elif resultado.get("cache_hit"):
                    cache_type = resultado.get("cache_type", "desconocido")
                    self.log_test(
                        f"RUC Individual - {ruc}",
                        "PASS",
                        f"💾 CACHE {cache_type.upper()}: {resultado.get('error', 'Desde cache')}",
                    )

                else:
                    self.log_test(
                        f"RUC Individual - {ruc}",
                        (
                            "WARNING"
                            if "timeout" in str(resultado.get("error", "")).lower()
                            else "FAIL"
                        ),
                        f"⚠️ ERROR: {resultado.get('error', 'Error desconocido')}",
                    )

        except Exception as e:
            self.log_test("Consulta RUC Individual", "FAIL", f"Error: {str(e)}")

    def test_migo_ruc_masivo(self):
        """Test de consulta masiva de RUCs."""
        self.print_header("TEST CONSULTA RUC MASIVA")

        try:
            # Lista de RUCs para prueba (mezcla de válidos, inválidos y formato incorrecto)
            rucs_prueba = [
                "20100038146",  # Válido
                "20100049008",  # Válido
                "20100227461",  # Válido
                "20678901234",  # Inválido (secuencia)
                "20123456789",  # Inválido (secuencia)
                "123",  # Formato inválido
                "20456789012",  # Inválido (secuencia)
                "20537088118",  # Válido
                "abc123",  # Formato inválido (no numérico)
                "20100000000",  # Posible inválido
            ]

            print(f"📋 Total RUCs a consultar: {len(rucs_prueba)}")
            print(
                "📊 Composición: 5 válidos conocidos, 3 inválidos conocidos, 2 formato inválido"
            )

            # Realizar consulta masiva
            start_time = datetime.now()
            resultados = self.migo_service.consultar_ruc_masivo(
                rucs_prueba,
                batch_size=3,  # Tamaño pequeño para pruebas
                update_partners=True,
            )
            elapsed = (datetime.now() - start_time).total_seconds()

            # Analizar resultados
            if resultados.get("success"):
                total_validos = resultados.get("total_validos", 0)
                total_invalidos = resultados.get("total_invalidos", 0)
                total_errores = resultados.get("total_errores", 0)
                cache_hits = resultados.get("cache_hits", 0)
                api_calls = resultados.get("api_calls", 0)

                print(f"\n📊 RESULTADOS MASIVOS:")
                print(f"   ✅ Válidos: {total_validos}")
                print(f"   ❌ Inválidos: {total_invalidos}")
                print(f"   ⚠️  Errores: {total_errores}")
                print(f"   💾 Cache hits: {cache_hits}")
                print(f"   📡 Llamadas API: {api_calls}")
                print(f"   ⏱️  Tiempo total: {elapsed:.2f} segundos")

                # Mostrar algunos ejemplos
                if resultados.get("validos"):
                    print(f"\n📝 Ejemplos de RUCs válidos:")
                    for valido in resultados["validos"][:2]:
                        ruc = valido.get("ruc")
                        data = valido.get("data", {})
                        razon_social = data.get(
                            "nombre_o_razon_social", "NO DISPONIBLE"
                        )[:40]
                        print(f"   • {ruc}: {razon_social}...")

                if resultados.get("invalidos"):
                    print(f"\n📝 Ejemplos de RUCs inválidos:")
                    for invalido in resultados["invalidos"][:2]:
                        ruc = invalido.get("ruc")
                        error = invalido.get("error", "Error desconocido")
                        print(f"   • {ruc}: {error}")

                # Evaluar resultados esperados
                expected_valid_min = 4  # Esperamos al menos 4 válidos
                expected_invalid_min = 3  # Esperamos al menos 3 inválidos

                if (
                    total_validos >= expected_valid_min
                    and total_invalidos >= expected_invalid_min
                ):
                    self.log_test(
                        "Consulta RUC Masiva",
                        "PASS",
                        f"{total_validos} válidos, {total_invalidos} inválidos, {total_errores} errores",
                    )
                else:
                    self.log_test(
                        "Consulta RUC Masiva",
                        "WARNING",
                        f"Esperados: ≥{expected_valid_min} válidos, ≥{expected_invalid_min} inválidos | "
                        f"Obtenidos: {total_validos} válidos, {total_invalidos} inválidos",
                    )

            else:
                self.log_test(
                    "Consulta RUC Masiva",
                    "FAIL",
                    f"Error: {resultados.get('error', 'Error desconocido')}",
                )

            # Mostrar reporte de RUCs inválidos en cache
            invalid_report = self.migo_service.get_invalid_rucs_report()
            if invalid_report.get("total_invalidos", 0) > 0:
                print(
                    f"\n📋 RUCS INVALIDOS EN CACHE: {invalid_report['total_invalidos']}"
                )
                for inv_ruc in invalid_report.get("invalid_rucs", [])[:3]:
                    print(f"   • {inv_ruc.get('ruc')}: {inv_ruc.get('reason')}")

        except Exception as e:
            self.log_test("Consulta RUC Masiva", "FAIL", f"Error: {str(e)}")

    def test_migo_tipo_cambio(self):
        """Test de consulta de tipo de cambio."""
        self.print_header("TEST TIPO DE CAMBIO")

        try:
            # Primero limpiar cache para forzar consulta real
            fecha_hoy = datetime.now().date().isoformat()
            self.cache_service.delete(f"tc_{fecha_hoy}")

            # Nota: Asumiendo que migo_service tiene método para tipo de cambio
            # Si no existe, esto es solo un ejemplo de cómo se implementaría

            print("⚠️  Nota: La implementación de tipo de cambio en MigoService")
            print("       debe ser agregada según los endpoints disponibles.")
            print("       Este test es un template para cuando se implemente.")

            self.log_test(
                "Tipo de Cambio", "WARNING", "Implementación pendiente en MigoService"
            )

        except Exception as e:
            self.log_test("Tipo de Cambio", "FAIL", f"Error: {str(e)}")

    def test_migo_invalid_rucs_management(self):
        """Test de manejo de RUCs inválidos."""
        self.print_header("TEST MANEJO DE RUCS INVALIDOS")

        try:
            # RUCs específicos para este test
            ruc_test_1 = "99900011122"  # RUC de prueba inválido
            ruc_test_2 = "99900011123"  # Otro RUC de prueba

            # Limpiar cache primero
            self.cache_service.clear_invalid_rucs()

            # Test 1: Marcar RUC como inválido manualmente
            print(f"\n1. Marcando RUC {ruc_test_1} como inválido...")
            self.cache_service.add_invalid_ruc(
                ruc_test_1, reason="TEST_MANUAL_INVALIDO", ttl_hours=1
            )

            # Test 2: Verificar que está marcado como inválido
            is_invalid = self.cache_service.is_ruc_invalid(ruc_test_1)

            if is_invalid:
                print(f"   ✅ RUC {ruc_test_1} correctamente marcado como inválido")
            else:
                print(f"   ❌ RUC {ruc_test_1} NO está marcado como inválido")

            # Test 3: Consultar RUC marcado como inválido (debería usar cache)
            print(f"\n2. Consultando RUC {ruc_test_1} (debería usar cache)...")
            resultado = self.migo_service.consultar_ruc(
                ruc_test_1, update_partner=False
            )

            if resultado.get("cache_hit") and resultado.get("cache_type") == "invalid":
                print(f"   ✅ Correctamente evitó consulta API (cache hit)")
                self.log_test(
                    "Evitar consulta RUC inválido",
                    "PASS",
                    f"RUC {ruc_test_1} evitó API mediante cache",
                )
            else:
                print(f"   ❌ Se consultó API en lugar de usar cache")
                self.log_test(
                    "Evitar consulta RUC inválido",
                    "FAIL",
                    f"Cache hit: {resultado.get('cache_hit')}, Type: {resultado.get('cache_type')}",
                )

            # Test 4: Obtener reporte de inválidos
            print(f"\n3. Obteniendo reporte de RUCs inválidos...")
            reporte = self.migo_service.get_invalid_rucs_report()

            if reporte.get("total_invalidos", 0) > 0:
                print(
                    f"   ✅ Reporte obtenido: {reporte['total_invalidos']} RUCs inválidos"
                )
                self.log_test(
                    "Reporte RUCs inválidos",
                    "PASS",
                    f"{reporte['total_invalidos']} RUCs en reporte",
                )
            else:
                print(f"   ❌ Reporte vacío")
                self.log_test("Reporte RUCs inválidos", "FAIL", "Reporte vacío")

            # Test 5: Limpiar RUC inválido específico
            print(f"\n4. Limpiando RUC {ruc_test_1} del cache de inválidos...")
            clear_result = self.migo_service.clear_invalid_rucs_cache(ruc_test_1)

            if clear_result.get("success"):
                print(f"   ✅ RUC {ruc_test_1} removido del cache")

                # Verificar que ya no está marcado como inválido
                still_invalid = self.cache_service.is_ruc_invalid(ruc_test_1)
                if not still_invalid:
                    self.log_test(
                        "Remover RUC inválido específico",
                        "PASS",
                        f"RUC {ruc_test_1} correctamente removido",
                    )
                else:
                    self.log_test(
                        "Remover RUC inválido específico",
                        "FAIL",
                        f"RUC {ruc_test_1} aún marcado como inválido",
                    )
            else:
                self.log_test(
                    "Remover RUC inválido específico",
                    "FAIL",
                    f"Error: {clear_result.get('message')}",
                )

            # Test 6: Limpiar todo el cache de inválidos
            print(f"\n5. Limpiando todo el cache de inválidos...")
            # Agregar otro RUC primero
            self.cache_service.add_invalid_ruc(ruc_test_2, reason="TEST_LIMPIEZA")

            clear_all_result = self.migo_service.clear_invalid_rucs_cache()
            after_clear = self.cache_service.get_all_invalid_rucs()

            if clear_all_result.get("success") and len(after_clear) == 0:
                print(f"   ✅ Cache de inválidos limpiado completamente")
                self.log_test("Limpiar todo cache inválidos", "PASS", "Cache limpiado")
            else:
                self.log_test(
                    "Limpiar todo cache inválidos",
                    "WARNING",
                    f"Clear result: {clear_all_result.get('success')}, "
                    f"After clear: {len(after_clear)} RUCs",
                )

        except Exception as e:
            self.log_test("Manejo RUCs Inválidos", "FAIL", f"Error: {str(e)}")

    def test_integracion_completa(self):
        """Test de integración completa de todos los componentes."""
        self.print_header("TEST INTEGRACIÓN COMPLETA")

        try:
            print("🚀 Ejecutando flujo completo de integración...")

            # Paso 1: Configurar RUCs inválidos en cache
            rucs_invalidos_setup = ["88877766655", "88877766656"]
            for ruc in rucs_invalidos_setup:
                self.cache_service.add_invalid_ruc(
                    ruc, reason="TEST_INTEGRACION", ttl_hours=1
                )

            print(
                f"✅ {len(rucs_invalidos_setup)} RUCs configurados como inválidos en cache"
            )

            # Paso 2: Realizar consulta masiva que incluya RUCs inválidos
            rucs_consulta = [
                "20100038146",  # Válido
                "88877766655",  # Inválido (en cache)
                "20100049008",  # Válido
                "88877766656",  # Inválido (en cache)
                "99988877766",  # Inválido (no en cache, será detectado por API)
            ]

            print(
                f"📦 Consultando {len(rucs_consulta)} RUCs (mix válidos/inválidos)..."
            )
            resultados = self.migo_service.consultar_ruc_masivo(
                rucs_consulta,
                batch_size=2,
                update_partners=False,  # No actualizar partners para prueba
            )

            # Paso 3: Analizar resultados
            if resultados.get("success"):
                cache_hits = resultados.get("cache_hits", 0)
                api_calls = resultados.get("api_calls", 0)

                print(f"\n📊 Resultados integración:")
                print(f"   💾 Cache hits: {cache_hits} (deberían ser ≥2)")
                print(f"   📡 Llamadas API: {api_calls}")
                print(f"   ✅ Válidos: {resultados.get('total_validos', 0)}")
                print(f"   ❌ Inválidos: {resultados.get('total_invalidos', 0)}")

                # Verificar que se usó el cache para RUCs inválidos conocidos
                if cache_hits >= 2:
                    self.log_test(
                        "Integración Cache-API",
                        "PASS",
                        f"Cache hits: {cache_hits}, API calls: {api_calls}",
                    )
                else:
                    self.log_test(
                        "Integración Cache-API",
                        "WARNING",
                        f"Pocos cache hits: {cache_hits} (esperados ≥2)",
                    )
            else:
                self.log_test(
                    "Integración Cache-API",
                    "FAIL",
                    f"Error en consulta masiva: {resultados.get('error')}",
                )

            # Paso 4: Verificar reporte final
            reporte_final = self.migo_service.get_invalid_rucs_report()
            print(
                f"\n📋 Reporte final RUCs inválidos: {reporte_final.get('total_invalidos', 0)}"
            )

            # Limpieza
            self.cache_service.clear_invalid_rucs()

        except Exception as e:
            self.log_test("Integración Completa", "FAIL", f"Error: {str(e)}")

    # ============================================================================
    # MENÚ Y EJECUCIÓN
    # ============================================================================

    def run_all_tests(self):
        """Ejecuta todos los tests."""
        self.print_header("INICIANDO TESTS V2 - SERVICIOS MEJORADOS")
        print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Ejecutar tests en orden
        self.test_cache_basico()
        self.test_cache_rucs_invalidos()
        self.test_migo_ruc_individual()
        self.test_migo_ruc_masivo()
        self.test_migo_invalid_rucs_management()
        self.test_integracion_completa()

        # Mostrar resumen
        self.print_summary()

    def run_interactive_menu(self):
        """Menú interactivo para ejecutar tests selectivamente."""
        while True:
            self.print_header("MENÚ TESTS V2")
            print("Seleccione una opción:")
            print(" 1. 🔄 Ejecutar TODOS los tests")
            print(" 2. 💾 Tests Cache Service")
            print(" 3. 🚀 Tests Migo Service")
            print(" 4. 🎯 Test específico")
            print(" 5. 📊 Ver resultados anteriores")
            print(" 0. 🚪 Salir")
            print("-" * 40)

            try:
                opcion = input("Opción: ").strip()

                if opcion == "1":
                    self.run_all_tests()
                    input("\nPresione Enter para continuar...")

                elif opcion == "2":
                    self.print_header("TESTS CACHE SERVICE")
                    self.test_cache_basico()
                    self.test_cache_rucs_invalidos()
                    self.print_summary()
                    input("\nPresione Enter para continuar...")

                elif opcion == "3":
                    self.print_header("TESTS MIGO SERVICE")
                    self.test_migo_ruc_individual()
                    self.test_migo_ruc_masivo()
                    self.test_migo_invalid_rucs_management()
                    self.print_summary()
                    input("\nPresione Enter para continuar...")

                elif opcion == "4":
                    self.print_header("TEST ESPECÍFICO")
                    print("1. Test Cache Básico")
                    print("2. Test Cache RUCs Inválidos")
                    print("3. Test RUC Individual")
                    print("4. Test RUC Masivo")
                    print("5. Test Manejo RUCs Inválidos")
                    print("6. Test Integración Completa")

                    sub_opcion = input("Seleccione test: ").strip()

                    tests_map = {
                        "1": self.test_cache_basico,
                        "2": self.test_cache_rucs_invalidos,
                        "3": self.test_migo_ruc_individual,
                        "4": self.test_migo_ruc_masivo,
                        "5": self.test_migo_invalid_rucs_management,
                        "6": self.test_integracion_completa,
                    }

                    if sub_opcion in tests_map:
                        tests_map[sub_opcion]()
                        self.print_summary()
                    else:
                        print("❌ Opción inválida")

                    input("\nPresione Enter para continuar...")

                elif opcion == "5":
                    import glob

                    result_files = glob.glob("test_results_v2_*.json")
                    if result_files:
                        print("\n📁 Archivos de resultados disponibles:")
                        for i, file in enumerate(
                            sorted(result_files, reverse=True)[:5], 1
                        ):
                            print(f"  {i}. {file}")
                    else:
                        print("📭 No hay archivos de resultados anteriores")
                    input("\nPresione Enter para continuar...")

                elif opcion == "0":
                    print("👋 Saliendo...")
                    break

                else:
                    print("❌ Opción inválida, intente nuevamente")

            except KeyboardInterrupt:
                print("\n\n👋 Interrumpido por el usuario")
                break
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                input("\nPresione Enter para continuar...")


def main():
    """Función principal."""
    print("=" * 60)
    print("🧪 TEST FLUJO FACTURACIÓN V2")
    print("   Servicios mejorados con manejo de RUCs inválidos")
    print("=" * 60)

    tester = TestFlujoFacturacionV2()

    # Verificar argumentos de línea de comandos
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            tester.run_all_tests()
        elif sys.argv[1] == "--cache":
            tester.test_cache_basico()
            tester.test_cache_rucs_invalidos()
            tester.print_summary()
        elif sys.argv[1] == "--migo":
            tester.test_migo_ruc_individual()
            tester.test_migo_ruc_masivo()
            tester.test_migo_invalid_rucs_management()
            tester.print_summary()
        else:
            print("Uso: python test_flujo_facturacion_v2.py [--all|--cache|--migo]")
            print("     Sin argumentos: Menú interactivo")
    else:
        # Modo interactivo por defecto
        tester.run_interactive_menu()


if __name__ == "__main__":
    main()
