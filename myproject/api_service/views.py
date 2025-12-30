# api_service/views.py - VERSIÓN CORREGIDA
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q  # ¡IMPORTANTE: Importar Count aquí!
from django.utils import timezone
from django.conf import settings 
from datetime import timedelta
from .models import ApiCallLog, ApiService, ApiEndpoint

@login_required
def dashboard_monitoreo(request):
    """Dashboard simple de monitoreo de APIs"""
    
    # Periodos de tiempo
    ahora_peru = timezone.now()
    hoy = ahora_peru.date()
    ultimas_24h = ahora_peru - timedelta(hours=24)
    ultima_semana = ahora_peru- timedelta(days=7)
    
    # Estadísticas generales
    total_logs = ApiCallLog.objects.count()
    logs_24h = ApiCallLog.objects.filter(created_at__gte=ultimas_24h)
    
    stats = {
        'total': total_logs,
        'ultimas_24h': logs_24h.count(),
        'exitosos': logs_24h.filter(status='SUCCESS').count(),
        'fallidos': logs_24h.filter(status='FAILED').count(),
        'tasa_exito': 0,
    }
    
    if logs_24h.count() > 0:
        stats['tasa_exito'] = round((stats['exitosos'] / logs_24h.count()) * 100, 1)
    
    # Servicios más usados
    servicios_stats = ApiService.objects.annotate(
        total_llamadas=Count('call_logs'),
        exitosas=Count('call_logs', filter=Q(call_logs__status='SUCCESS')),
        fallidas=Count('call_logs', filter=Q(call_logs__status='FAILED')),
        tiempo_promedio=Avg('call_logs__duration_ms')
    ).order_by('-total_llamadas')
    
    # Endpoints más problemáticos
    endpoints_problematicos = ApiEndpoint.objects.annotate(
        total_llamadas=Count('call_logs'),
        fallidas=Count('call_logs', filter=Q(call_logs__status='FAILED')),
    ).filter(fallidas__gt=0).order_by('-fallidas')[:10]
    
    # Últimos errores
    ultimos_errores = ApiCallLog.objects.filter(
        status='FAILED'
    ).select_related('service', 'endpoint').order_by('-created_at')[:20]
    
    # Errores comunes
    errores_comunes = ApiCallLog.objects.filter(
        status='FAILED',
        created_at__gte=ultima_semana
    ).values('error_message').annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    context = {
        'stats': stats,
        'servicios_stats': servicios_stats,
        'endpoints_problematicos': endpoints_problematicos,
        'ultimos_errores': ultimos_errores,
        'errores_comunes': errores_comunes,
        'hoy': hoy,
        #adicionales
        'hora_actual': ahora_peru,  # ← Hora exacta Perú
    }
    
    return render(request, 'api_service/dashboard.html', context)