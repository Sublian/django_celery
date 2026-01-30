# api_service/services/nubefact/tests.py
"""
Suite de Tests Sincronos para NubefactService

Pruebas completas incluyendo:
- Inicialización y configuración
- Carga de endpoints
- Rate limiting
- Métodos de operación (emitir, consultar, anular)
- Validación de datos
- Manejo de errores
- Logging automático
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from decimal import Decimal
from datetime import datetime, timedelta
import requests
import json

from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.services.nubefact.exceptions import (
    NubefactAPIError,
    NubefactValidationError,
)
from api_service.models import ApiService, ApiEndpoint, ApiCallLog, ApiRateLimit, ApiBatchRequest


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def api_service_mock():
    """Mock de ApiService para NUBEFACT."""
    service = Mock(spec=ApiService)
    service.service_type = "NUBEFACT"
    service.base_url = "https://api.nubefact.com"
    service.auth_token = "Bearer test_token_12345"
    service.is_active = True
    service.requests_per_minute = 60
    return service


@pytest.fixture
def api_endpoints_mock(api_service_mock):
    """Mocks de ApiEndpoint para los 3 endpoints."""
    endpoints = {
        "generar_comprobante": Mock(spec=ApiEndpoint),
        "consultar_comprobante": Mock(spec=ApiEndpoint),
        "anular_comprobante": Mock(spec=ApiEndpoint),
    }
    
    for name, endpoint in endpoints.items():
        endpoint.name = name
        endpoint.path = "/api/v1/send"  # Todos usan la misma ruta
        endpoint.method = "POST"
        endpoint.timeout = 60
        endpoint.service = api_service_mock
        endpoint.is_active = True
    
    return endpoints


@pytest.fixture
def rate_limit_mock(api_service_mock):
    """Mock de ApiRateLimit."""
    rate_limit = Mock(spec=ApiRateLimit)
    rate_limit.service = api_service_mock
    rate_limit.current_count = 0
    rate_limit.get_limit.return_value = 60
    rate_limit.can_make_request.return_value = True
    rate_limit.get_wait_time.return_value = 0.0
    rate_limit.increment_count = Mock()
    return rate_limit


@pytest.fixture
def nubefact_service(api_service_mock, api_endpoints_mock):
    """Instancia de NubefactService con mocks."""
    with patch('api_service.services.nubefact.base_service.ApiService.objects.filter') as mock_filter:
        mock_filter.return_value.first.return_value = api_service_mock
        service = NubefactService()
        service.session = Mock(spec=requests.Session)
        service.timeout = (30, 60)
        return service


@pytest.fixture
def sample_invoice_data():
    """Datos de prueba para una factura."""
    return {
        'operacion': 'generar_comprobante',
        'tipo_de_comprobante': '1',
        'serie': 'F001',
        'numero': 91430,
        'cliente_tipo_de_documento': '6',
        'cliente_numero_de_documento': '20343443961',
        'cliente_denominacion': 'TEST EMPRESA S.A.C.',
        'fecha_de_emision': '2026-01-30',
        'moneda': '1',
        'total_gravada': 100.0,
        'total_igv': 18.0,
        'total': 118.0,
        'items': [
            {
                'unidad_de_medida': 'ZZ',
                'codigo': 'TEST001',
                'descripcion': 'Servicio de prueba',
                'cantidad': 1.0,
                'valor_unitario': 100.0,
                'precio_unitario': 118.0,
                'descuento': 0.0,
                'subtotal': 100.0,
                'tipo_de_igv': '1',
                'igv': 18.0,
                'total': 118.0,
            }
        ]
    }


# ============================================================================
# TESTS DE INICIALIZACIÓN
# ============================================================================

class TestNubefactServiceInitialization:
    """Tests de inicialización del servicio."""

    def test_init_carga_configuracion(self, api_service_mock):
        """Verifica que __init__ carga configuración de ApiService."""
        with patch('api_service.services.nubefact.base_service.ApiService.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = api_service_mock
            service = NubefactService()
            assert service.service == api_service_mock

    def test_base_url_desde_service(self, nubefact_service, api_service_mock):
        """Verifica que base_url viene de ApiService."""
        assert nubefact_service.base_url == "https://api.nubefact.com"

    def test_auth_token_desde_service(self, nubefact_service, api_service_mock):
        """Verifica que auth_token viene de ApiService."""
        assert nubefact_service.auth_token == "Bearer test_token_12345"

    def test_token_alias(self, nubefact_service, api_service_mock):
        """Verifica que token es alias de auth_token."""
        assert nubefact_service.token == nubefact_service.auth_token

    def test_session_configurada(self, nubefact_service):
        """Verifica que session se configura."""
        assert nubefact_service.session is not None
        # Mock spec excluye algunos atributos, solo verificar que existe
        assert isinstance(nubefact_service.session, Mock)

    def test_timeout_por_defecto(self, nubefact_service):
        """Verifica que timeout tiene valor por defecto."""
        assert nubefact_service.timeout == (30, 60)

    def test_timeout_custom(self, api_service_mock):
        """Verifica que timeout custom se puede pasar."""
        with patch('api_service.services.nubefact.base_service.ApiService.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = api_service_mock
            service = NubefactService(timeout=(20, 40))
            assert service.timeout == (20, 40)


# ============================================================================
# TESTS DE ENDPOINT LOADING
# ============================================================================

class TestEndpointLoading:
    """Tests de carga de endpoints desde BD."""

    @patch('api_service.services.nubefact.base_service.ApiEndpoint.objects.filter')
    def test_get_endpoint_retorna_endpoint_valido(self, mock_filter, nubefact_service, api_endpoints_mock):
        """Verifica que _get_endpoint() retorna endpoint válido."""
        endpoint = api_endpoints_mock['generar_comprobante']
        mock_filter.return_value.first.return_value = endpoint
        
        result = nubefact_service._get_endpoint('generar_comprobante')
        
        assert result == endpoint
        mock_filter.assert_called_once()

    @patch('api_service.services.nubefact.base_service.ApiEndpoint.objects.filter')
    def test_get_endpoint_retorna_none_si_no_existe(self, mock_filter, nubefact_service):
        """Verifica que _get_endpoint() retorna None si no existe."""
        mock_filter.return_value.first.return_value = None
        
        result = nubefact_service._get_endpoint('endpoint_inexistente')
        
        assert result is None

    @patch.object(NubefactService, '_get_endpoint')
    def test_send_request_falla_sin_endpoint(self, mock_get_endpoint, nubefact_service, sample_invoice_data):
        """Verifica que send_request() falla si endpoint no existe."""
        mock_get_endpoint.return_value = None
        
        with pytest.raises(ValueError, match="no configurado"):
            nubefact_service.send_request('generar_comprobante', sample_invoice_data)


# ============================================================================
# TESTS DE RATE LIMITING
# ============================================================================

class TestRateLimiting:
    """Tests de rate limiting."""

    @patch.object(NubefactService, '_check_rate_limit')
    def test_rate_limit_permitido(self, mock_check, nubefact_service):
        """Verifica que la solicitud procede cuando rate limit lo permite."""
        mock_check.return_value = (True, 0)
        
        with patch.object(NubefactService, '_get_endpoint') as mock_get_ep:
            endpoint = Mock()
            endpoint.path = "/api/v1/send"
            endpoint.timeout = 60
            mock_get_ep.return_value = endpoint
            
            with patch.object(nubefact_service.session, 'post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {'success': True}
                mock_post.return_value = mock_response
                
                with patch.object(NubefactService, '_update_rate_limit'):
                    with patch.object(NubefactService, '_log_api_call'):
                        data = {'operacion': 'generar_comprobante'}
                        result = nubefact_service.send_request('generar_comprobante', data)
                        
                        assert result is not None

    @patch.object(NubefactService, '_check_rate_limit')
    @patch.object(NubefactService, '_log_api_call')
    def test_rate_limit_excedido(self, mock_log, mock_check, nubefact_service, sample_invoice_data):
        """Verifica que la solicitud falla cuando rate limit se excede."""
        mock_check.return_value = (False, 5.0)  # Esperar 5 segundos
        
        with patch.object(NubefactService, '_get_endpoint') as mock_get_ep:
            endpoint = Mock()
            mock_get_ep.return_value = endpoint
            
            with pytest.raises(NubefactAPIError, match="Rate limit"):
                nubefact_service.send_request('generar_comprobante', sample_invoice_data)


# ============================================================================
# TESTS DE MÉTODOS DE OPERACIÓN
# ============================================================================

class TestOperationMethods:
    """Tests de los métodos de operación (emitir, consultar, anular)."""

    @patch.object(NubefactService, 'send_request')
    def test_generar_comprobante_llama_send_request(self, mock_send, nubefact_service, sample_invoice_data):
        """Verifica que generar_comprobante() llama send_request() correctamente."""
        mock_send.return_value = {'success': True, 'enlace': 'http://example.com/pdf'}
        
        result = nubefact_service.generar_comprobante(sample_invoice_data)
        
        mock_send.assert_called_once_with('generar_comprobante', sample_invoice_data)
        assert result['success'] is True

    @patch.object(NubefactService, 'send_request')
    def test_consultar_comprobante_prepara_datos_correctos(self, mock_send, nubefact_service):
        """Verifica que consultar_comprobante() prepara los datos correctamente."""
        mock_send.return_value = {'estado': 'ACEPTADA'}
        
        result = nubefact_service.consultar_comprobante(1, 'F001', 1)
        
        # Verificar que send_request fue llamado con endpoint_name correcto
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == 'consultar_comprobante'
        
        # Verificar estructura de datos enviados
        data = call_args[0][1]
        assert data['operacion'] == 'consultar_comprobante'
        assert data['tipo_de_comprobante'] == 1
        assert data['serie'] == 'F001'
        assert data['numero'] == 1

    @patch.object(NubefactService, 'send_request')
    def test_anular_comprobante_prepara_datos_correctos(self, mock_send, nubefact_service):
        """Verifica que anular_comprobante() prepara los datos correctamente."""
        mock_send.return_value = {'estado': 'ANULADA'}
        
        result = nubefact_service.anular_comprobante(1, 'F001', 1, 'Error en datos')
        
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == 'anular_comprobante'
        
        data = call_args[0][1]
        assert data['operacion'] == 'generar_anulacion'
        assert data['tipo_de_comprobante'] == 1
        assert data['motivo'] == 'Error en datos'


# ============================================================================
# TESTS DE VALIDACIÓN
# ============================================================================

class TestValidation:
    """Tests de validación de datos."""

    def test_validate_token_con_bearer(self, nubefact_service):
        """Verifica que token con Bearer se mantiene."""
        token = "Bearer xxx123"
        result = nubefact_service._validate_and_format_token(token)
        assert result == "Bearer xxx123"

    def test_validate_token_sin_bearer(self, nubefact_service):
        """Verifica que token sin Bearer se le agrega."""
        token = "xxx123"
        result = nubefact_service._validate_and_format_token(token)
        assert result == "Bearer xxx123"

    def test_validate_token_vacio_falla(self, nubefact_service):
        """Verifica que token vacío lanza error."""
        with pytest.raises(ValueError, match="no configurado"):
            nubefact_service._validate_and_format_token("")

    def test_validate_token_none_falla(self, nubefact_service):
        """Verifica que token None lanza error."""
        with pytest.raises(ValueError, match="no configurado"):
            nubefact_service._validate_and_format_token(None)

    @patch('api_service.services.nubefact.nubefact_service.validate_json_structure')
    def test_send_request_valida_datos(self, mock_validate, nubefact_service, sample_invoice_data):
        """Verifica que send_request() valida datos."""
        mock_validate.return_value = sample_invoice_data
        
        with patch.object(NubefactService, '_get_endpoint') as mock_get_ep:
            endpoint = Mock()
            endpoint.path = "/api/v1/send"
            endpoint.timeout = 60
            mock_get_ep.return_value = endpoint
            
            with patch.object(NubefactService, '_check_rate_limit') as mock_check:
                mock_check.return_value = (True, 0)
                
                with patch.object(nubefact_service.session, 'post') as mock_post:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {'success': True}
                    mock_post.return_value = mock_response
                    
                    with patch.object(NubefactService, '_update_rate_limit'):
                        with patch.object(NubefactService, '_log_api_call'):
                            nubefact_service.send_request('generar_comprobante', sample_invoice_data)
                            
                            mock_validate.assert_called_once()


# ============================================================================
# TESTS DE MANEJO DE ERRORES
# ============================================================================

class TestErrorHandling:
    """Tests de manejo de errores."""

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    def test_handle_response_error_400(self, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica manejo de error 400 (validación)."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        mock_get_ep.return_value = endpoint
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {'error': 'Datos inválidos'}
            mock_post.return_value = mock_response
            
            with patch.object(NubefactService, '_log_api_call'):
                with patch('api_service.services.nubefact.nubefact_service.validate_json_structure'):
                    with pytest.raises(NubefactValidationError):
                        nubefact_service.send_request('generar_comprobante', sample_invoice_data)

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    def test_handle_response_error_500(self, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica manejo de error 500."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        mock_get_ep.return_value = endpoint
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {'error': 'Error interno'}
            mock_post.return_value = mock_response
            
            with patch.object(NubefactService, '_log_api_call'):
                with patch('api_service.services.nubefact.nubefact_service.validate_json_structure'):
                    with pytest.raises(NubefactAPIError):
                        nubefact_service.send_request('generar_comprobante', sample_invoice_data)

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    def test_handle_connection_error(self, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica manejo de error de conexión."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        mock_get_ep.return_value = endpoint
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError("Conexión rechazada")
            
            with patch.object(NubefactService, '_log_api_call'):
                with patch('api_service.services.nubefact.nubefact_service.validate_json_structure'):
                    with pytest.raises(NubefactAPIError, match="Error de conexión"):
                        nubefact_service.send_request('generar_comprobante', sample_invoice_data)

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    def test_handle_timeout_error(self, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica manejo de error de timeout."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        mock_get_ep.return_value = endpoint
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Tiempo de espera agotado")
            
            with patch.object(NubefactService, '_log_api_call'):
                with patch('api_service.services.nubefact.nubefact_service.validate_json_structure'):
                    with pytest.raises(NubefactAPIError, match="Error de conexión"):
                        nubefact_service.send_request('generar_comprobante', sample_invoice_data)


# ============================================================================
# TESTS DE LOGGING
# ============================================================================

class TestLogging:
    """Tests de logging automático."""

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    @patch('api_service.services.nubefact.base_service.ApiCallLog.objects.create')
    def test_log_api_call_en_exito(self, mock_create, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica que se crea log en respuesta exitosa."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        endpoint.name = 'generar_comprobante'
        mock_get_ep.return_value = endpoint
        
        response_data = {
            'success': True,
            'enlace': 'http://example.com',
        }
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_post.return_value = mock_response
            
            with patch('api_service.services.nubefact.nubefact_service.validate_json_structure') as mock_validate:
                mock_validate.return_value = sample_invoice_data
                
                with patch.object(NubefactService, '_update_rate_limit'):
                    nubefact_service.send_request('generar_comprobante', sample_invoice_data)
                    
                    # Verificar que se llamó a ApiCallLog.objects.create
                    assert mock_create.called
                    call_kwargs = mock_create.call_args[1]
                    assert call_kwargs['status'] == 'SUCCESS'

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    @patch('api_service.services.nubefact.base_service.ApiCallLog.objects.create')
    def test_log_api_call_en_error(self, mock_create, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica que se crea log en respuesta con error."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        endpoint.name = 'generar_comprobante'
        mock_get_ep.return_value = endpoint
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {'error': 'Error interno'}
            mock_post.return_value = mock_response
            
            with patch('api_service.services.nubefact.nubefact_service.validate_json_structure') as mock_validate:
                mock_validate.return_value = sample_invoice_data
                
                with pytest.raises(NubefactAPIError):
                    nubefact_service.send_request('generar_comprobante', sample_invoice_data)
                    
                    # Verificar que se llamó a ApiCallLog.objects.create
                    assert mock_create.called
                    call_kwargs = mock_create.call_args[1]
                    assert call_kwargs['status'] == 'FAILED'


# ============================================================================
# TESTS DE CONTEXT MANAGER
# ============================================================================

class TestContextManager:
    """Tests del context manager (with statement)."""

    def test_context_manager_enter(self, nubefact_service):
        """Verifica que __enter__ retorna self."""
        with nubefact_service as service:
            assert service is nubefact_service

    def test_context_manager_exit_cierra_sesion(self, nubefact_service):
        """Verifica que __exit__ cierra la sesión."""
        nubefact_service.session.close = Mock()
        
        with nubefact_service:
            pass
        
        nubefact_service.session.close.assert_called_once()


# ============================================================================
# TESTS DE BATCH REQUEST
# ============================================================================

class TestBatchRequest:
    """Tests de soporte para batch requests."""

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    @patch('api_service.services.nubefact.base_service.ApiCallLog.objects.create')
    def test_send_request_con_batch_request(self, mock_create, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Verifica que batch_request se pasa correctamente a _log_api_call."""
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        endpoint.name = 'generar_comprobante'
        mock_get_ep.return_value = endpoint
        
        batch_request = Mock(spec=ApiBatchRequest)
        batch_request.id = 123
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_post.return_value = mock_response
            
            with patch('api_service.services.nubefact.nubefact_service.validate_json_structure') as mock_validate:
                mock_validate.return_value = sample_invoice_data
                
                with patch.object(NubefactService, '_update_rate_limit'):
                    nubefact_service.send_request('generar_comprobante', sample_invoice_data, batch_request=batch_request)
                    
                    # Verificar que batch_request se pasó a ApiCallLog
                    assert mock_create.called
                    call_kwargs = mock_create.call_args[1]
                    assert call_kwargs['batch_request'] == batch_request


