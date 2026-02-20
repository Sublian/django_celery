# tests/integration/nubefact_flow/conftest.py

import pytest
import asyncio
from typing import Generator

from api_service.models import ApiService, ApiEndpoint
from django.db import connection


@pytest.fixture(scope="session")
def django_db_setup():
    """Configuración de base de datos para tests."""
    from django.conf import settings
    
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
    yield


@pytest.fixture(autouse=True)
def ensure_nubefact_service():
    """Asegura que el servicio NubeFact existe en BD."""
    from django.core.management import call_command
    
    # Esto asume que tienes un fixture o data migration que crea el servicio
    # Alternativamente, crearlo manualmente:
    try:
        service = ApiService.objects.get(name="NUBEFACT Perú")
    except ApiService.DoesNotExist:
        service = ApiService.objects.create(
            name="NUBEFACT Perú",
            base_url="https://api.nubefact.com",
            auth_token="tu_token_aqui",  # Configurar desde variable de entorno
            service_type="NUBEFACT",
            is_active=True
        )
    
    # Asegurar endpoints
    endpoints = [
        ("generar_comprobante", "POST", "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"),
        ("consultar_comprobante", "POST", "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"),
        ("anular_comprobante", "POST", "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223"),
    ]
    
    for name, method, path in endpoints:
        ApiEndpoint.objects.get_or_create(
            service=service,
            name=name,
            defaults={"method": method, "path": path}
        )
    
    yield