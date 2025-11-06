# core/utils/celery_status.py
import socket
import redis
import logging
import celery
from celery import current_app
from celery.result import AsyncResult
from django.conf import settings

logger = logging.getLogger(__name__)


def is_redis_available():
    """Verifica la conexión con Redis mediante un ping TCP directo."""
    try:
        broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
        host = broker_url.split("//")[-1].split(":")[0]
        port = int(broker_url.split(":")[-1].split("/")[0])

        logger.debug(f"🔍 Verificando conexión Redis en {host}:{port}")
        with socket.create_connection((host, port), timeout=2):
            r = redis.Redis.from_url(broker_url)
            r.ping()
        logger.debug("✅ Redis disponible")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Redis no disponible: {e}")
        return False

def is_celery_available():
    try:
        app = current_app
        i = app.control.inspect(timeout=3.0)
        stats = i.stats()
        if stats:
            return True

        # fallback solo si no se está ejecutando dentro de una tarea
        if not celery.current_task:
            result = app.send_task("celery.ping")
            AsyncResult(result.id).get(timeout=2)
            return True

        return False
    except Exception as e:
        logger.warning(f"⚠️ No se pudo verificar Celery: {e}")
        return False