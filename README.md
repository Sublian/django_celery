# 🧠 Django Celery Background Tasks

Proyecto base en **Django + Celery + Redis**, que demuestra cómo ejecutar tareas en segundo plano (procesamiento de archivos CSV y Excel) con un **panel de control (dashboard)** y un **sistema de carga (upload)** integrados.

---

## 🚀 Tecnologías utilizadas

- **Python 3.11+**
- **Django 5+**
- **Celery 5+**
- **Redis** (broker para tareas)
- **PostgreSQL** (base de datos principal)
- **Pandas + OpenPyXL** (lectura de archivos)
- **Bootstrap 5 + SweetAlert2** (interfaz)
- **Docker (opcional)** para servicios auxiliares

---

## ⚙️ Estructura del proyecto

```bash
myproject/
│
├── core/
│   ├── models.py          # Modelos FileProcess y TaskRecord
│   ├── tasks.py           # Tareas Celery (procesamiento de CSV/XLSX)
│   ├── views.py           # Vistas upload y dashboard
│   ├── templates/core/
│   │   ├── base.html      # Plantilla base
│   │   ├── upload.html    # Carga de archivos + feedback en tiempo real
│   │   └── dashboard.html # Monitoreo de tareas y archivos procesados
│   ├── urls.py
│   └── forms.py
│
├── myproject/
│   ├── settings.py        # Configuración Django + Celery
│   ├── celery.py          # Inicialización Celery
│   └── urls.py
│
├── manage.py
├── .env                   # Configuración sensible (DB, Redis, etc.)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🧩 Modelos principales

### `FileProcess`
Representa un archivo cargado por el usuario.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | CharField | Nombre asignado al archivo |
| `file` | FileField | Ruta del archivo subido |
| `status` | CharField | Pendiente / Procesando / Completado / Error |
| `processed` | Boolean | Indica si fue procesado |
| `message` | Text | Resultado o error del proceso |
| `created_at` | DateTime | Fecha de carga |

### `TaskRecord`
Registro histórico de tareas Celery.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `task_id` | UUID | ID interno de Celery |
| `task_name` | CharField | Nombre de la tarea ejecutada |
| `fileprocess` | FK | Archivo asociado |
| `status` | CharField | Estado Celery (STARTED, SUCCESS, FAILURE, etc.) |
| `result` | Text | Resultado o error capturado |
| `created_at` | DateTime | Inicio de tarea |
| `finished_at` | DateTime | Fin de tarea |

---

## 🔧 Configuración de entorno

### 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/<tu_usuario>/django_celery.git
cd django_celery
```

### 2️⃣ Crear entorno virtual
```bash
uv venv --python 3.11
source .venv/bin/activate    # Linux/Mac
.venv\Scripts\activate       # Windows
```

### 3️⃣ Instalar dependencias
```bash
uv pip install -r requirements.txt
```

### 4️⃣ Configurar variables de entorno
Crear un archivo `.env` con:
```env
DEBUG=True
SECRET_KEY=tu_clave
DATABASE_URL=postgres://usuario:password@localhost:5432/django_celery
CELERY_BROKER_URL=redis://localhost:6379/0
```

### 5️⃣ Ejecutar migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6️⃣ Crear superusuario
```bash
python manage.py createsuperuser
```

---

## 🧵 Ejecución del proyecto

### Iniciar Redis con Docker (Recomendado)
```bash
docker run -d -p 6379:6379 redis
```

### Iniciar Redis (si no usas Docker)
```bash
redis-server
```

### Iniciar servidor Django
```bash
python manage.py runserver
```

### Iniciar worker Celery
```bash
celery -A myproject worker -l info
# en caso de fallo
python -m celery -A myproject worker -l info
```

### Iniciar scheduler Celery Beat
```bash
celery -A myproject beat -l info
# en caso de fallo
python -m celery -A myproject beat -l info
```

---

## 💼 Flujo general

1. El usuario carga un archivo desde `/upload/`.
2. Django lo guarda y **encola una tarea Celery**.
3. El worker procesa el archivo (CSV o Excel).
4. Se actualiza el registro en `FileProcess` y `TaskRecord`.
5. El usuario visualiza el progreso desde `/dashboard/`.

---

## 💡 Funcionalidades destacadas

✅ Subida asíncrona de archivos  
✅ Procesamiento en segundo plano con feedback visual  
✅ Dashboard con paginación, búsqueda y color por estado  
✅ Tareas recurrentes con Celery Beat  
✅ SweetAlert2 para notificaciones limpias  
✅ Soporte CSV + Excel (`pandas`, `openpyxl`, `xlrd`)  
✅ Integración con PostgreSQL y Redis  

---

## 🧱 Pendientes / Próximos pasos

- [ ] API REST para consultas de tareas  
- [ ] Actualización en tiempo real con Django Channels  
- [ ] Logging centralizado de errores  
- [ ] Exportación de reportes  

---

## 👤 Autor

**Luis A. González**  
💼 Backend Developer | Python + Django + Celery  
📧 contacto: subliandev@gmail.com  
🔗 GitHub: [@Sublian](https://github.com/Sublian)

---

## 📜 Licencia

Este proyecto se distribuye bajo la licencia **MIT**, lo que permite su uso, copia y modificación libremente con la debida atribución.
