"""
Configuración de pytest para Django
Este archivo se ejecuta automáticamente antes de los tests
"""

import os
import sys
import django
from pathlib import Path

# Asegurar que la ruta de Django está en el PATH
django_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(django_dir))

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    raise

import pytest


@pytest.fixture(scope="session", autouse=True)
def django_setup():
    """
    Fixture que asegura que Django está configurado para toda la sesión de tests
    """
    # Django ya está configurado arriba, pero esto asegura que se ejecute
    # antes de cualquier test
    yield
    # Cleanup si es necesario


@pytest.fixture
def cache_service():
    """
    Fixture que proporciona una instancia limpia de APICacheService
    """
    from api_service.services.cache_service import APICacheService

    cache = APICacheService()
    yield cache

    # Cleanup: limpiar cache después de cada test
    try:
        cache.clear()
    except Exception:
        pass  # Ignorar errores en cleanup


@pytest.fixture
def api_service_migo():
    """
    Fixture que proporciona o crea ApiService para MIGO si no existe
    Esto permite ejecutar tests incluso si el servicio no está en BD
    """
    from api_service.models import ApiService, ApiEndpoint

    # Intentar obtener el servicio MIGO existente
    service = ApiService.objects.filter(service_type="MIGO").first()

    if not service:
        # Si no existe, crear uno de prueba
        service = ApiService.objects.create(
            service_type="MIGO",
            base_url="https://api.migo.pe",
            auth_token="test_token_migo",
            is_active=True,
        )

        # Crear endpoints comunes para MIGO
        endpoints_config = [
            ("consulta_cuenta", "/api/v1/account", 30),
            ("consulta_ruc", "/api/v1/ruc", 30),
            ("consulta_dni", "/api/v1/dni", 30),
            ("consulta_ruc_masivo", "/api/v1/ruc/collection", 60),
            ("tipo_cambio_latest", "/api/v1/exchange/latest", 30),
            ("tipo_cambio_fecha", "/api/v1/exchange/date", 30),
            ("tipo_cambio_rango", "/api/v1/exchange", 30),
            ("representantes_legales", "/api/v1/ruc/representantes-legales", 30),
        ]

        for name, path, timeout in endpoints_config:
            ApiEndpoint.objects.get_or_create(
                service=service,
                name=name,
                defaults={"path": path, "timeout": timeout, "method": "POST"},
            )

    yield service

    # No eliminar el servicio después del test, es compartido
