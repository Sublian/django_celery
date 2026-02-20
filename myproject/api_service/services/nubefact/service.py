"""
Servicio asíncrono para Nubefact.
Utiliza NubefactHttpClient y logging separado.
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from asgiref.sync import sync_to_async

from .config import NubefactConfig
from .client import NubefactHttpClient
from .logging import save_api_log_async
from ..base.timeout_config import TimeoutConfig

logger = logging.getLogger(__name__)


class NubefactServiceAsync:
    """
    Servicio asíncrono para interactuar con Nubefact.
    """

    # Endpoints predefinidos (pueden ser sobrescritos por BD)
    DEFAULT_ENDPOINTS = {
        "generar_comprobante": {
            "path": "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223",
            "method": "POST",
        },
        "consultar_comprobante": {
            "path": "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223",
            "method": "POST",
        },
        "anular_comprobante": {
            "path": "/api/v1/4edbcfc4-1b83-482f-882a-1356c048d223",
            "method": "POST",
        },
    }

    def __init__(
        self,
        config: Optional[NubefactConfig] = None,
        timeout_config: Optional[TimeoutConfig] = None,
    ):
        self.config = config or NubefactConfig(timeout_config=timeout_config)
        self.client = NubefactHttpClient(self.config)
        self._initialized = False

    async def _ensure_initialized(self):
        if not self._initialized:
            await self.config.load_async()
            self._initialized = True

    async def _get_endpoint_path(self, name: str) -> str:
        """Obtiene el path del endpoint, primero desde BD, luego desde defaults."""
        try:
            from api_service.models import ApiEndpoint
            endpoint = await sync_to_async(ApiEndpoint.objects.get)(
                service__name="NUBEFACT Perú", name=name
            )
            return endpoint.path
        except Exception:
            # Si no está en BD, usar default
            if name in self.DEFAULT_ENDPOINTS:
                return self.DEFAULT_ENDPOINTS[name]["path"]
            raise ValueError(f"Endpoint {name} no configurado")

    async def _call(
        self,
        endpoint_name: str,
        data: Dict[str, Any],
        called_from: str,
    ) -> Dict[str, Any]:
        """
        Método interno para realizar llamadas y logging.
        """
        await self._ensure_initialized()
        path = await self._get_endpoint_path(endpoint_name)
        method = self.DEFAULT_ENDPOINTS.get(endpoint_name, {}).get("method", "POST")

        # Asegurar que los datos tengan 'operacion' si es necesario
        if endpoint_name in self.DEFAULT_ENDPOINTS and "operacion" not in data:
            data["operacion"] = endpoint_name

        # Realizar petición
        response = await self.client.request_async(method, path, data=data)

        # Extraer metadatos para logging
        metadata = response.pop("_metadata", {})
        status_code = metadata.get("status_code", 500)
        duration_ms = metadata.get("duration_ms", 0)

        # Guardar log (fuego y olvido)
        asyncio.create_task(
            save_api_log_async(
                endpoint_name=endpoint_name,
                status_code=status_code,
                duration_ms=duration_ms,
                request_data=data,
                response_data=response,
                called_from=called_from,
            )
        )

        return response

    async def generar_comprobante(
        self,
        data: Dict[str, Any],
        called_from: str = "NubefactServiceAsync.generar_comprobante",
    ) -> Dict[str, Any]:
        """
        Genera un comprobante.
        """
        # Validar que los valores numéricos sean strings (Nubefact lo exige)
        self._ensure_strings(data)
        return await self._call("generar_comprobante", data, called_from)

    async def consultar_comprobante(
        self,
        numero: str,
        called_from: str = "NubefactServiceAsync.consultar_comprobante",
    ) -> Dict[str, Any]:
        """
        Consulta un comprobante por número.
        """
        data = {"numero": numero, "operacion": "consultar_comprobante"}
        return await self._call("consultar_comprobante", data, called_from)

    async def anular_comprobante(
        self,
        numero: str,
        motivo: str,
        called_from: str = "NubefactServiceAsync.anular_comprobante",
    ) -> Dict[str, Any]:
        """
        Anula un comprobante.
        """
        data = {"numero": numero, "motivo": motivo, "operacion": "anular_comprobante"}
        return await self._call("anular_comprobante", data, called_from)

    def _ensure_strings(self, data: Dict):
        """
        Convierte valores numéricos a strings recursivamente en items.
        """
        numeric_fields = {
            "tipo_de_comprobante", "numero", "sunat_transaction",
            "total_gravada", "total_igv", "total", "cantidad",
            "precio_unitario", "subtotal", "igv", "valor_unitario",
            "descuento", "total_descuento"
        }
        for key, value in data.items():
            if key in numeric_fields and value is not None:
                data[key] = str(value)
            elif key == "items" and isinstance(value, list):
                for item in value:
                    self._ensure_strings(item)

    async def close(self):
        await self.client.close_async()

    async def __aenter__(self):
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()