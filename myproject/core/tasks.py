from celery import shared_task
import csv, time
from django.db import transaction
from django.core.files.storage import default_storage
from .models import FileProcess, TaskRecord
from django.utils import timezone
import pandas as pd
import os


@shared_task
def send_welcome_email():
    record = TaskRecord.objects.create(task_name='send_welcome_email', status='STARTED')
    print("📧 Sending welcome email...")
    record.status = 'SUCCESS'
    record.finished_at = timezone.now()
    record.save()
    return "Welcome email sent!"

@shared_task
def print_heartbeat():
    record = TaskRecord.objects.create(task_name='print_heartbeat', status='STARTED')
    print("💓 Heartbeat")
    record.status = 'SUCCESS'
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
        task_id=(getattr(self.request, 'id', None)),
        task_name='process_csv_file',
        status='STARTED',
        created_at=timezone.now()
    )
    try:
        obj.status = 'processing'
        obj.save(update_fields=['status'])
        
        file_path = obj.file.path
        ext = os.path.splitext(file_path)[1].lower()
        print(f"📂 Procesando archivo: {file_path}")

        # Leer el archivo dependiendo de la extensión
        if ext == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip')
        elif ext in ('.xls', '.xlsx'):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Tipo de archivo no soportado: {ext}")
        
        # Simular carga pesada
        time.sleep(2)
        
        total_rows = len(df)
        print(f"✅ Procesamiento completado: {total_rows} filas")
        
        # Guardar resultado en TaskRecord y FileProcess
        record.status = 'SUCCESS'
        record.result = f"Total de filas: {total_rows}"
        record.finished_at = timezone.now()
        record.save(update_fields=['status', 'result', 'finished_at'])
        
        # Actualizar el estado y marcar como procesado
        obj.status = 'done'
        obj.processed = True
        obj.message = f'Procesamiento completado: {total_rows} filas'
        obj.save(update_fields=['status', 'processed', 'message'])

        # Puedes agregar lógica de procesamiento aquí (por ejemplo guardar resultados)
        return {"status": "ok", "rows": total_rows}

    except Exception as e:
        # Guardar error en TaskRecord y FileProcess
        print(f"❌ Error procesando archivo: {e}")
        record.status = 'FAILURE'
        record.result = str(e)
        record.finished_at = timezone.now()
        record.save(update_fields=['status', 'result', 'finished_at'])
        
        obj.status = 'error'
        obj.message = str(e)
        obj.save(update_fields=['status', 'message'])
        raise 