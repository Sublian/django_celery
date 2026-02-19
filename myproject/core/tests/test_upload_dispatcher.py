import pytest
from unittest.mock import patch
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.django_db
def test_upload_file_uses_dispatcher(client):

    fake_file = SimpleUploadedFile(
        "test.csv", b"name,age\nJohn,30", content_type="text/csv"
    )

    with patch("core.views.is_redis_available", return_value=True), patch(
        "core.views.is_celery_available", return_value=True
    ), patch("core.views.TaskDispatcher.dispatch") as mock_dispatch:

        response = client.post(
            reverse("upload_file"), {"name": "Test File", "file": fake_file}
        )

        assert response.status_code in [200, 302]
        assert mock_dispatch.called
