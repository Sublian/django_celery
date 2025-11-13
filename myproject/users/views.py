from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm

def user_list(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'users/user_list.html', {'users': users})

def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario creado correctamente.")
            return redirect('user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/user_form.html', {'form': form, 'title': 'Crear usuario'})

def user_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect('user_list')
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'users/user_form.html', {'form': form, 'title': 'Editar usuario'})

def user_deactivate(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.deactivate()
    messages.warning(request, f"Usuario '{user.username}' desactivado.")
    return redirect('user_list')

def user_activate(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.activate()
    messages.success(request, f"Usuario '{user.username}' activado.")
    return redirect('user_list')