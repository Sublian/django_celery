from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from .models import FileProcess, TaskRecord
from .tasks import process_csv_file
from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import FileProcess
import os
import logging

logger = logging.getLogger(__name__)

class UploadForm(forms.ModelForm):
    class Meta:
        model = FileProcess
        fields = ['name', 'file']

def upload_file(request):
    if request.method == 'POST':
        logger.info("Usuario %s subió un archivo desde %s", request.user, request.META.get('REMOTE_ADDR'))
        name = request.POST.get('name')
        file = request.FILES.get('file')

        if not name or not file:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Debe completar todos los campos.'}, status=400)
            messages.error(request, 'Debe completar todos los campos.')
            return redirect('upload')

        # Crear registro del archivo
        obj = FileProcess.objects.create(name=name, file=file, status='pending')

        # Encolar tarea Celery
        process_csv_file.delay(obj.id)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'queued', 'file_id': obj.id})

        messages.success(request, f"Archivo '{name}' agregado a la cola de tareas.")
        return redirect('dashboard')

    return render(request, 'core/upload.html')

def dashboard(request):
    # --- 🔍 Filtro de búsqueda ---
    query = request.GET.get('q', '').strip()
    file_qs = FileProcess.objects.all().order_by('-created_at')

    if query:
        file_qs = file_qs.filter(
            Q(name__icontains=query) |
            Q(status__icontains=query) |
            Q(message__icontains=query)
        )
    # --- 📄 Paginación ---
    per_page = request.GET.get('per_page', '10')
    if per_page not in ['10', '20']:
        per_page = '10'

    paginator = Paginator(file_qs, int(per_page))
    page_number = request.GET.get('page')
    files_page = paginator.get_page(page_number)
    
    # --- Datos adicionales ---
    tasks = TaskRecord.objects.all().order_by('-created_at')[:10]

    context = {
        'files': files_page,
        'tasks': tasks,
        'query': query,
        'per_page': per_page,
    }
    return render(request, 'core/dashboard.html', context)

