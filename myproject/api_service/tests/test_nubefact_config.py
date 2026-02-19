# api_service/tests/test_nubefact_config.py
import pytest
import pytest_asyncio
from asgiref.sync import sync_to_async
from .conftest_db import setup_nubefact_service

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_nubefact_config_loads_correctly(setup_nubefact_service):
    """Test que SÍ necesita BD - usando factory method asíncrono"""
    from api_service.services.nubefact.config import NubefactConfig
    
    # ✅ Usar factory method asíncrono
    config = await NubefactConfig.create()
    
    assert config.base_url == "https://api.nubefact.com"
    assert config.auth_token == "test_token_para_pruebas"
    assert config.timeout_config.connect_timeout == 10.0

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_nubefact_config_with_custom_timeout(setup_nubefact_service):
    """Test con timeout personalizado"""
    from api_service.services.nubefact.config import NubefactConfig
    from api_service.services.base.timeout_config import TimeoutConfig
    
    custom_timeout = TimeoutConfig(connect_timeout=5.0, read_timeout=60.0)
    config = await NubefactConfig.create(timeout_config=custom_timeout)
    
    assert config.timeout_config.connect_timeout == 5.0
    assert config.timeout_config.read_timeout == 60.0