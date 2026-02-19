from django.db import transaction
from core.models import FileProcess
from core.tasks import process_csv_file


def create_file_process_and_enqueue(*, name, file, user=None):
    """
    Crea un FileProcess y encola la tarea Celery
    solo después de que la transacción se haya confirmado.
    """

    file_process = FileProcess.objects.create(
        name=name,
        file=file,
        status="pending",
        user=user if hasattr(FileProcess, "user") else None,
    )

    # Encolar solo después del commit
    transaction.on_commit(lambda: process_csv_file.apply_async(args=[file_process.id]))

    return file_process
