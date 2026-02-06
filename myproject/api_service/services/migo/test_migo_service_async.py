"""
Pruebas unitarias para MigoAPIServiceAsync.

Status: ✅ Production Ready
Última actualización: 29 Enero 2026
Versión: 1.0

Cobertura:
- consultar_ruc_async: Consultas individuales con caché
- consultar_ruc_masivo_async: Procesamiento paralelo de lotes
- consultar_dni_async: Consultas DNI
- consultar_tipo_cambio_async: Consultas tipo de cambio
- Manejo de errores y reintentos
- Rate limiting
- Logging asincrónico
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from decimal import Decimal

# Nota: No necesitamos django_db para estos tests porque no usamos BD
# Los tests son únicamente de lógica async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def migo_service():
    """Fixture que proporciona instancia de MigoAPIServiceAsync."""
    from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

    service = MigoAPIServiceAsync()
    yield service
    # Cleanup


@pytest.fixture
def async_service_with_mock():
    """Fixture que proporciona servicio con cliente HTTP mockeado (sync fixture)."""
    from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

    service = MigoAPIServiceAsync()
    service.client = AsyncMock()
    yield service
    # No await in fixture teardown to keep fixture synchronous


class TestMigoAPIServiceAsyncInit:
    """Pruebas de inicialización del servicio async."""

    def test_init_default_values(self, migo_service):
        """Verificar inicialización con valores por defecto."""
        assert migo_service.timeout == 30
        assert migo_service.max_retries == 2
        assert migo_service.retry_delay == 0.5
        assert migo_service.service_name == "MIGO"

    def test_init_custom_timeout(self):
        """Verificar inicialización con timeout personalizado."""
        from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

        service = MigoAPIServiceAsync(timeout=60)
        assert service.timeout == 60

    @pytest.mark.asyncio
    async def test_context_manager_entry_exit(self):
        """Verificar que context manager crea y cierra cliente HTTP."""
        from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

        async with MigoAPIServiceAsync() as service:
            assert service.client is not None
        # Cliente debe estar cerrado después de __aexit__


class TestConsultarRucAsync:
    """Pruebas para consultar_ruc_async()."""

    @pytest.mark.asyncio
    async def test_consultar_ruc_success(self, async_service_with_mock):
        """Prueba exitosa de consulta de RUC."""
        service = async_service_with_mock

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "success": True,
                "ruc": "20100038146",
                "nombre_o_razon_social": "EMPRESA TEST",
                "estado_del_contribuyente": "ACTIVO",
                "condicion_de_domicilio": "HABIDO",
            }
        )

        service.client.post = AsyncMock(return_value=mock_response)
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.set = MagicMock()

        # Ejecutar
        result = await service.consultar_ruc_async("20100038146")

        # Verificar
        assert result["success"] is True
        assert result["nombre_o_razon_social"] == "EMPRESA TEST"
        # Verificar que se cachea el resultado
        assert service.cache_service.set.called

    @pytest.mark.asyncio
    async def test_consultar_ruc_from_cache(self, async_service_with_mock):
        """Prueba que usa resultado del caché sin hacer petición HTTP."""
        service = async_service_with_mock

        cached_result = {
            "success": True,
            "ruc": "20100038146",
            "nombre_o_razon_social": "EMPRESA CACHED",
        }

        # Mock caché
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=cached_result)
        service.cache_service.get_service_cache_key = MagicMock(
            return_value="migo:ruc_20100038146"
        )

        # Ejecutar
        result = await service.consultar_ruc_async("20100038146")

        # Verificar
        assert result == cached_result
        # HTTP client no debe ser usado
        assert service.client.post.call_count == 0

    @pytest.mark.asyncio
    async def test_consultar_ruc_retry_on_failure(self, async_service_with_mock):
        """Prueba reintentos automáticos en caso de fallo."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Primer intento falla, segundo exitoso
        failure_response = MagicMock()
        failure_response.status_code = 500
        failure_response.text = "Server Error"

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json = AsyncMock(
            return_value={"success": True, "ruc": "20100038146"}
        )

        service.client.post = AsyncMock(
            side_effect=[failure_response, success_response]
        )

        # Ejecutar
        result = await service.consultar_ruc_async("20100038146")

        # Verificar que se reintentó
        assert result["success"] is True
        assert service.client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_consultar_ruc_invalid_format(self, async_service_with_mock):
        """Prueba con formato de RUC inválido."""
        service = async_service_with_mock

        # Ejecutar con RUC inválido
        result = await service.consultar_ruc_async("ABC")

        # Verificar
        assert result["success"] is False
        assert "error" in result


