# En api_service/tasks.py

from celery import shared_task, group, chord
from celery.result import allow_join_result
from django.db import transaction
from django.utils import timezone
from .models import ApiBatchRequest, ApiService, ApiCallLog
from .services import MigoAPIClient
import logging
import json

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def consultar_ruc_task(self, ruc, retry_count=0):
    """Tarea asíncrona para consultar RUC con reintentos automáticos"""
    try:
        client = MigoAPIClient()
        result = client.consultar_ruc(ruc)
        return result
    
    except Exception as exc:
        # Reintentar en caso de error temporal
        if retry_count < 3:
            wait_time = 2 ** retry_count  # Backoff exponencial: 2, 4, 8 segundos
            raise self.retry(exc=exc, countdown=wait_time)
        
        # Registrar error final
        ApiCallLog.objects.create(
            service=ApiService.objects.filter(service_type='MIGO').first(),
            status='FAILED',
            request_data={'ruc': ruc},
            error_message=str(exc),
            called_from='consultar_ruc_task'
        )
        raise

@shared_task
def procesar_batch_ruc(ruc_list):
    """Procesa un batch de RUCs respetando rate limiting"""
    client = MigoAPIClient()
    results = []
    
    for ruc in ruc_list:
        try:
            # Pequeña pausa para respetar rate limiting
            time.sleep(0.5)
            result = client.consultar_ruc(ruc)
            results.append({'ruc': ruc, 'success': True, 'data': result})
        except Exception as e:
            results.append({'ruc': ruc, 'success': False, 'error': str(e)})
    
    return results

@shared_task
def limpiar_logs_antiguos(days=30):
    """Limpia logs de API más antiguos que 'days' días"""
    cutoff_date = timezone.now() - timezone.timedelta(days=days)
    deleted_count, _ = ApiCallLog.objects.filter(
        created_at__lt=cutoff_date
    ).delete()
    return f"Eliminados {deleted_count} logs antiguos"




@shared_task(bind=True)
def procesar_validacion_masiva_ruc(self, ruc_list, user_id=None, prioridad='facturacion_mensual'):
    """
    Tarea principal para validación masiva de RUCs previa a facturación
    
    Args:
        ruc_list: Lista de RUCs a validar (pueden ser miles)
        user_id: ID del usuario que solicita la validación
        prioridad: Contexto de uso (facturacion_mensual, onboarding, etc.)
    """
    # Crear registro de batch
    with transaction.atomic():
        batch_request = ApiBatchRequest.objects.create(
            service=ApiService.objects.filter(service_type='MIGO').first(),
            status='PROCESSING',
            input_data={'ruc_list': ruc_list, 'prioridad': prioridad},
            total_items=len(ruc_list),
            requested_by_id=user_id
        )
    
    try:
        # Dividir en subtareas por lotes de 100
        lotes = [ruc_list[i:i+100] for i in range(0, len(ruc_list), 100)]
        
        # Crear grupo de tareas paralelas (con límite de concurrencia)
        subtasks = []
        for i, lote in enumerate(lotes):
            # Espaciar tareas para respetar rate limiting (1 lote/segundo)
            countdown = i * 1  # 1 segundo entre cada lote
            subtask = procesar_lote_ruc.s(
                lote=lote,
                batch_id=str(batch_request.id),
                lote_numero=i+1
            ).set(countdown=countdown)
            subtasks.append(subtask)
        
        # Ejecutar subtasks y consolidar resultados
        job = group(subtasks)
        result_group = job.apply_async()
        
        with allow_join_result():
            resultados_lotes = result_group.get()
        
        # Consolidar resultados
        resultados_consolidados = {
            'validos': [],
            'invalidos': [],
            'total_procesado': 0
        }
        
        for resultado_lote in resultados_lotes:
            if resultado_lote.get('success'):
                resultados_consolidados['validos'].extend(resultado_lote.get('validos', []))
                resultados_consolidados['invalidos'].extend(resultado_lote.get('invalidos', []))
                resultados_consolidados['total_procesado'] += resultado_lote.get('total_procesado', 0)
        
        # Actualizar batch request final
        with transaction.atomic():
            batch_request.results = resultados_consolidados
            batch_request.processed_items = resultados_consolidados['total_procesado']
            batch_request.successful_items = len(resultados_consolidados['validos'])
            batch_request.failed_items = len(resultados_consolidados['invalidos'])
            batch_request.status = 'COMPLETED'
            batch_request.completed_at = timezone.now()
            batch_request.save()
        
        logger.info(f"Batch {batch_request.id} completado: "
                   f"{batch_request.successful_items} válidos, "
                   f"{batch_request.failed_items} inválidos")
        
        # Opcional: Disparar siguiente paso en el pipeline
        if prioridad == 'facturacion_mensual':
            # Preparar datos para facturación
            clientes_validos = [c['ruc'] for c in resultados_consolidados['validos']]
            iniciar_proceso_facturacion.delay(
                rucs_validados=clientes_validos,
                batch_id=str(batch_request.id),
                user_id=user_id
            )
        
        return {
            'batch_id': str(batch_request.id),
            'estadisticas': {
                'total': len(ruc_list),
                'procesados': resultados_consolidados['total_procesado'],
                'validos': len(resultados_consolidados['validos']),
                'invalidos': len(resultados_consolidados['invalidos']),
                'tasa_exito': (len(resultados_consolidados['validos']) / len(ruc_list)) * 100
            },
            'resumen_validos': resultados_consolidados['validos'][:10],  # Primeros 10
            'errores_comunes': obtener_errores_comunes(resultados_consolidados['invalidos'])
        }
    
    except Exception as e:
        logger.error(f"Error en validación masiva: {str(e)}", exc_info=True)
        
        with transaction.atomic():
            batch_request.status = 'FAILED'
            batch_request.error_summary = {'error': str(e)}
            batch_request.completed_at = timezone.now()
            batch_request.save()
        
        raise

