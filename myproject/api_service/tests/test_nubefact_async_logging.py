import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import os
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()

from api_service.models import ApiCallLog
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from api_service.services.nubefact.exceptions import NubefactValidationError
from asgiref.sync import sync_to_async


@pytest_asyncio.fixture(autouse=True)
async def clean_logs():
    """Limpiar logs antes de cada test"""
    await sync_to_async(ApiCallLog.objects.all().delete)()
    yield


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_logging_on_error():
    """Verificar que los errores se loguean correctamente"""
    
    service_async = NubefactServiceAsync()
    
    # ✅ Mockear rate limit update
    with patch.object(service_async, '_update_rate_limit_async', new_callable=AsyncMock):
        with patch.object(service_async, '_async_init', new_callable=AsyncMock):
            with patch.object(service_async, '_get_endpoint_sync') as mock_get_endpoint:
                mock_endpoint = MagicMock()
                mock_endpoint.path = "/api/v1/comprobante"
                mock_get_endpoint.return_value = mock_endpoint
                
                with patch.object(service_async, '_check_rate_limit_sync', return_value=(True, 0)):
                    with patch.object(service_async, '_ensure_client') as mock_ensure_client:
                        mock_response = AsyncMock()
                        mock_response.status_code = 400
                        mock_response.json = AsyncMock(return_value={"error": "Error"})
                        
                        mock_client = AsyncMock()
                        mock_client.post = AsyncMock(return_value=mock_response)
                        mock_ensure_client.return_value = mock_client
                        
                        with patch.object(
                            service_async,
                            '_handle_response_simple',
                            side_effect=NubefactValidationError("Error")
                        ):
                            mock_service = MagicMock()
                            mock_service.base_url = "https://api.nubefact.com"
                            
                            with patch.object(service_async, 'service', mock_service):
                                
                                bad_data = {"tipo_de_comprobante": "X"}
                                
                                initial_count = await sync_to_async(ApiCallLog.objects.count)()
                                
                                with pytest.raises(NubefactValidationError):
                                    await service_async.generar_comprobante(bad_data)
                                
                                await asyncio.sleep(0.5)
                                
                                final_count = await sync_to_async(ApiCallLog.objects.count)()
                                assert final_count == initial_count + 1


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_logging_success():
    """Verificar que los éxitos se loguean correctamente"""
    
    service_async = NubefactServiceAsync()
    
    # ✅ Mockear rate limit update
    with patch.object(service_async, '_update_rate_limit_async', new_callable=AsyncMock):
        with patch.object(service_async, '_async_init', new_callable=AsyncMock):
            with patch.object(service_async, '_get_endpoint_sync') as mock_get_endpoint:
                mock_endpoint = MagicMock()
                mock_endpoint.path = "/api/v1/comprobante"
                mock_get_endpoint.return_value = mock_endpoint
                
                with patch.object(service_async, '_check_rate_limit_sync', return_value=(True, 0)):
                    with patch.object(service_async, '_ensure_client') as mock_ensure_client:
                        mock_response_data = {
                            "success": True,
                            "numero": 99999,
                            "codigo_hash": "TEST_HASH_12345"
                        }
                        
                        mock_response = AsyncMock()
                        mock_response.status_code = 200
                        mock_response.json = AsyncMock(return_value=mock_response_data)
                        
                        mock_client = AsyncMock()
                        mock_client.post = AsyncMock(return_value=mock_response)
                        mock_ensure_client.return_value = mock_client
                        
                        with patch.object(
                            service_async,
                            '_handle_response_simple',
                            return_value=mock_response_data
                        ):
                            mock_service = MagicMock()
                            mock_service.base_url = "https://api.nubefact.com"
                            
                            with patch.object(service_async, 'service', mock_service):
                                
                                valid_data = {"test": "data"}
                                
                                initial_count = await sync_to_async(ApiCallLog.objects.count)()
                                
                                result = await service_async.generar_comprobante(valid_data)
                                
                                assert result['success'] is True
                                
                                await asyncio.sleep(0.5)
                                
                                final_count = await sync_to_async(ApiCallLog.objects.count)()
                                assert final_count == initial_count + 1


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_logging_with_http_error():
    """Verificar logging cuando hay error HTTP"""
    
    service_async = NubefactServiceAsync()
    
    # ✅ Mockear rate limit update
    with patch.object(service_async, '_update_rate_limit_async', new_callable=AsyncMock):
        with patch.object(service_async, '_async_init', new_callable=AsyncMock):
            with patch.object(service_async, '_get_endpoint_sync') as mock_get_endpoint:
                mock_endpoint = MagicMock()
                mock_endpoint.path = "/api/v1/comprobante"
                mock_get_endpoint.return_value = mock_endpoint
                
                with patch.object(service_async, '_check_rate_limit_sync', return_value=(True, 0)):
                    with patch.object(service_async, '_ensure_client') as mock_ensure_client:
                        mock_client = AsyncMock()
                        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
                        mock_ensure_client.return_value = mock_client
                        
                        mock_service = MagicMock()
                        mock_service.base_url = "https://api.nubefact.com"
                        
                        with patch.object(service_async, 'service', mock_service):
                            
                            bad_data = {"test": "data"}
                            
                            initial_count = await sync_to_async(ApiCallLog.objects.count)()
                            
                            with pytest.raises(Exception):
                                await service_async.generar_comprobante(bad_data)
                            
                            await asyncio.sleep(0.5)
                            
                            final_count = await sync_to_async(ApiCallLog.objects.count)()
                            assert final_count == initial_count + 1


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_logging_with_real_data():
    """Prueba con datos reales"""
    pytest.skip("Test manual - ejecutar sin --real")