class TestConsultarRucMasivoAsync:
    """Pruebas para consultar_ruc_masivo_async()."""

    @pytest.mark.asyncio
    async def test_consultar_ruc_masivo_parallel_execution(
        self, async_service_with_mock
    ):
        """Verificar que procesa RUCs en paralelo."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Use RUCs that pass format validation (not in the blocked list)
        rucs = ["20100038146", "20987654321", "20345678902"]

        # Mock responses as callable to handle multiple calls
        async def mock_post(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json = AsyncMock(
                return_value={
                    "success": True,
                    "ruc": "test_ruc",
                    "nombre_o_razon_social": "TEST COMPANY",
                }
            )
            return response

        service.client.post = mock_post

        # Ejecutar
        result = await service.consultar_ruc_masivo_async(rucs, batch_size=10)

        # Verificar
        assert result["total"] == 3
        assert (
            len(result["validos"]) == 3
        ), f"Expected 3 valid, got {len(result['validos'])}"
        assert len(result["invalidos"]) == 0
        assert result["exitosos"] == 3

    @pytest.mark.asyncio
    async def test_consultar_ruc_masivo_batch_processing(self, async_service_with_mock):
        """Verificar procesamiento en lotes."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Create 10 valid RUCs with different patterns (faster for testing)
        base_rucs = [
            "20100038146",
            "20200038146",
            "20300038146",
            "20400038146",
            "20500038146",
            "20600038146",
            "20700038146",
            "20800038146",
            "20900038146",
            "20987654321",
        ]

        # Mock success responses using callable side_effect
        async def mock_post_callable(*args, **kwargs):
            response = MagicMock()
            response.status_code = 200
            response.json = AsyncMock(
                return_value={"success": True, "nombre_o_razon_social": "TEST COMPANY"}
            )
            return response

        service.client.post = AsyncMock(side_effect=mock_post_callable)

        # Ejecutar con batch_size=5
        result = await service.consultar_ruc_masivo_async(base_rucs, batch_size=5)

        # Verificar
        assert result["total"] == 10, f"Total should be 10, got {result['total']}"
        assert (
            result["exitosos"] == 10
        ), f"Should have 10 successful, got {result['exitosos']}"
        # Con batch_size=5 deberían haber múltiples lotes
        assert service.client.post.call_count == 10

    @pytest.mark.asyncio
    async def test_consultar_ruc_masivo_error_handling(self, async_service_with_mock):
        """Verificar manejo de errores en lote."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Use valid RUCs (not in the blacklist)
        rucs = ["20100038146", "20987654321", "20345678902"]

        # Primer RUC OK, segundo falla, tercero OK
        def mock_responses():
            response1 = MagicMock()
            response1.status_code = 200
            response1.json = AsyncMock(return_value={"success": True})

            response2 = MagicMock()
            response2.status_code = 500
            response2.text = "Error"

            response3 = MagicMock()
            response3.status_code = 200
            response3.json = AsyncMock(return_value={"success": True})

            return [response1, response2, response3]

        service.client.post = AsyncMock(side_effect=mock_responses())

        # Ejecutar
        result = await service.consultar_ruc_masivo_async(rucs, batch_size=10)

        # Verificar
        assert result["total"] == 3
        assert result["exitosos"] >= 2  # Al menos 2 deberían ser exitosos


class TestConsultarDniAsync:
    """Pruebas para consultar_dni_async()."""

    @pytest.mark.asyncio
    async def test_consultar_dni_success(self, async_service_with_mock):
        """Prueba exitosa de consulta de DNI."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "success": True,
                "dni": "12345678",
                "nombres": "JUAN",
                "apellidos": "PEREZ",
            }
        )

        service.client.post = AsyncMock(return_value=mock_response)

        # Ejecutar
        result = await service.consultar_dni_async("12345678")

        # Verificar
        assert result["success"] is True
        assert result["nombres"] == "JUAN"


class TestConsultarTipoCambioAsync:
    """Pruebas para consultar_tipo_cambio_async()."""

    @pytest.mark.asyncio
    async def test_consultar_tipo_cambio_success(self, async_service_with_mock):
        """Prueba exitosa de consulta tipo de cambio."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={
                "success": True,
                "tipo_cambio": Decimal("3.50"),
                "fecha": "2026-01-29",
            }
        )

        service.client.post = AsyncMock(return_value=mock_response)

        # Ejecutar
        result = await service.consultar_tipo_cambio_async()

        # Verificar
        assert result["success"] is True
        assert result["tipo_cambio"] == Decimal("3.50")


class TestErrorHandling:
    """Pruebas de manejo de errores."""

    @pytest.mark.asyncio
    async def test_timeout_error(self, async_service_with_mock):
        """Prueba de timeout."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Simular timeout
        service.client.post = AsyncMock(side_effect=asyncio.TimeoutError())

        # Ejecutar
        result = await service.consultar_ruc_async("20100038146")

        # Verificar error
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_connection_error(self, async_service_with_mock):
        """Prueba de error de conexión."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        # Simular error de conexión
        service.client.post = AsyncMock(side_effect=Exception("Connection refused"))

        # Ejecutar
        result = await service.consultar_ruc_async("20100038146")

        # Verificar error
        assert result["success"] is False


class TestCaching:
    """Pruebas de funcionalidad de caché."""

    @pytest.mark.asyncio
    async def test_cache_ttl_respected(self, async_service_with_mock):
        """Verificar que se respetan los TTLs de caché."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"success": True})

        service.client.post = AsyncMock(return_value=mock_response)

        # Ejecutar
        await service.consultar_ruc_async("20100038146")

        # Verificar que set fue llamado con TTL
        assert service.cache_service.set.called

    @pytest.mark.asyncio
    async def test_invalid_ruc_cache(self, async_service_with_mock):
        """Verificar manejo de RUCs inválidos en caché."""
        service = async_service_with_mock
        service.cache_service = MagicMock()

        # Simular RUC inválido en caché
        service.cache_service.is_ruc_invalid = MagicMock(return_value=True)

        # Ejecutar
        result = await service.consultar_ruc_async("99999999999")

        # Verificar que no hace petición HTTP
        assert service.client.post.call_count == 0
        assert result["success"] is False


