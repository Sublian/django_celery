import pytest
from unittest.mock import patch
from django.db import transaction
from core.models import FileProcess
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_task_is_enqueued_only_after_commit():

    user = User.objects.create(username="testuser")

    with patch("core.views.process_csv_file.apply_async") as mock_apply:

        with transaction.atomic():
            obj = FileProcess.objects.create(
                name="test.csv",
                file="dummy.csv",
                status="pending",
                user=user,
            )

            from core.views import transaction as view_transaction

            view_transaction.on_commit(
                lambda: mock_apply(args=[obj.id])
            )

            # Aún no debería haberse llamado
            assert not mock_apply.called

        # Después del commit sí
        assert mock_apply.called
