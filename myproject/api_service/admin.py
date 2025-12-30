# admin.py
from django.contrib import admin
from .models import ApiService, ApiEndpoint, ApiCallLog

@admin.register(ApiService)
class ApiServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_type', 'is_active', 'requests_per_minute')
    list_filter = ('service_type', 'is_active')

@admin.register(ApiCallLog)
class ApiCallLogAdmin(admin.ModelAdmin):
    list_display = ('service', 'endpoint', 'status', 'response_code', 'duration_ms', 'created_at')
    list_filter = ('status', 'service', 'created_at')
    search_fields = ('request_data', 'error_message')
    readonly_fields = ('created_at',)
    ordering= ('-created_at',)    
    list_per_page = 100
    


@admin.register(ApiEndpoint)
class ApiEndpointAdmin(admin.ModelAdmin):
    list_display = ('name', 'service', 'path', 'method', 'is_active', 'custom_rate_limit')
    list_filter = ('service', 'method', 'is_active')
    search_fields = ('name', 'path', 'description')
    list_select_related = ('service',)
    
    list_per_page = 100
    
    ordering = ('service', 'path')  # ← Ordenar primero por servicio, luego por path
        
    # Esto muestra los endpoints agrupados por servicio en el admin
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "service":
            # Ordenar servicios por nombre
            kwargs["queryset"] = ApiService.objects.order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
        