from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from .models import FileProcess
from .tasks import process_csv_file
from django import forms
import os

class UploadForm(forms.ModelForm):
    class Meta:
        model = FileProcess
        fields = ['name', 'file']

def upload_file(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return HttpResponseBadRequest("❌ Formulario inválido.")
        
        obj = form.save()
        
            # Validar extensión del archivo
        valid_extensions = ['.csv', '.xls', '.xlsx']
        ext = os.path.splitext(obj.file.name)[1].lower()
        
        if ext not in valid_extensions:
            obj.delete()  # limpia el registro si no es válido
            return HttpResponseBadRequest(
                f"❌ Tipo de archivo no permitido: {ext}. Solo se aceptan CSV o Excel (.csv, .xls, .xlsx)."
            )
        # Encolar tarea asíncrona
        process_csv_file.delay(obj.id)
        return HttpResponse(f"Tarea encolada para el archivo {obj.name}")
            
    else:
        form = UploadForm()
    return render(request, 'core/upload.html', {'form': form})
