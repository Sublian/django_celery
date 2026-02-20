# api_service/services/nubefact/client.py (versión mejorada)

"""
Cliente HTTP para Nubefact con soporte síncrono y asíncrono.
Maneja timeouts, reintentos y logging de errores.
"""

import httpx
from typing import Optional, Dict, Any
from datetime import datetime
from .config import NubefactConfig
from .exceptions import (
    NubefactAPIError,
    NubefactAuthenticationError,
    NubefactValidationError,
)
from .schemas.validators import sanitize_token


class NubefactHttpClient:
    """
    Cliente HTTP asíncrono para NubeFact.
    """
    
    # Mapeo de códigos de error de Nubefact a excepciones específicas
    _ERROR_MAP = {
        10: NubefactAuthenticationError,
        11: NubefactAuthenticationError,
        20: NubefactValidationError,
        21: NubefactValidationError,
        22: NubefactValidationError,
        23: NubefactValidationError,
        24: NubefactValidationError,
    }
    
    def __init__(self, config: Optional[NubefactConfig] = None):
        self.config = config or NubefactConfig().load_sync()
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Construye headers para peticiones."""
        token = sanitize_token(self.config.auth_token)
        if not token.startswith("Bearer "):
            token = f"Bearer {token}"
        
        return {
            "Content-Type": "application/json",
            "Authorization": token,
            "Accept": "application/json",
        }
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """Obtiene o crea cliente asíncrono."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_config.httpx_timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=100),
                verify=True
            )
        return self._client
    
    def _get_sync_client(self) -> httpx.Client:
        """Obtiene o crea cliente síncrono."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=self.config.timeout_config.httpx_timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=100),
                verify=True
            )
        return self._sync_client
    
    def _handle_response(self, response: httpx.Response, response_data: dict) -> dict:
        """Procesa la respuesta y lanza excepciones apropiadas."""
        
        # Verificar errores HTTP
        if response.status_code == 401:
            raise NubefactAuthenticationError(
                "Token de autorización inválido o faltante."
            )
        elif response.status_code == 400:
            error_msg = response_data.get("errors", "Solicitud incorrecta.")
            raise NubefactValidationError(f"Error de validación: {error_msg}")
        elif response.status_code >= 500:
            raise NubefactAPIError(
                f"Error interno del servidor Nubefact: {response.status_code}"
            )
        
        # Verificar errores específicos de Nubefact en el JSON
        if "codigo" in response_data and response_data["codigo"] in self._ERROR_MAP:
            error_class = self._ERROR_MAP[response_data["codigo"]]
            error_desc = response_data.get("errors", "Error desconocido")
            raise error_class(f"Código {response_data['codigo']}: {error_desc}")
        
        return response_data
    
    async def request_async(
        self,
        method: str,
        endpoint_path: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Realiza petición asíncrona a NubeFact.
        """
        client = await self._get_async_client()
        url = f"{self.config.base_url}/{endpoint_path.lstrip('/')}"
        headers = self._get_headers()
        
        start = datetime.now()
        
        try:
            resp = await client.request(
                method=method,
                url=url,
                json=data,
                headers=headers
            )
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            try:
                response_data = resp.json()
            except:
                response_data = {"error": "Respuesta no JSON", "text": resp.text}
            
            # Añadir metadata
            response_data["_metadata"] = {
                "status_code": resp.status_code,
                "duration_ms": int(duration),
                "url": url
            }
            
            return self._handle_response(resp, response_data)
            
        except httpx.TimeoutException as e:
            raise NubefactAPIError(f"Timeout: {str(e)}")
        except httpx.RequestError as e:
            raise NubefactAPIError(f"Error de conexión: {str(e)}")
    
    def request_sync(
        self,
        method: str,
        endpoint_path: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Realiza petición síncrona a NubeFact.
        """
        client = self._get_sync_client()
        url = f"{self.config.base_url}/{endpoint_path.lstrip('/')}"
        headers = self._get_headers()
        
        start = datetime.now()
        
        try:
            resp = client.request(
                method=method,
                url=url,
                json=data,
                headers=headers
            )
            
            duration = (datetime.now() - start).total_seconds() * 1000
            
            try:
                response_data = resp.json()
            except:
                response_data = {"error": "Respuesta no JSON", "text": resp.text}
            
            response_data["_metadata"] = {
                "status_code": resp.status_code,
                "duration_ms": int(duration),
                "url": url
            }
            
            return self._handle_response(resp, response_data)
            
        except httpx.TimeoutException as e:
            raise NubefactAPIError(f"Timeout: {str(e)}")
        except httpx.RequestError as e:
            raise NubefactAPIError(f"Error de conexión: {str(e)}")
    
    async def close_async(self):
        """Cierra cliente asíncrono."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def close_sync(self):
        """Cierra cliente síncrono."""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_async()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_sync()