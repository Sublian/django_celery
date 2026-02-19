from celery import shared_task
import csv, time
from django.db import transaction
from django.core.files.storage import default_storage
from django.utils import timezone
import pandas as pd
import os, logging
from .models import FileProcess, TaskRecord, PendingTask
from .utils.celery_status import is_celery_available, is_redis_available


logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email():
    record = TaskRecord.objects.create(task_name="send_welcome_email", status="STARTED")
    print("📧 Sending welcome email...")
    record.status = "SUCCESS"
    record.finished_at = timezone.now()
    record.save()
    return "Welcome email sent!"


@shared_task
def print_heartbeat():
    record = TaskRecord.objects.create(task_name="print_heartbeat", status="STARTED")
    print("💓 Heartbeat")
    record.status = "SUCCESS"
    record.finished_at = timezone.now()
    record.save()
    return "Heartbeat sent!"


@shared_task(bind=True)
def process_csv_file(self, file_id):
    """Procesa CSV/XLSX, crea un TaskRecord vinculado al FileProcess y actualiza ambos modelos."""
    obj = FileProcess.objects.get(id=file_id)

    # Crear registro de task
    record = TaskRecord.objects.create(
        fileprocess=obj,
        task_id=(getattr(self.request, "id", None)),
        task_name="process_csv_file",
        status="STARTED",
        created_at=timezone.now(),
    )
    try:
        obj.status = "processing"
        obj.save(update_fields=["status"])

        file_path = obj.file.path
        ext = os.path.splitext(file_path)[1].lower()
        logger.info(f"📂 Iniciando procesamiento de {obj.name}")
        print(f"📂 Procesando archivo: {file_path}")

        # Leer el archivo dependiendo de la extensión
        if ext == ".csv":
            df = pd.read_csv(file_path, encoding="utf-8", on_bad_lines="skip")
        elif ext in (".xls", ".xlsx"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Tipo de archivo no soportado: {ext}")

        # Simular carga pesada
        time.sleep(2)

        total_rows = len(df)
        print(f"✅ Procesamiento completado: {total_rows} filas")

        # Guardar resultado en TaskRecord y FileProcess
        record.status = "SUCCESS"
        record.result = f"Total de filas: {total_rows}"
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "result", "finished_at"])

        # Actualizar el estado y marcar como procesado
        obj.status = "done"
        obj.processed = True
        obj.message = f"Procesamiento completado: {total_rows} filas"
        obj.save(update_fields=["status", "processed", "message"])
        logger.info(f"✅ Archivo {obj.name} procesado correctamente.")

        # Puedes agregar lógica de procesamiento aquí (por ejemplo guardar resultados)
        return {"status": "ok", "rows": total_rows}

    except Exception as e:
        # Guardar error en TaskRecord y FileProcess
        print(f"❌ Error procesando archivo: {e}")
        logger.error(f"❌ Error procesando archivo {file_id}: {e}", exc_info=True)
        record.status = "FAILURE"
        record.result = str(e)
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "result", "finished_at"])

        obj.status = "error"
        obj.message = str(e)
        obj.save(update_fields=["status", "message"])
        raise


# 📦 Reutilizamos el despachador central de tareas
TASK_DISPATCHER = {
    "core.tasks.process_csv_file": lambda args: process_csv_file.delay(**args),
    # Ejemplo para futuras tareas:
    # 'core.tasks.generar_reporte': lambda args: generar_reporte.delay(args.get('reporte_id')),
}


# @shared_task
# def reprocess_pending_tasks():
#     """
#     Reprocesa automáticamente las tareas pendientes guardadas cuando Celery o Redis estaban inactivos.
#     Se ejecuta cada 5 minutos.
#     """
#     redis_ok = is_redis_available()
#     # celery_ok = is_celery_available()
#     celery_ok = redis_ok
#     logger.info(
#         f"🔁 [AutoReprocess] Redis: {redis_ok}, Celery: {celery_ok} (modo interno Celery)"
#     )
#     if not (celery_ok and redis_ok):
#         logger.warning(f"⚠️ Celery o Redis aún no disponibles. Reintentará más tarde.")
#         return "Celery/Redis no disponibles"

#     pending = PendingTask.objects.all().order_by("-created_at")
#     total = pending.count()

#     if total == 0:
#         logger.info("✅ No hay tareas pendientes por reprocesar.")
#         return "Sin pendientes"

#     logger.info(f"♻️ Detectadas {total} tarea(s) pendientes para reprocesar.")

#     reprocesadas = 0
#     no_reconocidas = 0

#     for task in pending:
#         task_name = task.task_name
#         args = task.args or {}

#         try:
#             # Despachador dinámico
#             if task_name in TASK_DISPATCHER:
#                 TASK_DISPATCHER[task_name](args)
#                 # task.processed = True
#                 # task.processed_at = timezone.now()
#                 task.delete()
#                 reprocesadas += 1
#                 logger.info(f"✅ Reprocesada tarea {task.id}: {task_name} ({args})")
#             else:
#                 no_reconocidas += 1
#                 logger.warning(
#                     f"⚠️ Tarea '{task_name}' no está registrada en el despachador."
#                 )
#         except Exception as e:
#             logger.error(f"❌ Error reprocesando tarea {task.id}: {e}", exc_info=True)

#     logger.info(f"🔁 Reprocesadas: {reprocesadas}, No reconocidas: {no_reconocidas}")

#     return f"{reprocesadas} tareas reprocesadas, {no_reconocidas} no reconocidas."

@shared_task
def reprocess_pending_tasks(batch_size=50):
    pending_qs = PendingTask.objects.filter(processed=False).order_by('created_at')
    reprocesadas = 0
    with transaction.atomic():
        to_process = list(pending_qs.select_for_update(skip_locked=True)[:batch_size])
        for task in to_process:
            try:
                if task.task_name in TASK_DISPATCHER:
                    TASK_DISPATCHER[task.task_name](task.args or {})
                    task.delete()
                    reprocesadas += 1
                else:
                    task.attempts = F('attempts') + 1
                    task.save()
            except Exception as e:
                task.attempts = F('attempts') + 1
                task.save()
    return f"{reprocesadas} reprocesadas"
