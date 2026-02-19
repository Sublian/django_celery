from .settings import *

# ---------- DATABASE ----------
# Usar SQLite para pruebas
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# ---------- CELERY ----------
# Ejecutar tareas sin worker
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Opcional: desactivar retries automáticos en test
CELERY_TASK_IGNORE_RESULT = True

# ---------- PASSWORD HASHERS ----------
# Acelera creación de usuarios en test
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------- EMAIL ----------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
