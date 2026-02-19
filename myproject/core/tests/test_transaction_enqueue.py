import pytest
from unittest.mock import patch
from django.db import transaction
from core.models import FileProcess


@pytest.mark.django_db(transaction=True)
def test_task_is_enqueued_only_after_commit():

    with patch("core.views.process_csv_file.apply_async") as mock_apply:

        with transaction.atomic():
            obj = FileProcess.objects.create(
                name="test.csv",
                file="dummy.csv",
                status="pending",
            )

            from core.views import transaction as view_transaction

            view_transaction.on_commit(
                lambda: mock_apply(args=[obj.id])
            )

            assert not mock_apply.called

        assert mock_apply.called
