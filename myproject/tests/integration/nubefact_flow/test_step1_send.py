# tests/integration/nubefact_flow/test_step1_send.py
# Como usar: al final colocar el numero de la factura en un valor como este
#python -m tests.integration.nubefact_flow.test_step1_send 91515

import os
import sys
import django

# ✅ Configurar Django PRIMERO
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

# Ahora sí, importaciones
import pytest
import asyncio
from datetime import datetime
from pathlib import Path

# ✅ Usar importación absoluta
from tests.integration.nubefact_flow.base_test import NubefactTestBase
from api_service.models import ApiCallLog
from asgiref.sync import sync_to_async


@pytest.mark.django_db
@pytest.mark.integration
class TestNubefactSend(NubefactTestBase):
    """
    Prueba de integración: Solo envío a NubeFact.
    Verifica que el servicio async envía correctamente y guarda logs.
    """
    
    @pytest.mark.asyncio
    async def test_send_invoice_async(self, numero_factura=None):
        """
        Envía una factura usando el servicio asíncrono.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 1: ENVÍO ASYNC A NUBEFACT")
        print("="*60)
        
        # Configurar
        output_dir = self.setup_output_dir("step1_send")
        numero = numero_factura or str(int(datetime.now().timestamp() % 100000))
        invoice_data = self.create_test_invoice_data(numero)
        
        print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
        
        # Obtener servicio
        service = self.get_async_service()
        
        # Enviar
        print(f"\n📤 Enviando a NubeFact...")
        start = datetime.now()
        
        try:
            response = await service.generar_comprobante(
                invoice_data,
                caller_context="test_step1_send_async"
            )
            
            duration = (datetime.now() - start).total_seconds()
            print(f"📥 Respuesta recibida en {duration:.2f}s")
            
            # Guardar respuesta
            filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            filepath = self.save_response(response, filename, output_dir)
            print(f"✅ Respuesta guardada en: {filepath}")
            
            # Mostrar resultado
            if response.get('aceptada_por_sunat'):
                print(f"   ✅ ACEPTADA por SUNAT")
            else:
                print(f"   ⏳ PENDIENTE de SUNAT")
            
            print(f"   Hash: {response.get('codigo_hash', 'N/A')[:30]}...")
            
            # Verificar log en BD
            await asyncio.sleep(1)  # Esperar logging async
            await self._check_logs(invoice_data['numero'])
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "response": response,
                "output_dir": output_dir,
                "filepath": filepath
            }
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    @pytest.mark.asyncio
    async def test_send_invoice_sync(self, numero_factura=None):
        """
        Envía una factura usando el servicio síncrono.
        """
        print("\n" + "="*60)
        print("🧪 TEST STEP 1: ENVÍO SYNC A NUBEFACT")
        print("="*60)
        
        # Configurar
        output_dir = self.setup_output_dir("step1_send_sync")
        numero = numero_factura or str(int(datetime.now().timestamp() % 100000))
        invoice_data = self.create_test_invoice_data(numero)
        
        print(f"\n📄 Factura: {invoice_data['serie']}-{invoice_data['numero']}")
        
        # Obtener servicio
        service = self.get_sync_service()
        
        # Enviar
        print(f"\n📤 Enviando a NubeFact...")
        start = datetime.now()
        
        try:
            response = service.generar_comprobante(invoice_data)
            
            duration = (datetime.now() - start).total_seconds()
            print(f"📥 Respuesta recibida en {duration:.2f}s")
            
            # Guardar respuesta
            filename = f"response_{invoice_data['serie']}_{invoice_data['numero']}.json"
            filepath = self.save_response(response, filename, output_dir)
            print(f"✅ Respuesta guardada en: {filepath}")
            
            # Mostrar resultado
            if response.get('aceptada_por_sunat'):
                print(f"   ✅ ACEPTADA por SUNAT")
            else:
                print(f"   ⏳ PENDIENTE de SUNAT")
            
            print(f"   Hash: {response.get('codigo_hash', 'N/A')[:30]}...")
            
            # Verificar log en BD (sync ya guardó)
            await self._check_logs(invoice_data['numero'])
            
            return {
                "success": True,
                "invoice_data": invoice_data,
                "response": response,
                "output_dir": output_dir,
                "filepath": filepath
            }
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _check_logs(self, numero: str):
        """Verifica que existan logs para esta factura."""
        from api_service.models import ApiCallLog
        
        count = await sync_to_async(
            lambda: ApiCallLog.objects.filter(
                response_data__contains=f'"{numero}"'
            ).count()
        )()
        
        print(f"\n📊 LOGS EN BD: {count}")
        
        if count > 0:
            latest = await sync_to_async(
                lambda: ApiCallLog.objects.filter(
                    response_data__contains=f'"{numero}"'
                ).order_by('-created_at').first()
            )()
            
            if latest:
                called_from = await sync_to_async(lambda: latest.called_from)()
                status = await sync_to_async(lambda: latest.status)()
                print(f"   Último log: {status} - llamado desde: {called_from}")


# Función para ejecutar manualmente
async def main():
    # Configurar Django para ejecución manual
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    django.setup()
    
    # Tomar número de argumento si existe
    import sys
    numero = sys.argv[1] if len(sys.argv) > 1 else None
    
    test = TestNubefactSend()
    result = await test.test_send_invoice_async(numero)
    if result["success"]:
        print(f"\n✅ PRUEBA EXITOSA")
    else:
        print(f"\n❌ PRUEBA FALLÓ: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())