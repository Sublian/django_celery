# Ejemplos de integración de MigoAPIServiceAsync en Django
# archivo: myproject/api_service/views_async.py

"""
Vistas async de Django usando MigoAPIServiceAsync.

Estos ejemplos muestran patrones recomendados para integrar
el servicio async en vistas, endpoints y tareas de background.

Status: ✅ Ejemplos listos para usar
Última actualización: 29 Enero 2026
Versión: 1.0
"""

import asyncio
import logging
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import sync_and_async_middleware
from django.db import transaction

from api_service.services.migo_service_async import (
    MigoAPIServiceAsync,
    run_async,
    batch_query,
)
from api_service.models import ApiCallLog
from partners.models import Partner

logger = logging.getLogger(__name__)

# ============================================================================
# 1. VISTAS ASINCRÓNICAS (Django 3.1+)
# ============================================================================


class ConsultarRucAsyncView(View):
    """
    ✅ Vista async para consultar RUC individual.

    Endpoint: POST /api/ruc/consultar-async/
    Parámetros:
    - ruc: RUC a consultar
    """

    async def post(self, request):
        """Consultar RUC de forma async."""
        try:
            ruc = request.POST.get("ruc", "").strip()

            if not ruc:
                return JsonResponse(
                    {"success": False, "error": "RUC es requerido"}, status=400
                )

            # Usar servicio async
            async with MigoAPIServiceAsync() as service:
                result = await service.consultar_ruc_async(ruc)

            # Log (async-safe)
            await self._log_call_async(ruc, result)

            return JsonResponse(result)

        except Exception as e:
            logger.error(f"Error en ConsultarRucAsyncView: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    async def _log_call_async(self, ruc, result):
        """Log de consulta en BD (async-safe)."""
        # Usar sync_to_async para operaciones ORM
        from asgiref.sync import sync_to_async

        await sync_to_async(ApiCallLog.objects.create)(
            service_name="MIGO",
            endpoint="consultar_ruc",
            request_data={"ruc": ruc},
            response_data=result,
            success=result.get("success", False),
        )


class ConsultarRucMasivoAsyncView(View):
    """
    ✅ Vista async para consultar múltiples RUCs en paralelo.

    Endpoint: POST /api/ruc/consultar-masivo-async/
    Parámetros (JSON):
    {
        "rucs": ["20100038146", "20123456789", ...],
        "batch_size": 10,
        "update_partners": true
    }
    """

    async def post(self, request):
        """Consultar múltiples RUCs en paralelo."""
        import json
        from asgiref.sync import sync_to_async

        try:
            data = json.loads(request.body)
            rucs = data.get("rucs", [])
            batch_size = data.get("batch_size", 10)
            update_partners = data.get("update_partners", False)

            if not rucs:
                return JsonResponse(
                    {"success": False, "error": "Lista de RUCs requerida"}, status=400
                )

            # ⏱️ Inicio de cronómetro
            start_time = datetime.now()

            # Consultar RUCs en paralelo
            async with MigoAPIServiceAsync() as service:
                results = await service.consultar_ruc_masivo_async(
                    rucs, batch_size=batch_size, update_partners=update_partners
                )

            # ⏱️ Fin de cronómetro
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Actualizar Partners si aplica (async-safe)
            if update_partners and results["validos"]:
                await self._actualizar_partners_async(results["validos"])

            # Log de operación
            await self._log_operation_async(rucs, results, duration_ms)

            # Respuesta
            response = {
                "success": True,
                "total_consultados": results["total"],
                "exitosos": results["exitosos"],
                "validos": len(results["validos"]),
                "invalidos": len(results["invalidos"]),
                "errores": len(results["errores"]),
                "duration_ms": results.get("duration_ms", 0),
                "data": {
                    "validos": results["validos"],
                    "invalidos": results["invalidos"],
                    "errores": results["errores"],
                },
            }

            return JsonResponse(response)

        except Exception as e:
            logger.error(f"Error en ConsultarRucMasivoAsyncView: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    async def _actualizar_partners_async(self, resultados_validos):
        """Actualizar Partners con datos de SUNAT."""
        from asgiref.sync import sync_to_async

        for resultado in resultados_validos:
            ruc = resultado.get("ruc")
            try:
                # Buscar Partner por RUC (sync_to_async)
                def get_partner():
                    return Partner.objects.filter(ruc=ruc).first()

                partner = await sync_to_async(get_partner)()

                if partner:
                    # Actualizar datos
                    def update_partner():
                        partner.legal_name = resultado.get("nombre_o_razon_social")
                        partner.status = resultado.get("estado_del_contribuyente")
                        partner.last_sunat_check = datetime.now()
                        partner.save()

                    await sync_to_async(update_partner)()
                    logger.info(f"✅ Partner {ruc} actualizado desde SUNAT")

            except Exception as e:
                logger.error(f"❌ Error actualizando Partner {ruc}: {e}")

    async def _log_operation_async(self, rucs, results, duration_ms):
        """Log de operación masiva."""
        from asgiref.sync import sync_to_async

        await sync_to_async(ApiCallLog.objects.create)(
            service_name="MIGO",
            endpoint="consultar_ruc_masivo",
            request_data={"total_rucs": len(rucs)},
            response_data={
                "exitosos": results["exitosos"],
                "validos": len(results["validos"]),
                "invalidos": len(results["invalidos"]),
                "duration_ms": duration_ms,
            },
            success=True,
        )


class ConsultarDniAsyncView(View):
    """
    ✅ Vista async para consultar DNI.

    Endpoint: POST /api/dni/consultar-async/
    Parámetros:
    - dni: DNI a consultar
    """

    async def post(self, request):
        """Consultar DNI de forma async."""
        from asgiref.sync import sync_to_async

        try:
            dni = request.POST.get("dni", "").strip()

            if not dni:
                return JsonResponse(
                    {"success": False, "error": "DNI es requerido"}, status=400
                )

            # Consultar DNI
            async with MigoAPIServiceAsync() as service:
                result = await service.consultar_dni_async(dni)

            # Log
            await sync_to_async(ApiCallLog.objects.create)(
                service_name="MIGO",
                endpoint="consultar_dni",
                request_data={"dni": dni},
                response_data=result,
                success=result.get("success", False),
            )

            return JsonResponse(result)

        except Exception as e:
            logger.error(f"Error en ConsultarDniAsyncView: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class TipoCambioAsyncView(View):
    """
    ✅ Vista async para obtener tipo de cambio.

    Endpoint: GET /api/tipo-cambio/
    """

    async def get(self, request):
        """Obtener tipo de cambio actual."""
        try:
            async with MigoAPIServiceAsync() as service:
                result = await service.consultar_tipo_cambio_async()

            return JsonResponse(result)

        except Exception as e:
            logger.error(f"Error en TipoCambioAsyncView: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)


# ============================================================================
# 2. DECORADORES Y FUNCIONES HELPER
# ============================================================================


def async_api_view(view_func):
    """
    Decorador para vistas async.

    Uso:
    @async_api_view
    async def mi_vista(request):
        async with MigoAPIServiceAsync() as service:
            result = await service.consultar_ruc_async(ruc)
        return JsonResponse(result)
    """

    async def wrapper(request, *args, **kwargs):
        try:
            return await view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error en async view: {e}")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return wrapper


async def consultar_rucs_en_paralelo(rucs: list, max_concurrent=10):
    """
    Helper para consultar múltiples RUCs desde código arbitrario.

    Uso:
    results = await consultar_rucs_en_paralelo(['20100038146', '20123456789'])
    """
    async with MigoAPIServiceAsync() as service:
        tasks = [service.consultar_ruc_async(ruc) for ruc in rucs]
        results = await asyncio.gather(*tasks)

    return results


async def validar_rucs_batch(rucs: list, batch_size=10):
    """
    Helper para validar lote de RUCs y devolver separado en válidos/inválidos.

    Retorna: {validos, invalidos, errores}
    """
    async with MigoAPIServiceAsync() as service:
        result = await service.consultar_ruc_masivo_async(rucs, batch_size=batch_size)

    return {
        "validos": result["validos"],
        "invalidos": result["invalidos"],
        "errores": result["errores"],
        "total": result["total"],
    }


# ============================================================================
# 3. TAREAS DE CELERY ASYNC
# ============================================================================

# archivo: myproject/api_service/tasks.py

from celery import shared_task
from asgiref.sync import async_to_sync


@shared_task
def consultar_ruc_task(ruc: str):
    """
    Tarea Celery para consultar RUC de forma async.

    Uso:
    consultar_ruc_task.delay('20100038146')
    """
    logger.info(f"🔄 Iniciando consulta de RUC {ruc}")

    async def do_query():
        async with MigoAPIServiceAsync() as service:
            return await service.consultar_ruc_async(ruc)

    result = async_to_sync(do_query)()
    logger.info(f"✅ Consulta de RUC {ruc} completada: {result.get('success')}")
    return result


@shared_task
def consultar_rucs_masivo_task(rucs: list, batch_size=10, update_partners=False):
    """
    Tarea Celery para consultar múltiples RUCs.

    Uso:
    consultar_rucs_masivo_task.delay(
        ['20100038146', '20123456789'],
        batch_size=10,
        update_partners=True
    )
    """
    logger.info(f"🔄 Iniciando consulta masiva de {len(rucs)} RUCs")

    async def do_query():
        async with MigoAPIServiceAsync() as service:
            return await service.consultar_ruc_masivo_async(
                rucs, batch_size=batch_size, update_partners=update_partners
            )

    result = async_to_sync(do_query)()
    logger.info(
        f"✅ Consulta masiva completada: {result['exitosos']}/{result['total']}"
    )
    return result


@shared_task
def actualizar_partners_sunat():
    """
    Tarea periódica para actualizar datos de Partners desde SUNAT.

    Configurar en celery beat:
    - Nombre: 'actualizar_partners_sunat'
    - Schedule: crontab(hour=0, minute=0)  # Cada medianoche
    """
    logger.info("🔄 Iniciando actualización de Partners desde SUNAT")

    async def do_update():
        from partners.models import Partner

        # Obtener Partners sin revisar últimamente
        partners = Partner.objects.filter(last_sunat_check__isnull=True)[
            :1000
        ]  # Limitar a 1000 por ejecución

        rucs = [p.ruc for p in partners]

        if not rucs:
            logger.info("No hay Partners para actualizar")
            return

        async with MigoAPIServiceAsync() as service:
            results = await service.consultar_ruc_masivo_async(
                rucs, batch_size=20, update_partners=True
            )

        return results

    result = async_to_sync(do_update)()
    logger.info(f"✅ Actualización completada: {result}")
    return result


# ============================================================================
# 4. URLS
# ============================================================================

# archivo: myproject/api_service/urls.py (agregar estas rutas)

"""
from django.urls import path
from . import views_async

urlpatterns = [
    # Vistas async
    path('ruc/consultar-async/', views_async.ConsultarRucAsyncView.as_view(), 
         name='consultar_ruc_async'),
    path('ruc/consultar-masivo-async/', views_async.ConsultarRucMasivoAsyncView.as_view(), 
         name='consultar_ruc_masivo_async'),
    path('dni/consultar-async/', views_async.ConsultarDniAsyncView.as_view(), 
         name='consultar_dni_async'),
    path('tipo-cambio/', views_async.TipoCambioAsyncView.as_view(), 
         name='tipo_cambio_async'),
]
"""


# ============================================================================
# 5. FIXTURES Y UTILITIES PARA TESTING
# ============================================================================

# archivo: myproject/api_service/test_fixtures_async.py

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_migo_response():
    """Fixture que devuelve un mock de respuesta exitosa."""

    def _create_response(**kwargs):
        response = MagicMock()
        response.status_code = 200
        default_data = {
            "success": True,
            "ruc": "20100038146",
            "nombre_o_razon_social": "EMPRESA TEST",
            "estado_del_contribuyente": "ACTIVO",
        }
        default_data.update(kwargs)
        response.json = AsyncMock(return_value=default_data)
        return response

    return _create_response


@pytest.fixture
def sample_rucs():
    """Fixture con lista de RUCs de prueba."""
    return ["20100038146", "20123456789", "20345678901", "20567890123", "20789012345"]


@pytest.fixture
def async_service_mock(mock_migo_response):
    """Fixture que devuelve servicio con mocks."""
    from api_service.services.migo_service_async import MigoAPIServiceAsync

    service = MigoAPIServiceAsync()
    service.client = AsyncMock()
    service.cache_service = MagicMock()
    service.cache_service.get = MagicMock(return_value=None)
    service.cache_service.get_service_cache_key = MagicMock(
        side_effect=lambda svc, key: f"{svc}:{key}"
    )

    return service


# ============================================================================
# 6. EJEMPLOS DE SCRIPT STANDALONE
# ============================================================================

"""
# archivo: manage_commands/consultar_rucs_async.py

from django.core.management.base import BaseCommand
import asyncio
import csv
from api_service.services.migo_service_async import MigoAPIServiceAsync


class Command(BaseCommand):
    help = 'Consultar RUCs desde CSV usando async'
    
    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Archivo CSV con RUCs')
        parser.add_argument('--batch-size', type=int, default=10)
        parser.add_argument('--output', type=str, default='resultados.json')
    
    def handle(self, *args, **options):
        rucs = []
        
        # Leer RUCs del CSV
        with open(options['csv_file']) as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            rucs = [row[0] for row in reader]
        
        # Consultar en paralelo
        results = asyncio.run(self.consultar_async(
            rucs,
            options['batch_size']
        ))
        
        # Guardar resultados
        import json
        with open(options['output'], 'w') as f:
            json.dump(results, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {len(rucs)} RUCs procesados. Resultados en {options['output']}"
            )
        )
    
    async def consultar_async(self, rucs, batch_size):
        async with MigoAPIServiceAsync() as service:
            return await service.consultar_ruc_masivo_async(
                rucs,
                batch_size=batch_size
            )
"""


# ============================================================================
# Notas de Implementación
# ============================================================================

"""
✅ CHECKLIST DE IMPLEMENTACIÓN

1. Instalación
   □ pip install httpx>=0.27.0
   □ Verificar en requirements.txt

2. Configuración Django
   □ Copiar views_async.py a myproject/api_service/
   □ Actualizar urls.py con nuevas rutas
   □ Configurar ASGI server (uvicorn en dev, gunicorn en prod)

3. Tareas de Celery
   □ Actualizar tasks.py con nuevas tareas async
   □ Configurar celery beat para tareas periódicas

4. Testing
   □ Instalar pytest-asyncio
   □ Crear test_migo_service_async.py
   □ Ejecutar: pytest -m asyncio

5. Monitoreo
   □ Agregar logging para [ASYNC] operations
   □ Monitorear duration_ms en logs
   □ Alertas si duration > 5000ms

6. Documentación
   □ Actualizar equipo sobre endpoints async
   □ Crear runbook de troubleshooting
   □ Documentar performance expectations

⚠️ CONSIDERACIONES DE PRODUCCIÓN

- Django 3.1+ requerido para async views
- Usar ASGI server (uvicorn, hypercorn)
- Monitorear connection pool
- Testear con carga realista antes de deploy
- Implementar circuit breaker para API fallando
- Considerar cache warming antes de horarios pico
"""
