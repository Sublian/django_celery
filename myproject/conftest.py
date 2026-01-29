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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

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
