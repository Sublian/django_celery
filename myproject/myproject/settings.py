import os
from decouple import config
from pathlib import Path
from datetime import datetime

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-e)r_e$i#0rp$&qhttpkf1+v!&^vgzv&^d%g1t0tzz5s@93e$9_"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition
AUTH_USER_MODEL = "users.User"

INSTALLED_APPS = [
    "users",
    "core",
    "billing",
    "api_service",
    "formtools",
    "django_extensions",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "easy_pdf",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "myproject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",              # Directorio global de templates
            BASE_DIR / 'billing' / 'templates',  # Templates de billing app
            BASE_DIR / 'shared' / 'utils' / 'pdf' / 'templates',  # Templates base para PDFs
            BASE_DIR / 'shared',  # Directorio shared completo
        ],  # <-- aquí se indica la carpeta 'templates' del proyecto
        "APP_DIRS": True,   # Esto busca en app_name/templates/
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "myproject.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        # 'ENGINE': 'django.db.backends.sqlite3',
        # 'NAME': BASE_DIR / 'db.sqlite3',
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

from datetime import timedelta

CELERY_BEAT_SCHEDULE = {
    "heartbeat-every-10-seconds": {
        "task": "core.tasks.print_heartbeat",
        "schedule": timedelta(seconds=10),
    },
    "send_welcome_email_5s": {
        "task": "core.tasks.send_welcome_email",
        "schedule": timedelta(seconds=5),
    },
    "reprocess_pending": {
        "task": "core.tasks.reprocess_pending_tasks",
        "schedule": timedelta(minutes=5),
    },
}

CELERY_BEAT_SCHEDULE_FILENAME = BASE_DIR / "celery-data" / "celerybeat-schedule"

# Configuración de Celery
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# (Opcional) Zona horaria por defecto
# CELERY_TIMEZONE = 'America/Lima'
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'UTC'
# USE_I18N = True
# USE_TZ = True

# 🌎 Configuración regional
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# 📜 Configuración de logs
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    # 🧩 Formatos de mensaje
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} ({name}) {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname}: {message}",
            "style": "{",
        },
    },
    # 🧱 Handlers: a dónde van los logs
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django_app.log",
            "maxBytes": 5 * 1024 * 1024,  # 5 MB
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    # 🎯 Loggers: qué se registra
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "core": {  # tu aplicación principal
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        # 'LOCATION': '127.0.0.1:11211',  # Puerto default de Memcached
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 3600,  # 1 hora por defecto
        # 'OPTIONS': {
        #     'no_delay': True,
        #     'ignore_exc': True,
        #     'max_pool_size': 4,
        #     'use_pooling': True,
        # }
    }
}


############################### PDF CONFIG
# Configuración de empresa
COMPANY_NAME = os.getenv('COMPANY_NAME', 'MI EMPRESA S.A.C.')
COMPANY_RUC = os.getenv('COMPANY_RUC', '20123456789')  # <-- ESTE FALTA
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', 'Av. Principal 123, Lima')
COMPANY_PHONE = os.getenv('COMPANY_PHONE', '(01) 123-4567')
COMPANY_EMAIL = os.getenv('COMPANY_EMAIL', 'contacto@empresa.com')

# Templates para PDFs
PDF_TEMPLATES = {
    'invoice': 'billing/factura_electronica.html',
    'invoice_custom': 'billing/plantilla_personalizada.html',
    'receipt': 'billing/boleta_electronica.html',  # Crear después
    'quote': 'billing/cotizacion.html',            # Crear después
}

# Opcional: Configuración de rutas base
PDF_BASE_TEMPLATE = 'shared/utils/pdf/templates/base_pdf.html'

# Configuración de almacenamiento de documentos
DOCUMENT_STORAGE = {
    'BASE_DIR': os.path.join(BASE_DIR, 'file_store'),
    'STRUCTURE': {
        'invoices': 'billing/invoices/{year}/{month}/',
        'receipts': 'billing/receipts/{year}/{month}/',
        'quotes': 'billing/quotes/{year}/{month}/',
        'credit_notes': 'billing/credit_notes/{year}/{month}/',
        'temporary': 'temp/{date}/',
    },
    'RETENTION_DAYS': {
        'invoices': 365 * 10,      # 10 años
        'receipts': 365 * 10,      # 10 años
        'quotes': 365,             # 1 año
        'credit_notes': 365 * 10,  # 10 años
        'temporary': 7,            # 7 días
    }
}

# Crear directorios de almacenamiento
import os
from datetime import datetime
for doc_type, path_template in DOCUMENT_STORAGE['STRUCTURE'].items():
    now = datetime.now()
    path = path_template.format(
        year=now.strftime('%Y'),
        month=now.strftime('%m'),
        date=now.strftime('%Y%m%d')
    )
    full_path = os.path.join(DOCUMENT_STORAGE['BASE_DIR'], path)
    os.makedirs(full_path, exist_ok=True)