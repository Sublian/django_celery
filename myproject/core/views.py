from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from .models import FileProcess, TaskRecord, PendingTask
from .tasks import process_csv_file
from .utils.celery_status import is_redis_available, is_celery_available
import os, logging


logger = logging.getLogger(__name__)


class UploadForm(forms.ModelForm):
    class Meta:
        model = FileProcess
        fields = ["name", "file"]


def upload_file(request):
    if request.method == "POST":
        user_ip = request.META.get("REMOTE_ADDR")
        logger.info("Usuario %s subió un archivo desde %s", request.user, user_ip)

        name = request.POST.get("name")
        file = request.FILES.get("file")

        # 🧩 Validaciones básicas
        if not name or not file:
            msg = "Debe completar todos los campos."
            logger.warning(f"⚠️ Solicitud incompleta desde {user_ip}: {msg}")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect("upload_file")

        # Crear registro del archivo
        obj = FileProcess.objects.create(name=name, file=file, status="pending")
        logger.info(f"Archivo '{name}' guardado en base de datos con ID {obj.id}")

        # 📦 Validar extensión
        valid_extensions = [".csv", ".xls", ".xlsx"]
        import os

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in valid_extensions:
            msg = f"Tipo de archivo no permitido: {ext}"
            obj.status = "error"
            obj.message = msg
            obj.save()
            logger.error(f"❌ {msg} - Usuario desde {user_ip}")
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"error": msg}, status=400)
            messages.error(request, msg)
            return redirect("upload_file")

        # 🚦 Verificar disponibilidad de Redis y Celery
        redis_ok = is_redis_available()
        celery_ok = is_celery_available()

        if redis_ok and celery_ok:
            def enqueue_task():
                process_csv_file.apply_async(args=[obj.id])
                logger.info(
                    f"✅ Celery activo, tarea encolada para archivo '{name}' (ID {obj.id})"
                )
            transaction.on_commit(enqueue_task)
        else:
            logger.warning(
                f"⚠️ Celery/Redis inactivos. Guardando tarea pendiente para '{name}'"
            )
            PendingTask.objects.create(
                task_name="core.tasks.process_csv_file", args={"file_id": obj.id}
            )

        # 🧠 Respuesta AJAX o normal
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "status": "queued" if (redis_ok and celery_ok) else "pending",
                    "file_id": obj.id,
                    "celery_ok": celery_ok,
                    "redis_ok": redis_ok,
                }
            )

        messages.success(
            request,
            f"Archivo '{name}' agregado {'a la cola de tareas' if celery_ok else 'como pendiente'}.",
        )
        return redirect("dashboard")

    # GET — render de la página de subida
    return render(request, "core/upload.html")


def dashboard(request):
    # --- 🔍 Filtro de búsqueda ---
    query = request.GET.get("q", "").strip()
    file_qs = FileProcess.objects.all().order_by("-created_at")

    if query:
        file_qs = file_qs.filter(
            Q(name__icontains=query)
            | Q(status__icontains=query)
            | Q(message__icontains=query)
        )
    # --- 📄 Paginación ---
    per_page = request.GET.get("per_page", "10")
    if per_page not in ["10", "20"]:
        per_page = "10"

    paginator = Paginator(file_qs, int(per_page))
    page_number = request.GET.get("page")
    files_page = paginator.get_page(page_number)

    # --- Datos adicionales ---
    tasks = TaskRecord.objects.all().order_by("-created_at")[:10]

    context = {
        "files": files_page,
        "tasks": tasks,
        "query": query,
        "per_page": per_page,
    }
    return render(request, "core/dashboard.html", context)


def view_logs(request):
    """
    Vista para mostrar el contenido del archivo de logs y permitir recarga dinámica.
    """
    log_path = os.path.join(settings.BASE_DIR, "logs", "django_app.log")

    if not os.path.exists(log_path):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"lines": []})
        return HttpResponse(
            "⚠️ No hay registros disponibles.", content_type="text/plain"
        )

    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines.reverse()  # Mostrar los más recientes primero
    paginator = Paginator(lines, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # ⚡ Respuesta dinámica para fetch()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "lines": page_obj.object_list,
                "page": page_obj.number,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        )

    return render(request, "core/logs.html", {"page_obj": page_obj})


def pending_tasks_monitor(request):
    redis_ok = is_redis_available()
    celery_ok = is_celery_available()
    pendientes = PendingTask.objects.all().order_by("-created_at")

    context = {
        "pendientes": pendientes,
        "redis_ok": redis_ok,
        "celery_ok": celery_ok,
    }
    logger.info(f"[Monitor] Se detectaron {pendientes.count()} tareas pendientes.")
    return render(request, "core/pending_tasks.html", context)


# 🔧 1️⃣ Definimos el despachador global de tareas
TASK_DISPATCHER = {
    "core.tasks.process_csv_file": lambda args: process_csv_file.delay(
        args.get("file_id")
    ),
    # Ejemplo de futuras tareas:
    # 'core.tasks.generar_reporte': lambda args: generar_reporte.delay(args.get('reporte_id')),
    # 'core.tasks.enviar_notificacion': lambda args: enviar_notificacion.delay(args.get('user_id')),
}


@require_POST
def reprocesar_pendientes(request):
    """Reintenta encolar manualmente las tareas pendientes."""
    pendientes = PendingTask.objects.all().order_by("-created_at")
    redis_ok = is_redis_available()
    celery_ok = is_celery_available()

    if not pendientes.exists():
        messages.info(request, "No hay tareas pendientes por procesar.")
        return redirect("pending_tasks_monitor")

    if not (celery_ok and redis_ok):
        messages.error(
            request, "Celery o Redis siguen inactivos. No se pueden reprocesar."
        )
        return redirect("pending_tasks_monitor")

    reencoladas = 0
    no_reconocidas = 0
    for p in pendientes:
        # Extraemos el nombre de la tarea y los argumentos
        task_name = p.task_name
        args = p.args or {}
        try:
            # 2️⃣ Buscamos si la tarea está en el despachador
            if task_name in TASK_DISPATCHER:
                TASK_DISPATCHER[task_name](args)
                p.delete()
                reencoladas += 1
                logger.info(
                    f"Tarea pendiente '{task_name}' reencolada correctamente (args={args})"
                )
            else:
                no_reconocidas += 1
                logger.warning(
                    f"Tarea '{task_name}' no reconocida o no registrada en el despachador."
                )
        except Exception as e:
            logger.error(
                f"Error reintentando tarea pendiente '{task_name}' (ID={p.id}): {e}"
            )

    # 3️⃣ Feedback visual al usuario

    if reencoladas:
        messages.success(
            request, f"{reencoladas} tarea(s) pendientes reencoladas correctamente."
        )
    else:
        messages.warning(
            request,
            "No se reencoló ninguna tarea (ninguna coincidía con las reglas definidas).",
        )

    messages.success(
        request, f"{reencoladas} tarea(s) pendientes reencoladas correctamente."
    )
    return redirect("pending_tasks_monitor")
