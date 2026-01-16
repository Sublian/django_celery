from urllib import response
import requests
import time
import hashlib
import json
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from ..models import ApiService, ApiEndpoint, ApiCallLog, ApiRateLimit, ApiBatchRequest
from api_service.services.cache_service import APICacheService
import requests
from ..exceptions import (
    APIError,
    RateLimitExceededError,
    AuthenticationError,
    APINotFoundError,
    APIBadResponseError,
    APITimeoutError,
)
import logging

logger = logging.getLogger(__name__)


class MigoAPIClient:
    """Cliente específico para APIMIGO con todas sus funcionalidades"""

    def __init__(self, token=None):
        self.service = ApiService.objects.filter(service_type="MIGO").first()
        if not self.service:
            raise ValueError("Servicio APIMIGO no configurado")

        self.token = token or self.service.auth_token
        self.base_url = self.service.base_url
        # self.version = "1.0"  # Definir versión para User-Agent
        self.timeout = 30  # Definir timeout
        self.cache_service = APICacheService()

        # Mapeo de endpoints MIGO
        self.endpoints = {
            "consulta_cuenta": self._get_endpoint("consulta_cuenta", "/api/v1/account"),
            "consulta_ruc": self._get_endpoint("consulta_ruc", "/api/v1/ruc"),
            "consulta_dni": self._get_endpoint("consulta_dni", "/api/v1/dni"),
            "consulta_ruc_masivo": self._get_endpoint(
                "consulta_ruc_masivo", "/api/v1/ruc/collection"
            ),
            "tipo_cambio_latest": self._get_endpoint(
                "tipo_cambio_latest", "/api/v1/exchange/latest"
            ),
            "tipo_cambio_fecha": self._get_endpoint(
                "tipo_cambio_fecha", "/api/v1/exchange/date"
            ),
            "tipo_cambio_rango": self._get_endpoint(
                "tipo_cambio_rango", "/api/v1/exchange"
            ),
            "representantes_legales": self._get_endpoint(
                "representantes_legales", "/api/v1/ruc/representantes-legales"
            ),
        }
        # Mantener compatibilidad con métodos existentes
        self.endpoint_aliases = {
            "account": "consulta_cuenta",
            "ruc": "consulta_ruc",
            "dni": "consulta_dni",
        }

    def _get_endpoint(self, name, path):
        """Obtiene o crea un endpoint en la base de datos"""
        endpoint, created = ApiEndpoint.objects.get_or_create(
            service=self.service, path=path, defaults={"name": name, "method": "POST"}
        )
        return endpoint

    def _check_rate_limit(self, endpoint_name=None):
        """
        Verifica rate limit y lanza excepción si se excede.
        Solo debe lanzar excepción, NO devolver True/False.
        """
        # 1. Obtener endpoint si tenemos el nombre
        endpoint_obj = None
        if endpoint_name:
            endpoint_obj = self.endpoints.get(endpoint_name)

        # 2. Determinar límite real (endpoint específico o servicio general)
        if (
            endpoint_obj
            and hasattr(endpoint_obj, "custom_rate_limit")
            and endpoint_obj.custom_rate_limit
        ):
            limit = endpoint_obj.custom_rate_limit
        else:
            limit = self.service.requests_per_minute

        # 3. Obtener o crear rate limit
        rate_limit_obj, created = ApiRateLimit.objects.get_or_create(
            service=self.service
        )

        # 4. Verificar si puede hacer la petición
        if not rate_limit_obj.can_make_request():
            wait_time = rate_limit_obj.get_wait_time()

            # 5. Obtener información del caller de forma simple
            caller_info = self._get_caller_info()

            # 6. Crear request_data mejorado
            request_data = {
                "rate_limit_check": True,
                "attempted_endpoint": endpoint_name or "unknown",
                "caller": caller_info,
                "current_count": rate_limit_obj.current_count,
                "limit": limit,
                "wait_time_seconds": wait_time,
                "endpoint_specific_limit": (
                    endpoint_obj.custom_rate_limit if endpoint_obj else None
                ),
            }

            # 7. Crear log del rate limit
            api_log = ApiCallLog.objects.create(
                service=self.service,
                endpoint=endpoint_obj,
                status="RATE_LIMITED",
                request_data=request_data,
                error_message=f'Rate limit excedido. Límite: {limit}/min. Esperar: {wait_time}s. Endpoint intentado: {endpoint_name or "unknown"}',
                called_from=caller_info,
                response_code=429,
            )

            logger.warning(
                f"Rate limit excedido para {self.service.name}. "
                f"Endpoint: {endpoint_name}. Límite: {limit}/min. "
                f"Log ID: {api_log.id}"
            )

            # 8. Lanzar excepción
            raise RateLimitExceededError(wait_time, limit)

    def _make_request(self, endpoint_name, payload, endpoint_name_display=None):
        """Método base para hacer peticiones con auditoría completa"""

        # 1. Verificar rate limiting (lanza excepción si falla)
        self._check_rate_limit(endpoint_name=endpoint_name)

        # 2. Obtener endpoint
        endpoint = self.endpoints.get(endpoint_name)
        if not endpoint:
            api_log = ApiCallLog.objects.create(
                service=self.service,
                status="FAILED",
                request_data=payload,
                error_message=f"Endpoint no configurado: {endpoint_name}",
                called_from=self._get_caller_info(),
                response_code=400,
            )
            raise ValueError(f"Endpoint '{endpoint_name}' no configurado en el sistema")

        # 3. VERIFICAR SI EL ENDPOINT ESTÁ ACTIVO
        if not endpoint.is_active:
            # Crear log específico para endpoint inactivo
            api_log = ApiCallLog.objects.create(
                service=self.service,
                endpoint=endpoint,
                status="FAILED",
                request_data=payload,
                error_message=f"Endpoint inactivo: {endpoint.name}",
                called_from=self._get_caller_info(),
                response_code=403,  # Forbidden
            )
            raise ValueError(f"Endpoint '{endpoint.name}' está marcado como inactivo")

        url = f"{self.base_url.rstrip('/')}{endpoint.path}"

        # 3. Preparar payload con token
        payload_with_token = {"token": self.token, **payload}

        # 4. Crear log de auditoría
        api_log = ApiCallLog.objects.create(
            service=self.service,
            endpoint=endpoint,
            request_data=payload_with_token,
            called_from=self._get_caller_info(),
            status="PENDING",
        )

        try:
            start_time = time.time()

            # 5. Hacer petición HTTP
            response = requests.post(
                url,
                json=payload_with_token,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # 6. Procesar respuesta
            return self._process_response(response, api_log, endpoint_name, duration_ms)

        except requests.exceptions.Timeout:
            self._handle_exception(
                api_log,
                "Timeout de conexión",
                APITimeoutError("Timeout al conectar con APIMIGO"),
            )

        except requests.exceptions.ConnectionError:
            self._handle_exception(
                api_log,
                "Error de conexión",
                APIError("No se pudo conectar con APIMIGO"),
            )

        except Exception as e:
            self._handle_exception(api_log, str(e), e)

    def _get_caller_info(self):
        """Obtiene información simple sobre quién llamó"""
        import inspect

        stack = inspect.stack()

        # Buscar el primer caller fuera de esta clase
        for frame_info in stack[2:]:  # Saltar _get_caller_info y el método que lo llamó
            function_name = frame_info.function

            # Saltar métodos internos
            if function_name.startswith("_") and function_name not in ["__init__"]:
                continue

            if "self" in frame_info.frame.f_locals:
                caller = frame_info.frame.f_locals["self"]
                return f"{caller.__class__.__name__}.{function_name}"
            else:
                module = frame_info.frame.f_globals.get("__name__", "unknown")
                # Omitir módulos Django internos
                if not module.startswith("django."):
                    return f"{module}.{function_name}"

        return "unknown"

    # Métodos específicos de APIMIGO
    def consultar_cuenta(self):
        """Consulta información de la cuenta MIGO"""
        return self._make_request(
            endpoint_name="consulta_cuenta",
            payload={},
            endpoint_name_display="Consulta cuenta APIMIGO",
        )

    def consultar_ruc(self, ruc) -> dict:
        """Consulta individual de un RUC en SUNAT"""
        cache_key = f"ruc_{ruc}"

        # 1. Verificar cache primero
        cached_data = self.cache_service.get(cache_key)
        if cached_data:
            return {**cached_data, "cache_hit": True}

        # 2. Hacer consulta si no está en cache
        try:
            result = self._make_request("consulta_ruc", {"ruc": ruc})

            # Cachear por 24 horas si se encuentra
            if result.get("success"):
                cache.set(cache_key, result, 86400)
                return result.json()
            elif response.status_code == 404:
                # Manejar RUC no encontrado
                return {
                    "success": False,
                    "error": "RUC no encontrado",
                    "status_code": 404,
                }
            else:
                return {
                    "success": False,
                    "error": f"Error {response.status_code}",
                    "status_code": response.status_code,
                }
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def consultar_dni(self, dni):
        """Consulta datos de un DNI"""
        cache_key = f"migo_dni_{dni}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        result = self._make_request("consulta_dni", {"dni": dni})

        # Cachear por 24 horas
        if result.get("success"):
            cache.set(cache_key, result, 86400)

        return result

    def consultar_tipo_cambio_latest(self):
        """
        Consulta el tipo de cambio más reciente.
        Endpoint: POST /api/v1/exchange/latest
        Returns:
            Dict: Tipo de cambio del día más reciente
        """
        return self._make_request(
            endpoint_name="tipo_cambio_latest",
            payload={"token": self.token},
            endpoint_name_display="Consulta tipo cambio más reciente",
        )

    def consultar_tipo_cambio_fecha(self, fecha):
        """
        Consulta tipo de cambio para una fecha específica.
        Endpoint: POST /api/v1/exchange/date
        Args:
            fecha: Fecha en formato YYYY-MM-DD
        Returns:
            Dict: Tipo de cambio para la fecha especificada
        """
        return self._make_request(
            endpoint_name="tipo_cambio_fecha",
            payload={"token": self.token, "fecha": fecha},
            endpoint_name_display=f"Consulta tipo cambio fecha {fecha}",
        )

    def consultar_tipo_cambio_rango(self, fecha_inicio, fecha_fin):
        """
        Consulta tipo de cambio por rango de fechas.
        Endpoint: POST /api/v1/exchange
        Args:
            fecha_inicio: Fecha inicio (YYYY-MM-DD)
            fecha_fin: Fecha fin (YYYY-MM-DD)
        Returns:
            Dict: Tipos de cambio en el rango
        """
        return self._make_request(
            endpoint_name="tipo_cambio_rango",
            payload={
                "token": self.token,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
            },
            endpoint_name_display=f"Consulta tipo cambio rango {fecha_inicio} a {fecha_fin}",
        )

    def consultar_representantes_legales(self, ruc):
        """
        Consulta representantes legales de un RUC.
        Endpoint: POST /api/v1/ruc/representantes-legales
        Args:
            ruc: Número de RUC
        Returns:
            Dict: Lista de representantes legales
        """
        return self._make_request(
            endpoint_name="representantes_legales",
            payload={"token": self.token, "ruc": ruc},
            endpoint_name_display="Consulta representantes legales",
        )

    def validar_ruc_para_facturacion(self, ruc):
        """Verificación específica para facturación: RUC activo y habido"""

        try:
            resultado = self.consultar_ruc(ruc)

            if not resultado.get("success"):
                return {
                    "valido": False,
                    "ruc": ruc,
                    "razon_social": None,
                    "estado": None,
                    "condicion": None,
                    "direccion": None,
                    "errores": ["RUC no encontrado en SUNAT"],
                    "advertencias": [],
                }

            estado = resultado.get("estado_del_contribuyente", "").upper()
            condicion = resultado.get("condicion_de_domicilio", "").upper()

            errores = []
            advertencias = []

            # Validaciones críticas
            if estado != "ACTIVO":
                errores.append(f"Contribuyente no está ACTIVO (estado: {estado})")

            if condicion != "HABIDO":
                errores.append(f"Contribuyente no es HABIDO (condición: {condicion})")

            # Validaciones de datos
            razon_social = resultado.get("nombre_o_razon_social")
            if not razon_social or len(razon_social.strip()) < 3:
                advertencias.append("Razón social muy corta o vacía")

            direccion = resultado.get("direccion")
            if not direccion or len(direccion.strip()) < 10:
                advertencias.append("Dirección muy corta o incompleta")

            return {
                "valido": len(errores) == 0,
                "ruc": ruc,
                "razon_social": razon_social,
                "estado": estado,
                "condicion": condicion,
                "direccion": direccion,
                "data_completa": resultado,
                "errores": errores,
                "advertencias": advertencias,
            }

        except Exception as e:
            print(f"Error validando RUC {ruc}: {e}")
            return {
                "valido": False,
                "ruc": ruc,
                "razon_social": None,
                "errores": [f"Error de validación: {str(e)}"],
                "advertencias": [],
            }

    def _particionar_rucs_en_lotes(self, ruc_list, tamano_lote=None):
        """
        Particiona una lista de RUCs en lotes del tamaño especificado.
        Args:
            ruc_list: Lista de RUCs a particionar
            tamano_lote: Tamaño máximo de cada lote (por defecto 100, límite de APIMIGO)
        Returns:
            Lista de lotes (cada lote es una lista de RUCs)
        Ejemplo:
            >>> _particionar_rucs_en_lotes([1,2,3,4,5], 2)
            [[1,2], [3,4], [5]]
        """
        if not isinstance(ruc_list, list):
            raise ValueError("ruc_list debe ser una lista")
        # Determinar tamaño de lote
        if tamano_lote is None:
            if (
                self.service
                and hasattr(self.service, "max_batch_size")
                and self.service.max_batch_size
            ):
                tamano_lote = self.service.max_batch_size
            else:
                tamano_lote = 100  # Valor por defecto seguro
        if tamano_lote <= 0:
            raise ValueError("tamano_lote debe ser mayor a 0")

        # Normalizar RUCs antes de particionar
        lotes = []
        lote_actual = []

        for ruc in ruc_list:
            # Normalizar cada RUC
            if isinstance(ruc, (int, float)):
                ruc_normalizado = str(int(ruc))
            elif isinstance(ruc, str):
                ruc_normalizado = ruc.strip()
            else:
                raise ValueError(f"Tipo de dato no válido para RUC: {type(ruc)}")

            # Validar formato básico
            if len(ruc_normalizado) != 11 or not ruc_normalizado.isdigit():
                raise ValueError(
                    f"RUC inválido: {ruc_normalizado}. Debe tener 11 dígitos"
                )

            lote_actual.append(ruc_normalizado)

            # Si el lote alcanzó el tamaño máximo, agregarlo y comenzar uno nuevo
            if len(lote_actual) >= tamano_lote:
                lotes.append(lote_actual)
                lote_actual = []

        # Agregar el último lote si no está vacío
        if lote_actual:
            lotes.append(lote_actual)

        return lotes

    def _analizar_facturacion(self, resultados):
        """
        Analiza qué RUCs están habilitados para facturación según SUNAT.

        Criterios para facturación válida:
        1. Estado: ACTIVO (no BAJA, SUSPENSION_TEMPORAL, etc.)
        2. Condición: HABIDO (no NO_HABIDO)
        3. Tipo de contribuyente: No debe ser EXTRANJERO_NO_DOMICILIADO sin ciertas condiciones
        4. Ubicación: Debe tener dirección válida en Perú

        Args:
            resultados: Lista de diccionarios con datos de RUC

        Returns:
            dict con análisis de facturación
        """
        habilitados = []
        no_habilitados = []
        advertencias = []

        for item in resultados:
            if not isinstance(item, dict) or not item.get("success"):
                # Si no es exitoso, no se puede analizar
                no_habilitados.append(
                    {
                        "ruc": item.get("ruc", "DESCONOCIDO"),
                        "razon": item.get("nombre_o_razon_social", ""),
                        "motivo": "Consulta fallida",
                        "detalle": item.get("error", "Error desconocido"),
                    }
                )
                continue

            ruc = item.get("ruc")
            razon = item.get("nombre_o_razon_social", "")
            estado = item.get("estado_del_contribuyente", "")
            condicion = item.get("condicion_de_domicilio", "")
            tipo_contribuyente = item.get("tipo_contribuyente", "")

            motivos_rechazo = []
            advertencias_ruc = []

            # 1. Verificar estado
            if estado != "ACTIVO":
                motivos_rechazo.append(f"Estado: {estado}")

            # 2. Verificar condición
            if condicion != "HABIDO":
                motivos_rechazo.append(f"Condición: {condicion}")

            # 3. Verificar tipo de contribuyente
            if tipo_contribuyente in ["EXTRANJERO_NO_DOMICILIADO", "NO_DOMICILIADO"]:
                advertencias_ruc.append(
                    f"Tipo contribuyente: {tipo_contribuyente} - Verificar retenciones"
                )

            # 4. Verificar dirección
            direccion = item.get("direccion", "")
            if not direccion or len(direccion.strip()) < 10:
                advertencias_ruc.append("Dirección incompleta o muy corta")

            # 5. Verificar actualización (si tiene más de 1 año, podría estar desactualizado)
            actualizado_en = item.get("actualizado_en", "")
            if actualizado_en:
                try:
                    from datetime import datetime

                    fecha_actualizacion = datetime.strptime(
                        actualizado_en, "%Y-%m-%d %H:%M:%S"
                    )
                    dias_desde_actualizacion = (
                        datetime.now() - fecha_actualizacion
                    ).days
                    if dias_desde_actualizacion > 365:
                        advertencias_ruc.append(
                            f"Datos desactualizados ({dias_desde_actualizacion} días)"
                        )
                except:
                    pass

            # Clasificar resultado
            if not motivos_rechazo:
                habilitados.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "estado": estado,
                        "condicion": condicion,
                        "advertencias": advertencias_ruc,
                        "direccion": (
                            direccion[:100] + "..."
                            if len(direccion) > 100
                            else direccion
                        ),
                        "actualizado_en": actualizado_en,
                    }
                )
            else:
                # if motivos_rechazo:
                no_habilitados.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "motivos": motivos_rechazo,
                        "estado": estado,
                        "condicion": condicion,
                    }
                )

            if advertencias_ruc:
                advertencias.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "advertencias": advertencias_ruc,
                    }
                )

        return {
            "total_analizados": len(resultados),
            "habilitados_facturacion": {
                "cantidad": len(habilitados),
                "porcentaje": (
                    (len(habilitados) / len(resultados) * 100) if resultados else 0
                ),
                "items": habilitados,
            },
            "no_habilitados_facturacion": {
                "cantidad": len(no_habilitados),
                "porcentaje": (
                    (len(no_habilitados) / len(resultados) * 100) if resultados else 0
                ),
                "items": no_habilitados,
            },
            "advertencias": {
                "cantidad": len(advertencias),
                "porcentaje": (
                    (len(advertencias) / len(resultados) * 100) if resultados else 0
                ),
                "items": advertencias,
            },
        }

    def validar_rucs_para_facturacion(self, ruc_list):
        """
        Valida específicamente si RUCs están habilitados para facturación.
        Args:
            ruc_list: Lista de RUCs a validar
        Returns:
            dict con validación detallada por RUC
        """
        # Consultar los RUCs
        resultado = self.consultar_ruc_masivo(ruc_list)

        if not resultado.get("success"):
            return {
                "success": False,
                "error": resultado.get("error", "Error en consulta"),
                "validaciones": [],
            }

        validaciones = []

        for ruc_data in resultado.get("results", []):
            ruc = ruc_data.get("ruc", "")
            razon = ruc_data.get("nombre_o_razon_social", "")

            if not ruc_data.get("success"):
                validaciones.append(
                    {
                        "ruc": ruc,
                        "razon_social": razon,
                        "valido_facturacion": False,
                        "motivo": "Consulta fallida",
                        "detalles": ruc_data.get("error", "Error desconocido"),
                    }
                )
                continue

            # Aplicar criterios de facturación
            criterios = {
                "estado_activo": ruc_data.get("estado_del_contribuyente") == "ACTIVO",
                "habido": ruc_data.get("condicion_de_domicilio") == "HABIDO",
                "direccion_valida": len(ruc_data.get("direccion", "").strip()) > 10,
                "datos_actualizados": "actualizado_en" in ruc_data,
            }

            valido = all(criterios.values())

            validaciones.append(
                {
                    "ruc": ruc,
                    "razon_social": razon,
                    "valido_facturacion": valido,
                    "criterios": criterios,
                    "estado": ruc_data.get("estado_del_contribuyente"),
                    "condicion": ruc_data.get("condicion_de_domicilio"),
                    "direccion": (
                        ruc_data.get("direccion", "")[:50] + "..."
                        if len(ruc_data.get("direccion", "")) > 50
                        else ruc_data.get("direccion", "")
                    ),
                    "motivo": (
                        "Válido"
                        if valido
                        else ", ".join([k for k, v in criterios.items() if not v])
                    ),
                }
            )

        # Resumen
        validos = [v for v in validaciones if v["valido_facturacion"]]

        return {
            "success": True,
            "total_rucs": len(ruc_list),
            "validos_facturacion": len(validos),
            "invalidos_facturacion": len(validaciones) - len(validos),
            "porcentaje_valido": (
                (len(validos) / len(validaciones) * 100) if validaciones else 0
            ),
            "validaciones": validaciones,
            "resumen_criterios": {
                "estado_activo": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("estado_activo", False)
                ),
                "habido": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("habido", False)
                ),
                "direccion_valida": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("direccion_valida", False)
                ),
                "datos_actualizados": sum(
                    1
                    for v in validaciones
                    if v.get("criterios", {}).get("datos_actualizados", False)
                ),
            },
        }

    def consultar_ruc_masivo_completo(self, ruc_list, batch_id=None, tamano_lote=None):
        """
        Consulta masiva de RUCs sin límite de cantidad (usa particionado automático).

        Args:
            ruc_list: Lista de RUCs a consultar (cualquier cantidad)
            batch_id: ID de ApiBatchRequest para tracking
            tamano_lote: Tamaño de cada lote (máximo 100 por APIMIGO, por defecto 100)

        Returns:
            dict con resultados consolidados de todos los lotes
        """
        if tamano_lote is None:
            if (
                self.service
                and hasattr(self.service, "max_batch_size")
                and self.service.max_batch_size
            ):
                tamano_lote = self.service.max_batch_size
            else:
                tamano_lote = 100
        logger.info(
            f"Iniciando consulta masiva completa de {len(ruc_list)} RUCs con lotes de {tamano_lote}"
        )

        # Validar entrada
        if not isinstance(ruc_list, list):
            raise ValueError("ruc_list debe ser una lista")

        if len(ruc_list) == 0:
            return {
                "success": True,
                "total_requested": 0,
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
                "summary": {"activos": 0, "habidos": 0},
                "lotes_procesados": 0,
            }

        # Registrar batch request si se proporciona batch_id
        batch_request = None
        if batch_id:
            try:
                batch_request = ApiBatchRequest.objects.get(id=batch_id)
                batch_request.status = "PROCESSING"
                batch_request.total_items = len(ruc_list)
                batch_request.processed_items = 0
                batch_request.successful_items = 0
                batch_request.failed_items = 0
                batch_request.save()
            except ApiBatchRequest.DoesNotExist:
                pass

        try:
            # Particionar RUCs en lotes
            lotes = self._particionar_rucs_en_lotes(ruc_list, tamano_lote)

            # Resultados consolidados
            todos_resultados = []
            total_exitosos = 0
            total_fallidos = 0
            total_procesados = 0

            # Procesar cada lote
            for i, lote in enumerate(lotes):
                logger.info(f"Procesando lote {i+1}/{len(lotes)} con {len(lote)} RUCs")

                try:
                    # Consultar el lote actual
                    resultado_lote = self.consultar_ruc_masivo(lote)

                    # Si el lote fue exitoso, procesar resultados
                    if resultado_lote.get("success"):
                        resultados_lote = resultado_lote.get("results", [])
                        todos_resultados.extend(resultados_lote)

                        # Contar exitosos y fallidos
                        for item in resultados_lote:
                            if isinstance(item, dict) and item.get("success", False):
                                total_exitosos += 1
                            else:
                                total_fallidos += 1

                        total_procesados += len(resultados_lote)

                        # Actualizar batch request si existe
                        if batch_request:
                            batch_request.processed_items = total_procesados
                            batch_request.successful_items = total_exitosos
                            batch_request.failed_items = total_fallidos
                            batch_request.save()

                    else:
                        # Si falló todo el lote
                        total_fallidos += len(lote)
                        total_procesados += len(lote)

                        # Crear registros fallidos para cada RUC del lote
                        for ruc in lote:
                            todos_resultados.append(
                                {
                                    "success": False,
                                    "ruc": ruc,
                                    "error": resultado_lote.get(
                                        "error", "Error en consulta masiva"
                                    ),
                                }
                            )

                        if batch_request:
                            batch_request.failed_items += len(lote)
                            batch_request.processed_items += len(lote)
                            batch_request.save()

                    # Respetar rate limiting entre lotes (mínimo 2 segundos)
                    if i < len(lotes) - 1:  # No esperar después del último lote
                        time.sleep(2)

                except Exception as e:
                    logger.error(f"Error procesando lote {i+1}: {str(e)}")
                    total_fallidos += len(lote)
                    total_procesados += len(lote)

                    # Crear registros fallidos para cada RUC del lote
                    for ruc in lote:
                        todos_resultados.append(
                            {
                                "success": False,
                                "ruc": ruc,
                                "error": f"Error en lote: {str(e)}",
                            }
                        )

                    if batch_request:
                        batch_request.failed_items += len(lote)
                        batch_request.processed_items += len(lote)
                        batch_request.save()

                    # Continuar con el siguiente lote
                    continue

            # Calcular estadísticas finales
            activos = len(
                [
                    r
                    for r in todos_resultados
                    if isinstance(r, dict)
                    and r.get("success")
                    and r.get("estado_del_contribuyente") == "ACTIVO"
                ]
            )

            habidos = len(
                [
                    r
                    for r in todos_resultados
                    if isinstance(r, dict)
                    and r.get("success")
                    and r.get("condicion_de_domicilio") == "HABIDO"
                ]
            )

            # Actualizar batch request final si existe
            if batch_request:
                batch_request.results = {
                    "successful": [r for r in todos_resultados if r.get("success")],
                    "failed": [r for r in todos_resultados if not r.get("success")],
                    "total": len(todos_resultados),
                }
                batch_request.processed_items = total_procesados
                batch_request.successful_items = total_exitosos
                batch_request.failed_items = total_fallidos
                batch_request.status = "COMPLETED" if total_fallidos == 0 else "PARTIAL"
                batch_request.completed_at = timezone.now()
                batch_request.save()

            # Retornar resultados consolidados
            return {
                "success": True,
                "total_requested": len(ruc_list),
                "total_processed": total_procesados,
                "successful": total_exitosos,
                "failed": total_fallidos,
                "results": todos_resultados,
                "summary": {
                    "activos": activos,
                    "habidos": habidos,
                },
                "lotes_procesados": len(lotes),
                "batch_id": batch_request.id if batch_request else None,
            }

        except Exception as e:
            # Manejar errores globales
            if batch_request:
                batch_request.status = "FAILED"
                batch_request.error_summary = {"error": str(e)}
                batch_request.completed_at = timezone.now()
                batch_request.save()

            error_msg = f"Error en consulta masiva completa: {str(e)}"
            error_msg += f"\nRUCs totales: {len(ruc_list)}"
            error_msg += (
                f"\nPrimeros RUCs: {ruc_list[:5] if len(ruc_list) > 5 else ruc_list}"
            )
            raise Exception(error_msg)

    def consultar_ruc_masivo(self, ruc_list, batch_id=None):
        """
        Consulta masiva de RUCs (máximo 100 por llamada)
        Args:
            ruc_list: Lista de RUCs a consultar
            batch_id: ID de ApiBatchRequest para tracking
        Returns:
            dict con resultados y estadísticas
        """
        # Validar y normalizar entrada
        if not isinstance(ruc_list, list):
            raise ValueError("ruc_list debe ser una lista")

        if len(ruc_list) > 100:
            raise ValueError("Máximo 100 RUCs por consulta masiva")

        # Normalizar RUCs a strings y limpiar
        cleaned_ruc_list = []
        for ruc in ruc_list:
            if isinstance(ruc, (int, float)):
                ruc = str(int(ruc))  # Convertir números a string sin decimales
            elif isinstance(ruc, str):
                ruc = ruc.strip()  # Limpiar espacios
            else:
                raise ValueError(f"Tipo de dato no válido para RUC: {type(ruc)}")

            # Validar formato básico de RUC (11 dígitos para Perú)
            if len(ruc) != 11 or not ruc.isdigit():
                raise ValueError(f"RUC inválido: {ruc}. Debe tener 11 dígitos")

            cleaned_ruc_list.append(ruc)

        # Registrar batch request si se proporciona batch_id
        batch_request = None
        if batch_id:
            try:
                batch_request = ApiBatchRequest.objects.get(id=batch_id)
                batch_request.status = "PROCESSING"
                batch_request.total_items = len(cleaned_ruc_list)
                batch_request.processed_items = 0
                batch_request.successful_items = 0
                batch_request.failed_items = 0
                batch_request.save()
            except ApiBatchRequest.DoesNotExist:
                pass

        try:
            # Usar el método _make_request existente para consistencia
            result = self._make_request(
                endpoint_name="consulta_ruc_masivo", payload={"ruc": cleaned_ruc_list}
            )

            # PROCESAR LA LISTA DIRECTAMENTE
            if not isinstance(result, list):
                # Si no es una lista, hubo un error
                return {
                    "success": False,
                    "error": f"Formato de respuesta inesperado: {type(result)}",
                    "total_requested": len(cleaned_ruc_list),
                    "total_processed": 0,
                    "successful": 0,
                    "failed": len(cleaned_ruc_list),
                    "results": [],
                    "summary": {"activos": 0, "habidos": 0},
                    "batch_id": batch_request.id if batch_request else None,
                }

            # La API devolvió una lista de diccionarios
            results_list = result

            # Clasificar resultados
            successful_results = []
            failed_results = []

            for item in results_list:
                if isinstance(item, dict):
                    # Para consultas masivas, el éxito está en la clave 'success'
                    if item.get("success", False):
                        successful_results.append(item)
                    else:
                        failed_results.append(item)
                else:
                    failed_results.append({"raw": item, "success": False})

            # Calcular estadísticas
            activos = len(
                [
                    r
                    for r in successful_results
                    if r.get("estado_del_contribuyente") == "ACTIVO"
                ]
            )
            habidos = len(
                [
                    r
                    for r in successful_results
                    if r.get("condicion_de_domicilio") == "HABIDO"
                ]
            )

            # ✅ NUEVO: Análisis de facturación
            analisis_facturacion = self._analizar_facturacion(results_list)

            # Actualizar batch request si existe
            if batch_request:
                batch_request.results = {
                    "successful": successful_results,
                    "failed": failed_results,
                    "total": len(results_list),
                    "analisis_facturacion": analisis_facturacion,  # ✅ Agregar análisis
                }
                batch_request.processed_items = len(results_list)
                batch_request.successful_items = len(successful_results)
                batch_request.failed_items = len(failed_results)
                batch_request.status = (
                    "COMPLETED" if len(failed_results) == 0 else "PARTIAL"
                )
                batch_request.completed_at = timezone.now()
                batch_request.save()

            # Retornar estadísticas
            return {
                "success": True,
                "total_requested": len(cleaned_ruc_list),
                "total_processed": len(results_list),
                "successful": len(successful_results),
                "failed": len(failed_results),
                "results": results_list,
                "summary": {
                    "activos": activos,
                    "habidos": habidos,
                },
                "analisis_facturacion": analisis_facturacion,
                "batch_id": batch_request.id if batch_request else None,
            }

        except RateLimitExceededError as e:
            # Manejar rate limit específicamente
            if batch_request:
                batch_request.status = "FAILED"
                batch_request.error_summary = {
                    "error": "Rate limit excedido",
                    "wait_time": e.wait_time,
                }
                batch_request.completed_at = timezone.now()
                batch_request.save()
            raise

        except Exception as e:
            # Manejar otros errores
            if batch_request:
                batch_request.status = "FAILED"
                batch_request.error_summary = {"error": str(e)}
                batch_request.completed_at = timezone.now()
                batch_request.save()

            # Re-lanzar con contexto útil
            error_msg = f"Error en consulta masiva de RUCs: {str(e)}"
            error_msg += f"\nRUCs procesados: {len(cleaned_ruc_list)}"
            error_msg += f"\nPrimeros RUCs: {cleaned_ruc_list[:3]}"
            raise Exception(error_msg)

    def preparar_datos_facturacion_mensual(self, ruc_list):
        """
        Prepara datos de clientes para facturación mensual

        Args:
            ruc_list: Lista de RUCs a validar

        Returns:
            dict con clientes válidos y problemas encontrados
        """
        resultados = {"validos": [], "invalidos": [], "advertencias": []}

        # Dividir en lotes de 100 (máximo permitido)
        lotes = [ruc_list[i : i + 100] for i in range(0, len(ruc_list), 100)]

        for lote in lotes:
            try:
                batch_result = self.consultar_ruc_masivo(lote)

                if batch_result.get("success"):
                    for item in batch_result.get("results", []):
                        ruc = item.get("ruc")

                        # Verificar si fue exitoso (basado en campo 'success')
                        if isinstance(item, dict) and item.get("success", False):
                            estado = item.get("estado_del_contribuyente", "").upper()
                            condicion = item.get("condicion_de_domicilio", "").upper()

                            cliente_data = {
                                "ruc": ruc,
                                "razon_social": item.get("nombre_o_razon_social"),
                                "direccion": item.get("direccion"),
                                "estado": estado,
                                "condicion": condicion,
                                "habido": condicion == "HABIDO",
                                "activo": estado == "ACTIVO",
                                "data_completa": item,
                                "valido_para_facturar": estado == "ACTIVO"
                                and condicion == "HABIDO",
                            }

                            if cliente_data["valido_para_facturar"]:
                                resultados["validos"].append(cliente_data)
                            else:
                                resultados["invalidos"].append(
                                    {
                                        "ruc": ruc,
                                        "razon_social": cliente_data["razon_social"],
                                        "estado": estado,
                                        "condicion": condicion,
                                        "error": "No activo o no habido",
                                    }
                                )
                        else:
                            resultados["advertencias"].append(
                                {
                                    "ruc": ruc,
                                    "error": "Consulta fallida (success=False)",
                                }
                            )
                else:
                    # Si falló el lote completo
                    for ruc in lote:
                        resultados["advertencias"].append(
                            {
                                "ruc": ruc,
                                "error": batch_result.get(
                                    "error", "Error en consulta masiva"
                                ),
                            }
                        )

                # Respetar rate limiting
                time.sleep(2)  # Más tiempo para respetar límites

            except Exception as e:
                resultados["advertencias"].extend(
                    [{"ruc": ruc, "error": f"Error en lote: {str(e)}"} for ruc in lote]
                )

        return resultados

    def _process_response(self, response, api_log, endpoint_name, duration_ms):
        """Procesa la respuesta HTTP y actualiza el log"""
        api_log.duration_ms = duration_ms
        api_log.response_code = response.status_code

        if response.status_code == 200:
            try:
                response_data = response.json()
                api_log.response_data = response_data

                # CASO ESPECIAL: Para consulta_ruc_masivo, la respuesta es una lista
                if endpoint_name == "consulta_ruc_masivo":
                    if isinstance(response_data, list):
                        # Para consultas masivas, considerar éxito si obtenemos una lista
                        # incluso si está vacía
                        api_log.status = "SUCCESS"
                        api_log.save()

                        # Actualizar rate limit
                        rate_limit_obj = ApiRateLimit.objects.get(service=self.service)
                        rate_limit_obj.increment_count()

                        # Devolver la lista directamente
                        return response_data
                    else:
                        # Si no es una lista, marcar como error
                        error_msg = (
                            "Formato de respuesta inesperado para consulta masiva"
                        )
                        api_log.status = "FAILED"
                        api_log.error_message = error_msg
                        api_log.save()
                        raise APIBadResponseError(error_msg)

                # CASO NORMAL: Para otros endpoints
                if response_data.get("success"):
                    # ÉXITO
                    api_log.status = "SUCCESS"
                    api_log.save()

                    # Actualizar rate limit
                    rate_limit_obj = ApiRateLimit.objects.get(service=self.service)
                    rate_limit_obj.increment_count()

                    return response_data
                else:
                    # Error de negocio (ej: RUC no existe)
                    error_msg = response_data.get("message", "Error desconocido en API")
                    api_log.status = "FAILED"
                    api_log.error_message = error_msg
                    api_log.save()

                    if (
                        "no existe" in error_msg.lower()
                        or "not found" in error_msg.lower()
                    ):
                        raise APINotFoundError(f"Recurso no encontrado: {error_msg}")
                    else:
                        raise APIError(f"Error de API: {error_msg}")

            except ValueError:  # JSON decode error
                api_log.status = "FAILED"
                if (
                    "token_invalido" in response.text.lower()
                    or "unauthorized" in response.text.lower()
                ):
                    api_log.error_message = "Token inválido o no autorizado"
                    api_log.save()
                    raise AuthenticationError("Token APIMIGO inválido o no autorizado")
                else:
                    api_log.error_message = f"Respuesta no JSON: {response.text[:200]}"
                    api_log.save()
                    raise APIBadResponseError("Respuesta inesperada de APIMIGO")

        elif response.status_code == 404:
            api_log.status = "FAILED"
            if endpoint_name in ["ruc", "dni"]:
                api_log.error_message = (
                    f"{'RUC' if endpoint_name == 'ruc' else 'DNI'} no encontrado"
                )
                api_log.save()
                raise APINotFoundError(api_log.error_message)
            else:
                api_log.error_message = "Endpoint no encontrado"
                api_log.save()
                raise APINotFoundError("Endpoint no encontrado")

        elif response.status_code in [401, 403]:
            api_log.status = "FAILED"
            api_log.error_message = "Authentication failed"
            api_log.save()
            raise AuthenticationError(f"Authentication failed: {response.status_code}")

        else:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            api_log.status = "FAILED"
            api_log.error_message = error_msg
            api_log.save()
            raise APIError(error_msg)

    def _handle_exception(self, api_log, error_message, exception):
        """Maneja excepciones y actualiza el log"""
        api_log.status = "FAILED"
        api_log.error_message = error_message
        api_log.save()
        raise exception
