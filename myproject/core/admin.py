from django.contrib import admin
from .models import FileProcess, TaskRecord

@admin.register(FileProcess)
class FileProcessAdmin(admin.ModelAdmin):
    list_display = ('id','name','status','processed','created_at')

@admin.register(TaskRecord)
class TaskRecordAdmin(admin.ModelAdmin):
    list_display = ('task_id','task_name','status','fileprocess','started_at','finished_at')
    list_filter = ('status','task_name')
