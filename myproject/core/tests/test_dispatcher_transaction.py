import pytest
from unittest.mock import patch
from django.db import transaction
from core.services.task_dispatcher import TaskDispatcher


@pytest.mark.django_db(transaction=True)
def test_dispatcher_executes_after_commit():

    with patch("core.tasks.process_csv_file.apply_async") as mock_apply:

        with transaction.atomic():
            TaskDispatcher.dispatch(
                "process_csv_file",
                file_id=123
            )

            # No debe ejecutarse aún
            assert not mock_apply.called

        # Después del commit sí
        assert mock_apply.called
