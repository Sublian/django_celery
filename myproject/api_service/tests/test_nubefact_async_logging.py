import os
import sys
import django
import pytest
import anyio

# Configurar Django
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# Importar servicio y modelos
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync, NubefactValidationError
# from api_service.services.nubefact.exceptions import NubefactValidationError
from api_service.models import ApiCallLog, ApiService, ApiEndpoint


async def test_logging_on_error():
    """Verificar que los errores se loguean correctamente"""
    service = NubefactServiceAsync()
    
    # Datos inválidos
    bad_data = {"tipo_de_comprobante": "X"}
    
    with pytest.raises(NubefactValidationError):
        await service.generar_comprobante(bad_data)
    
    # Verificar que se creó el log
    log = ApiCallLog.objects.latest('created_at')
    assert log.status == 'FAILED'
    assert log.error_message is not None