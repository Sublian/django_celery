from django.db import transaction
from core.tasks import process_csv_file


class TaskDispatcher:

    TASK_MAP = {
        "process_csv_file": lambda args: process_csv_file.apply_async(
            args=[args["file_id"]]
        ),
    }

    @classmethod
    def dispatch(cls, task_name: str, **kwargs):
        if task_name not in cls.TASK_MAP:
            raise ValueError(f"Tarea '{task_name}' no registrada.")

        transaction.on_commit(lambda: cls.TASK_MAP[task_name](kwargs))
