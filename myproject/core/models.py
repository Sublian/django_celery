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
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False) 

    def __str__(self):
        return f"{self.name} - {self.status}"


class TaskRecord(models.Model):
    TASK_STATUS = [
        ('PENDING', 'Pending'),
        ('STARTED', 'Started'),
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    ]
    # FK a FileProcess (nullable para permitir tareas no ligadas)
    fileprocess = models.ForeignKey(
        FileProcess,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='task_records'
    )
    task_id = models.CharField(max_length=255, null=True, blank=True)  # id del task (celery request.id)
    task_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='PENDING')
    result = models.TextField(null=True, blank=True)                    # mensaje/resultados
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Nota: related_name='task_records' te permite acceder a fileprocess.task_records.all()
    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.task_name} ({self.status})"