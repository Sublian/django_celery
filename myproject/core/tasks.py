from celery import shared_task
import csv, time
from django.core.files.storage import default_storage
from .models import FileProcess
import pandas as pd
import os

@shared_task
def send_welcome_email():
    username= 'Luis'
    print(f"Enviando correo de bienvenida a {username}...")
    time.sleep(5)  # Simulamos una operación lenta
    print(f"Correo enviado a {username} ✅")
    return f"Tarea terminada"

@shared_task
def print_heartbeat():
    print("❤️ Latido del sistema activo.")
    
@shared_task(bind=True)
def process_csv_file(self, file_id):
    try:
        obj = FileProcess.objects.get(id=file_id)
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
        time.sleep(5)

        total_rows = len(df)
        print(f"✅ Procesamiento completado: {total_rows} filas")

        # Puedes agregar lógica de procesamiento aquí (por ejemplo guardar resultados)
        return f"Archivo procesado correctamente. Total de filas: {total_rows}"

    except Exception as e:
        print(f"❌ Error procesando archivo: {e}")
        raise e