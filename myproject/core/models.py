from django.db import models

class FileProcess(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ]
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.status}"