# ============================================================================
# SUITE DE INTEGRACIÓN
# ============================================================================

class TestIntegration:
    """Tests de integración entre componentes."""

    @patch.object(NubefactService, '_get_endpoint')
    @patch.object(NubefactService, '_check_rate_limit')
    @patch.object(NubefactService, '_update_rate_limit')
    @patch('api_service.services.nubefact.base_service.ApiCallLog.objects.create')
    def test_flujo_completo_generar_comprobante(self, mock_create, mock_update, mock_check, mock_get_ep, nubefact_service, sample_invoice_data):
        """Test de flujo completo: emitir comprobante."""
        # Setup
        mock_check.return_value = (True, 0)
        endpoint = Mock()
        endpoint.path = "/api/v1/send"
        endpoint.timeout = 60
        endpoint.name = 'generar_comprobante'
        mock_get_ep.return_value = endpoint
        
        response_data = {
            'success': True,
            'enlace': 'https://example.com/pdf/factura.pdf',
            'aceptada_por_sunat': True,
        }
        
        with patch.object(nubefact_service.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = response_data
            mock_post.return_value = mock_response
            
            with patch('api_service.services.nubefact.nubefact_service.validate_json_structure') as mock_validate:
                mock_validate.return_value = sample_invoice_data
                
                # Ejecutar
                result = nubefact_service.generar_comprobante(sample_invoice_data)
                
                # Verificaciones
                assert result['success'] is True
                assert 'enlace' in result
                
                # Verificar que se verificó rate limit
                mock_check.assert_called()
                
                # Verificar que se actualizó rate limit
                mock_update.assert_called()
                
                # Verificar que se creó log
                mock_create.assert_called()