@shared_task(bind=True, max_retries=3)
def procesar_lote_ruc(self, lote, batch_id=None, lote_numero=1):
    """Procesa un lote de hasta 100 RUCs"""
    try:
        client = MigoAPIClient()
        
        # Usar consulta masiva para el lote completo
        resultado = client.consultar_ruc_masivo(lote, batch_id)
        
        # Procesar resultados individuales
        validos = []
        invalidos = []
        
        for item in resultado.get('results', []):
            if item.get('success'):
                estado = item.get('estado_del_contribuyente', '').upper()
                condicion = item.get('condicion_de_domicilio', '').upper()
                
                if estado == 'ACTIVO' and condicion == 'HABIDO':
                    validos.append({
                        'ruc': item.get('ruc'),
                        'razon_social': item.get('nombre_o_razon_social'),
                        'direccion': item.get('direccion'),
                        'actualizado_en': item.get('actualizado_en')
                    })
                else:
                    invalidos.append({
                        'ruc': item.get('ruc'),
                        'razon_social': item.get('nombre_o_razon_social'),
                        'estado': estado,
                        'condicion': condicion,
                        'error': f'Estado: {estado}, Condición: {condicion}'
                    })
            else:
                invalidos.append({
                    'ruc': item.get('ruc', 'DESCONOCIDO'),
                    'error': 'Consulta fallida'
                })
        
        return {
            'success': True,
            'lote_numero': lote_numero,
            'total_procesado': len(lote),
            'validos': validos,
            'invalidos': invalidos,
            'tasa_exito_lote': (len(validos) / len(lote)) * 100
        }
    
    except Exception as exc:
        logger.warning(f"Reintentando lote {lote_numero}: {str(exc)}")
        
        # Backoff exponencial: 2, 4, 8 segundos
        countdown = 2 ** self.request.retries
        
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=countdown)
        
        # Si falla después de reintentos, marcar todos como inválidos
        return {
            'success': False,
            'lote_numero': lote_numero,
            'total_procesado': len(lote),
            'validos': [],
            'invalidos': [{'ruc': ruc, 'error': f'Error después de {self.max_retries} reintentos'} for ruc in lote],
            'error': str(exc)
        }

@shared_task
def iniciar_proceso_facturacion(rucs_validados, batch_id=None, user_id=None):
    """
    Tarea puente entre validación API y facturación
    
    Esta tarea se dispara automáticamente después de la validación masiva
    """
    from billing.tasks import generar_facturas_mensuales  # Importar del módulo billing
    
    logger.info(f"Iniciando facturación para {len(rucs_validados)} clientes validados")
    
    # Obtener datos adicionales de la base de datos
    clientes_completos = obtener_datos_clientes(rucs_validados)
    
    # Llamar a la tarea de facturación
    resultado_facturacion = generar_facturas_mensuales.delay(
        clientes=clientes_completos,
        contexto='post_validacion_api',
        metadata={'batch_api_id': batch_id, 'user_id': user_id}
    )
    
    return {
        'status': 'facturacion_iniciada',
        'clientes_a_facturar': len(clientes_completos),
        'task_id_facturacion': resultado_facturacion.id,
        'batch_api_id': batch_id
    }

def obtener_errores_comunes(invalidos):
    """Analiza errores comunes en RUCs inválidos"""
    from collections import Counter
    
    errores = [item.get('error', 'Desconocido') for item in invalidos]
    return dict(Counter(errores).most_common(5))

def obtener_datos_clientes(ruc_list):
    """
    Obtiene datos completos de clientes desde la base de datos
    
    Esta función debe ser implementada en tu módulo de clientes/CRM
    """
    # Esto es un placeholder - implementa según tus modelos
    try:
        from crm.models import Cliente
        return list(Cliente.objects.filter(ruc__in=ruc_list).values())
    except ImportError:
        # Fallback si el módulo CRM no existe aún
        return [{'ruc': ruc} for ruc in ruc_list]