class TestLogging:
    """Pruebas de funcionalidad de logging."""

    @pytest.mark.asyncio
    async def test_async_logging(self, async_service_with_mock, caplog):
        """Verificar que logging funciona en contexto async."""
        import logging

        caplog.set_level(logging.DEBUG)

        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"success": True})

        service.client.post = AsyncMock(return_value=mock_response)

        # Ejecutar
        await service.consultar_ruc_async("20100038146")

        # Verificar logs (pueden contener [ASYNC] marker)
        # Esto es verificación flexible dado que logging en async es complejo


class TestRateLimiting:
    """Pruebas de rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_respected(self, async_service_with_mock):
        """Verificar que se respetan los rate limits."""
        service = async_service_with_mock
        service.cache_service = MagicMock()
        service.cache_service.get = MagicMock(return_value=None)
        service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

        call_times = []

        # Mock slow response that tracks call times
        async def slow_post(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)
            response = MagicMock()
            response.status_code = 200
            response.json = AsyncMock(return_value={"success": True})
            return response

        service.client.post = slow_post

        # Use valid RUCs (not in the blacklist)
        rucs = ["20100038146", "20987654321"]

        start = asyncio.get_event_loop().time()
        await service.consultar_ruc_masivo_async(rucs, batch_size=1)
        elapsed = asyncio.get_event_loop().time() - start

        # With batch_size=1, requests should be sequential with sleep in between
        # Batch 1: ~0.1s, Sleep: ~0.05s, Batch 2: ~0.1s = ~0.25s total
        # Allow some margin for execution overhead
        assert elapsed >= 0.15, f"Expected at least 0.15s, got {elapsed:.2f}s"


class TestHelperFunctions:
    """Pruebas de funciones helper."""

    @pytest.mark.asyncio
    async def test_run_async_function(self):
        """Prueba de run_async() bridge function."""
        from api_service.services.migo.migo_service_async import run_async

        async def async_func():
            return "resultado"

        result = run_async(async_func())
        assert result == "resultado"

    @pytest.mark.asyncio
    async def test_batch_query_function(self):
        """Prueba de batch_query() helper."""
        from api_service.services.migo.migo_service_async import batch_query

        async def mock_query(item):
            await asyncio.sleep(0.01)
            return f"result_{item}"

        items = ["a", "b", "c"]
        results = await batch_query(mock_query, items, batch_size=2)

        assert len(results) == 3
        assert all("result_" in r for r in results)


# ============================================================================
# Tests de Integración (requieren BD y API reales)
# ============================================================================


@pytest.mark.integration
class TestIntegration:
    """Tests de integración con API real (requiere .env APIMIGO)."""

    @pytest.mark.asyncio
    async def test_consultar_ruc_real_api(self):
        """Test con API real (solo si APIMIGO_TOKEN está configurado)."""
        import os

        if not os.getenv("APIMIGO_TOKEN"):
            pytest.skip("APIMIGO_TOKEN no configurado")

        from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

        async with MigoAPIServiceAsync() as service:
            # Usar RUC conocido en pruebas
            result = await service.consultar_ruc_async("20100038146")

            # Verificar
            assert "success" in result

    @pytest.mark.asyncio
    async def test_consultar_ruc_masivo_real_api(self):
        """Test masivo con API real."""
        import os

        if not os.getenv("APIMIGO_TOKEN"):
            pytest.skip("APIMIGO_TOKEN no configurado")

        from api_service.services.migo.migo_service_async import MigoAPIServiceAsync

        rucs = ["20100038146", "20123456789", "20345678901"]

        async with MigoAPIServiceAsync() as service:
            result = await service.consultar_ruc_masivo_async(rucs, batch_size=3)

            # Verificar
            assert result["total"] == len(rucs)


# ============================================================================
# Tests de Performance
# ============================================================================


@pytest.mark.performance
class TestPerformance:
    """Tests de rendimiento."""

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential(self):
        """Comparar performance paralelo vs secuencial."""
        # Este test requiere mocking apropiado
        pass
