# En api_service/pipeline.py (archivo nuevo)
from celery import chain
from .tasks import (
    procesar_validacion_masiva_ruc,
    iniciar_proceso_facturacion
)
from billing.tasks import (
    generar_facturas_mensuales,
    generar_reportes_facturacion,
    enviar_notificaciones
)

def crear_pipeline_facturacion_mensual(fecha_corte=None, user_id=None):
    """
    Crea el pipeline completo para facturación mensual
    
    1. Obtener suscripciones a facturar
    2. Validar RUCs masivamente con APIMIGO
    3. Generar facturas para clientes válidos
    4. Generar reportes
    5. Enviar notificaciones
    """
    from billing.utils import obtener_suscripciones_a_facturar
    
    # 1. Obtener suscripciones
    suscripciones = obtener_suscripciones_a_facturar(fecha_corte)
    rucs_a_validar = list({s.cliente.ruc for s in suscripciones if s.cliente.ruc})
    
    logger.info(f"Iniciando pipeline para {len(rucs_a_validar)} RUCs, {len(suscripciones)} suscripciones")
    
    # 2. Crear pipeline Celery con todas las etapas
    pipeline = chain(
        # Etapa 1: Validación masiva de RUCs
        procesar_validacion_masiva_ruc.s(
            ruc_list=rucs_a_validar,
            user_id=user_id,
            prioridad='facturacion_mensual'
        ),
        
        # Etapa 2: Generar facturas (se dispara automáticamente desde la etapa 1)
        # La función iniciar_proceso_facturacion se llama desde procesar_validacion_masiva_ruc
        
        # Etapa 3: Reportes y notificaciones
        generar_reportes_facturacion.s(user_id=user_id),
        enviar_notificaciones.s(tipo='facturacion_mensual')
    )
    
    # Ejecutar pipeline
    result = pipeline.apply_async()
    
    return {
        'pipeline_id': result.id,
        'estadisticas_iniciales': {
            'rucs_a_validar': len(rucs_a_validar),
            'suscripciones': len(suscripciones),
            'fecha_corte': fecha_corte or 'actual'
        },
        'tasks': [
            'validacion_masiva_ruc',
            'generacion_facturas',
            'reportes',
            'notificaciones'
        ]
    }