# billing/views/company.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from billing.models import Company
from billing.forms.company import CompanyForm


def company_list(request):
    companies = Company.objects.all().order_by('id')
    return render(request, 'billing/company/list.html', {"companies": companies})


def company_create(request):
    form = CompanyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Compañía creada correctamente.")
        return redirect("billing:company_list")

    return render(request, "billing/company/create.html", {"form": form})


def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    form = CompanyForm(request.POST or None, request.FILES or None, instance=company)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Compañía actualizada correctamente.")
        return redirect("billing:company_detail", pk=pk)

    return render(request, "billing/company/edit.html", {"form": form, "company": company})


def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk)
    return render(request, 'billing/company/detail.html', {"company": company})


def company_toggle_active(request, pk):
    company = get_object_or_404(Company, pk=pk)
    company.active = not company.active
    company.save()
    messages.info(request, f"Estado cambiado: {'Activa' if company.active else 'Inactiva'}")
    return redirect('billing:company_list')
