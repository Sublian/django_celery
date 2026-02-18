# api_service/tests/conftest.py
import pytest
import pytest_asyncio
from asgiref.sync import sync_to_async
from api_service.models import ApiService, ApiEndpoint

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_nubefact_service():
    """Fixture que asegura que el servicio NubeFact existe en BD"""
    
    # Crear servicio si no existe
    service, created = await sync_to_async(ApiService.objects.get_or_create)(
        name="NUBEFACT Perú",
        defaults={
            "base_url": "https://api.nubefact.com",
            "auth_token": "test_token_para_pruebas"
        }
    )
    
    # Crear endpoints si no existen
    endpoints = [
        ("generar_comprobante", "POST", "/api/v1/comprobante"),
        ("consultar_comprobante", "GET", "/api/v1/comprobante"),
        ("anular_comprobante", "POST", "/api/v1/comprobante/anular"),
    ]
    
    for name, method, path in endpoints:
        await sync_to_async(ApiEndpoint.objects.get_or_create)(
            service=service,
            name=name,
            defaults={
                "method": method,
                "path": path
            }
        )
    
    yield service
    
    # Cleanup opcional - no eliminar si otros tests lo necesitan
    # await sync_to_async(service.delete)()