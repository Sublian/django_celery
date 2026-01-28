"""
Módulo: api_service.models
==========================
Modelos para gestión de APIs externas.

Este módulo define la estructura de datos para:
1. Configurar servicios API (APIMIGO, NubeFact, SUNAT, etc.)
2. Registrar todas las llamadas API para auditoría
3. Controlar rate limiting y límites de uso
4. Gestionar solicitudes masivas (batches)

Principales entidades:
- ApiService: Configuración de un servicio API externo
- ApiEndpoint: Endpoints específicos de cada servicio
- ApiCallLog: Auditoría de cada llamada API
- ApiBatchRequest: Solicitudes masivas de procesamiento
- ApiRateLimit: Control de rate limiting en tiempo real
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class ApiService(models.Model):
    """
    Configuración de un servicio API externo.

    Ejemplos: APIMIGO, NubeFact, SUNAT, etc.
    Cada servicio tiene su propia URL base, token de autenticación
    y límites de rate limiting.

    Campos:
    - name: Nombre identificador del servicio (ej: 'APIMIGO Perú')
    - service_type: Tipo general del servicio (personalizable)
    - base_url: URL base del servicio
    - auth_token: Token/API Key para autenticación
    - auth_type: Tipo de autenticación (token, bearer, api_key, basic)
    - is_active: Si el servicio está habilitado para uso
    - requests_per_minute: Límite de peticiones por minuto
    - max_batch_size: Tamaño máximo para solicitudes masivas
    """

    # Tipos de autenticación soportados
    AUTH_TOKEN = "token"
    AUTH_BEARER = "bearer"
    AUTH_API_KEY = "api_key"
    AUTH_BASIC = "basic"

    AUTH_TYPE_CHOICES = [
        (AUTH_TOKEN, "Token Simple"),
        (AUTH_BEARER, "Bearer Token (JWT)"),
        (AUTH_API_KEY, "API Key"),
        (AUTH_BASIC, "Basic Auth"),
    ]

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nombre identificador del servicio API (ej: 'APIMIGO Perú')",
    )

    service_type = models.CharField(
        max_length=50,
        help_text="Tipo de servicio (ej: 'MIGO', 'NUBEFACT', 'SUNAT', 'OTRO')",
    )

    base_url = models.URLField(
        help_text="URL base del servicio API (ej: https://api.migo.pe)"
    )

    auth_token = models.CharField(
        max_length=512,
        blank=True,
        help_text="Token, API Key o credenciales para autenticación",
    )

    auth_type = models.CharField(
        max_length=20,
        choices=AUTH_TYPE_CHOICES,
        default=AUTH_TOKEN,
        help_text="Tipo de autenticación requerida por el servicio",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Indica si el servicio está activo y disponible para uso",
    )

    requests_per_minute = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Límite máximo de peticiones por minuto (rate limiting)",
    )

    max_batch_size = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Tamaño máximo para solicitudes masivas (batch)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Servicio API"
        verbose_name_plural = "Servicios API"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["service_type", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.service_type})"

    @property
    def is_migo_service(self):
        """Verifica si es un servicio APIMIGO"""
        return self.service_type.upper() == "MIGO"

    def get_auth_header(self):
        """Devuelve el header de autenticación según el tipo"""
        if self.auth_type == self.AUTH_BEARER:
            return {"Authorization": f"Bearer {self.auth_token}"}
        elif self.auth_type == self.AUTH_TOKEN:
            return {"X-API-Token": self.auth_token}
        elif self.auth_type == self.AUTH_API_KEY:
            return {"X-API-Key": self.auth_token}
        elif self.auth_type == self.AUTH_BASIC:
            return {"Authorization": f"Basic {self.auth_token}"}
        return {}


class ApiEndpoint(models.Model):
    """
    Endpoint específico de un servicio API.

    Cada servicio puede tener múltiples endpoints (ej: /api/v1/ruc, /api/v1/dni).
    Esto permite un manejo granular de rate limiting y configuración.
    """

    HTTP_METHODS = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("DELETE", "DELETE"),
        ("PATCH", "PATCH"),
    ]

    service = models.ForeignKey(
        ApiService,
        on_delete=models.CASCADE,
        related_name="endpoints",
        help_text="Servicio API al que pertenece este endpoint",
    )

    name = models.CharField(
        max_length=100, help_text="Nombre descriptivo del endpoint (ej: 'Consulta RUC')"
    )

    path = models.CharField(
        max_length=200, help_text="Ruta del endpoint (ej: '/api/v1/ruc')"
    )

    method = models.CharField(
        max_length=10,
        choices=HTTP_METHODS,
        default="POST",
        help_text="Método HTTP utilizado",
    )

    description = models.TextField(
        blank=True, help_text="Descripción detallada del endpoint y su uso"
    )

    is_active = models.BooleanField(
        default=True, help_text="Indica si el endpoint está activo"
    )

    custom_rate_limit = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Límite personalizado para este endpoint (sobrescribe el del servicio)",
    )
    
    timeout = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        help_text="Tiempo de espera máximo en segundos para las peticiones a este endpoint",
    )

    class Meta:
        verbose_name = "Endpoint API"
        verbose_name_plural = "Endpoints API"
        unique_together = ["service", "path", "method"]
        ordering = ["service", "path"]

    def __str__(self):
        return f"{self.service.name}: {self.name}"

    @property
    def rate_limit(self):
        """Devuelve el límite de tasa efectivo para este endpoint"""
        return self.custom_rate_limit or self.service.requests_per_minute

    def get_full_url(self):
        """Devuelve la URL completa del endpoint"""
        return f"{self.service.base_url.rstrip('/')}{self.path}"


class ApiCallLog(models.Model):
    """
    Registro detallado de cada llamada a API externa.

    Propósito:
    1. Auditoría completa de todas las interacciones
    2. Monitoreo de errores y rendimiento
    3. Base para reintentos y manejo de fallos
    4. Análisis de uso y costos

    Este modelo es la piedra angular de la trazabilidad del módulo.
    """

    STATUS_CHOICES = [
        ("PENDING", "🟡 Pendiente"),
        ("SUCCESS", "🟢 Éxito"),
        ("FAILED", "🔴 Fallido"),
        ("RATE_LIMITED", "⏸️ Limitado por tasa"),
        ("RETRYING", "🔄 Reintentando"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único de la llamada",
    )

    service = models.ForeignKey(
        ApiService,
        on_delete=models.PROTECT,
        related_name="call_logs",
        help_text="Servicio API llamado",
    )

    endpoint = models.ForeignKey(
        ApiEndpoint,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="call_logs",
        help_text="Endpoint específico utilizado",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text="Estado actual de la llamada",
    )

    request_data = models.JSONField(
        default=dict, help_text="Datos enviados en la petición (formato JSON)"
    )

    response_data = models.JSONField(
        null=True, blank=True, help_text="Respuesta completa de la API (formato JSON)"
    )

    response_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="Código HTTP de la respuesta (200, 404, 500, etc.)",
    )

    error_message = models.TextField(
        blank=True, help_text="Mensaje de error en caso de fallo"
    )

    duration_ms = models.IntegerField(
        null=True, blank=True, help_text="Duración de la llamada en milisegundos"
    )

    called_from = models.CharField(
        max_length=500,
        blank=True,
        help_text="Módulo/función que realizó la llamada (para trazabilidad)",
    )

    batch_request = models.ForeignKey(
        "ApiBatchRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_logs",
        help_text="Solicitud masiva a la que pertenece esta llamada",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registro de Llamada API"
        verbose_name_plural = "Registros de Llamadas API"
        indexes = [
            models.Index(fields=["service", "status", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["status", "response_code"]),
            models.Index(fields=["called_from"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        # Obtener datetime localizado
        if timezone.is_aware(self.created_at):
            local_time = timezone.localtime(self.created_at)
        else:
            local_time = self.created_at
        time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")

        return f"{self.service.name} - {self.status} - {time_str}"

    @property
    def was_successful(self):
        """Indica si la llamada fue exitosa"""
        return self.status == "SUCCESS"

    @property
    def is_recent(self):
        """Indica si la llamada es reciente (últimos 5 minutos)"""
        return (timezone.now() - self.created_at).seconds < 300

    def mark_as_success(self, response_data, response_code=200, duration_ms=None):
        """Marca la llamada como exitosa"""
        self.status = "SUCCESS"
        self.response_data = response_data
        self.response_code = response_code
        if duration_ms:
            self.duration_ms = duration_ms
        self.save()

    def mark_as_failed(self, error_message, response_code=None, duration_ms=None):
        """Marca la llamada como fallida"""
        self.status = "FAILED"
        self.error_message = error_message[:2000]  # Limitar longitud
        if response_code:
            self.response_code = response_code
        if duration_ms:
            self.duration_ms = duration_ms
        self.save()


class ApiBatchRequest(models.Model):
    """
    Solicitud masiva de procesamiento API.

    Ejemplo: Validación de 3000 RUCs para facturación mensual.
    Divide la carga en lotes manejables y gestiona el estado general.
    """

    STATUS_CHOICES = [
        ("PENDING", "⏳ Pendiente"),
        ("PROCESSING", "🔄 Procesando"),
        ("PARTIAL", "⚠️ Parcialmente Completado"),
        ("COMPLETED", "✅ Completado"),
        ("FAILED", "❌ Fallido"),
        ("CANCELLED", "🚫 Cancelado"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "🔵 Baja"),
        ("NORMAL", "🟢 Normal"),
        ("HIGH", "🟡 Alta"),
        ("CRITICAL", "🔴 Crítica"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único de la solicitud masiva",
    )

    service = models.ForeignKey(
        ApiService,
        on_delete=models.PROTECT,
        related_name="batch_requests",
        help_text="Servicio API utilizado para esta solicitud masiva",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        help_text="Estado actual del procesamiento masivo",
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="NORMAL",
        help_text="Prioridad de procesamiento",
    )

    input_data = models.JSONField(
        help_text="Datos de entrada para el procesamiento masivo"
    )

    results = models.JSONField(
        null=True, blank=True, help_text="Resultados consolidados del procesamiento"
    )

    total_items = models.IntegerField(
        default=0, help_text="Número total de items a procesar"
    )

    processed_items = models.IntegerField(
        default=0, help_text="Items procesados hasta el momento"
    )

    successful_items = models.IntegerField(
        default=0, help_text="Items procesados exitosamente"
    )

    failed_items = models.IntegerField(
        default=0, help_text="Items que fallaron en el procesamiento"
    )

    error_summary = models.JSONField(
        null=True, blank=True, help_text="Resumen de errores agrupados por tipo"
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_batch_requests",
        help_text="Usuario que solicitó el procesamiento",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Solicitud Masiva API"
        verbose_name_plural = "Solicitudes Masivas API"
        indexes = [
            models.Index(fields=["service", "status", "priority"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["requested_by", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch {self.id} - {self.service.name} - {self.status}"

    @property
    def progress_percentage(self):
        """Porcentaje de completado del batch"""
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)

    @property
    def success_rate(self):
        """Tasa de éxito del batch"""
        if self.processed_items == 0:
            return 0
        return int((self.successful_items / self.processed_items) * 100)

    @property
    def duration_seconds(self):
        """Duración total en segundos (si está completado)"""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def start_processing(self):
        """Marca el inicio del procesamiento"""
        self.status = "PROCESSING"
        self.started_at = timezone.now()
        self.save()

    def complete_processing(self, results, success_count, fail_count):
        """Marca el fin del procesamiento"""
        self.status = "COMPLETED" if fail_count == 0 else "PARTIAL"
        self.results = results
        self.successful_items = success_count
        self.failed_items = fail_count
        self.processed_items = success_count + fail_count
        self.completed_at = timezone.now()
        self.save()

    def cancel_processing(self):
        """Cancela el procesamiento"""
        self.status = "CANCELLED"
        self.completed_at = timezone.now()
        self.save()


class ApiRateLimit(models.Model):
    """
    Control de rate limiting en tiempo real.

    Monitorea y controla las peticiones por minuto para cada servicio.
    Se actualiza en tiempo real durante las llamadas.
    """

    service = models.OneToOneField(
        ApiService,
        on_delete=models.CASCADE,
        related_name="rate_limit_status",
        help_text="Servicio API monitoreado",
    )
    endpoint = models.ForeignKey(
        ApiEndpoint,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="rate_limits",
        help_text="Endpoint específico (null para límite general del servicio)",
    )

    current_count = models.IntegerField(
        default=0, help_text="Número de peticiones en la ventana actual"
    )

    last_request_at = models.DateTimeField(
        auto_now=True, help_text="Última vez que se hizo una petición"
    )

    minute_window_start = models.DateTimeField(
        auto_now=True, help_text="Inicio de la ventana de 1 minuto para rate limiting"
    )

    total_requests = models.IntegerField(
        default=0, help_text="Total de peticiones realizadas (histórico)"
    )

    class Meta:
        verbose_name = "Control de Rate Limit"
        verbose_name_plural = "Controles de Rate Limit"
        unique_together = ["service", "endpoint"]  # Una entrada por servicio-endpoint
        indexes = [
            models.Index(fields=["service", "endpoint"]),
            models.Index(fields=["minute_window_start"]),
        ]

    def __str__(self):
        if self.endpoint:
            return f"Rate Limit: {self.service.name} - {self.endpoint.name} ({self.current_count}/{self.get_limit()})"
        return (
            f"Rate Limit: {self.service.name} ({self.current_count}/{self.get_limit()})"
        )

    def get_limit(self):
        """Obtiene el límite aplicable"""
        if self.endpoint and self.endpoint.custom_rate_limit:
            return self.endpoint.custom_rate_limit
        return self.service.requests_per_minute

    def can_make_request(self):
        """
        Verifica si se puede hacer una nueva petición respetando el rate limit.

        Returns:
            bool: True si se puede hacer la petición, False si se excedió el límite
        """
        now = timezone.now()

        # Reiniciar contador si ha pasado más de 1 minuto desde el inicio de la ventana
        if (now - self.minute_window_start).seconds >= 60:
            self.current_count = 0
            self.minute_window_start = now
            self.save()

        return self.current_count < self.service.requests_per_minute

    def increment_count(self):
        """
        Incrementa el contador de peticiones.

        Este método debe llamarse después de cada petición exitosa.
        """
        self.current_count += 1
        self.total_requests += 1
        self.last_request_at = timezone.now()
        self.save()

    def get_wait_time(self):
        """
        Calcula el tiempo de espera necesario si se excedió el límite.

        Returns:
            int: Segundos a esperar antes de la próxima petición
        """
        now = timezone.now()
        seconds_passed = (now - self.minute_window_start).seconds

        if seconds_passed < 60:
            return 60 - seconds_passed
        return 0

    def reset_counter(self):
        """Reinicia el contador manualmente"""
        self.current_count = 0
        self.minute_window_start = timezone.now()
        self.save()

    @classmethod
    def get_for_service_endpoint(cls, service, endpoint=None):
        """
        Obtiene o crea un ApiRateLimit para un servicio (y opcionalmente endpoint).
        """
        obj, created = cls.objects.get_or_create(
            service=service,
            endpoint=endpoint,
            defaults={"current_count": 0, "total_requests": 0},
        )
        return obj, created
