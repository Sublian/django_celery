"""
PRUEBA SINCRÓNICA FINAL - Facturación + PDF + QR
CORREGIDO: Terminología correcta y logging mejorado
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
import django

django.setup()

from billing.services.invoice_service import InvoiceService
from shared.utils.pdf.invoice_generator import InvoicePDFGenerator
from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync
from asgiref.sync import async_to_sync


class InvoiceTestRunner:
    """Runner para pruebas de facturación con PDF y QR"""

    def __init__(self, config=None):
        self.config = config or self.get_default_config()
        self.nubefact_service = None
        self.test_results = {
            "start_time": None,
            "end_time": None,
            "steps": {},
            "errors": [],
            "generated_files": [],
        }

    def get_default_config(self):
        return {
            "generate_pdf": True,
            "save_to_disk": True,
            "output_dir": Path("test_output"),
            "use_real_nubefact": False,
            "simulate_nubefact_response": True,
            "log_level": "detailed",
        }

    def log(self, message, level="info", emoji="ℹ️"):
        print(f"{emoji} {message}")

    def create_test_invoice_data(self, invoice_number=None):
        """Crea datos de prueba completos para una factura"""
        if invoice_number is None:
            invoice_number = f"{int(datetime.now().timestamp() % 100000)}"

        # ✅ CORRECCIÓN: Usar RUC válido (último dígito 6)
        return {
            "operacion": "generar_comprobante",
            "tipo_de_comprobante": "1",
            "serie": "F001",
            "numero": invoice_number,
            "sunat_transaction": "1",
            "cliente_tipo_de_documento": "6",
            "cliente_numero_de_documento": "20343443961",  # RUC válido
            "cliente_denominacion": "EMPRESA DE PRUEBA S.A.C.",
            "cliente_direccion": "AV. LOS EJEMPLOS 123, LIMA - LIMA - SAN ISIDRO",
            "cliente_email": "contacto@empresaprueba.com",
            "fecha_de_emision": datetime.now().strftime("%Y-%m-%d"),
            "fecha_de_vencimiento": datetime.now().strftime("%Y-%m-%d"),
            "moneda": "1",
            "tipo_de_cambio": "1",
            "porcentaje_de_igv": "18.00",
            "total_gravada": "847.46",
            "total_igv": "152.54",
            "total": "1000.00",
            "enviar_automaticamente_a_la_sunat": "false",
            "enviar_automaticamente_al_cliente": "false",
            "items": [
                {
                    "unidad_de_medida": "ZZ",
                    "codigo": "SERV-001",
                    "descripcion": "SERVICIO DE CONSULTORÍA IT - Asesoría técnica",
                    "cantidad": "10",
                    "valor_unitario": "84.746",
                    "precio_unitario": "100.00",
                    "subtotal": "847.46",
                    "tipo_de_igv": "1",
                    "igv": "152.54",
                    "total": "1000.00",
                    "codigo_producto_sunat": "81112105",
                }
            ],
        }

    def has_error_response(self, response):
        """
        Determina si la respuesta de NubeFact indica error
        """
        # Si hay campo 'error' o 'errors' con contenido, es un error
        if response.get("error") and str(response["error"]).strip():
            return True, f"Error: {response['error']}"

        if response.get("errors") and response["errors"]:
            errors = response["errors"]
            if isinstance(errors, list) and errors:
                return True, f"Errors: {', '.join(str(e) for e in errors)}"
            if isinstance(errors, str) and errors.strip():
                return True, f"Errors: {errors}"

        return False, None

    def get_sunat_status_text(self, aceptada_por_sunat):
        """
        ✅ CORRECCIÓN: Terminología correcta para estado SUNAT
        """
        if aceptada_por_sunat is True:
            return "✅ ACEPTADA"
        elif aceptada_por_sunat is False:
            return "⏳ PENDIENTE (esperando actualización)"
        else:
            return "❓ DESCONOCIDO"

    def send_to_nubefact_sync(self, invoice_data):
        """Envía a NubeFact con logging de fallos"""
        self.log(
            f"Enviando factura {invoice_data['serie']}-{invoice_data['numero']} a NubeFact..."
        )

        if (
            not self.config["use_real_nubefact"]
            and self.config["simulate_nubefact_response"]
        ):
            import time

            time.sleep(1)
            return self.simulate_nubefact_response(invoice_data)
        
            
        async def _init_and_call():
            service = NubefactServiceAsync()
            await service._async_init()  # Inicializar explícitamente
            return await service.generar_comprobante(invoice_data)

        try:
            response =  async_to_sync(_init_and_call)()
        except Exception as e:
            # ✅ El error ya debería estar logueado por nubefact_service_async.py
            self.log(
                f"❌ Error en comunicación con NubeFact: {str(e)}", "error", "❌"
            )
            raise

        # Verificar error en respuesta
        is_error, error_msg = self.has_error_response(response)
        if is_error:
            self.log(f"❌ Error en respuesta de NubeFact: {error_msg}", "error", "❌")
            raise ValueError(f"NubeFact respondió con error: {error_msg}")

        # ✅ CORRECCIÓN: Usar terminología correcta
        sunat_status = response.get("aceptada_por_sunat")
        status_text = self.get_sunat_status_text(sunat_status)
        self.log(f"✅ {status_text}", "success", "✅")

        # Mostrar información adicional si está disponible
        if response.get("sunat_description"):
            self.log(f"   SUNAT: {response['sunat_description']}", "info")

        self.log(f"✅ Respuesta válida recibida de NubeFact", "success", "✅")
        return response

    def simulate_nubefact_response(self, invoice_data):
        """Simula respuesta exitosa de NubeFact"""
        return {
            "tipo_de_comprobante": 1,
            "serie": invoice_data["serie"],
            "numero": int(invoice_data["numero"]),
            "enlace": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}",
            "aceptada_por_sunat": True,
            "sunat_description": "La Factura Electrónica ha sido ACEPTADA",
            "sunat_responsecode": "0",
            "cadena_para_codigo_qr": f"20123456789|01|{invoice_data['serie']}|{invoice_data['numero']}|152.54|1000.0|{invoice_data['fecha_de_emision']}|6|{invoice_data['cliente_numero_de_documento']}|TEST_HASH_SIMULADO|",
            "codigo_hash": f"TEST_HASH_{invoice_data['numero']}_SIMULADO",
            "enlace_del_pdf": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}.pdf",
            "enlace_del_xml": f"https://www.nubefact.com/cpe/test-{invoice_data['numero']}.xml",
        }

    def generate_pdf_with_qr(self, invoice_data, nubefact_response):
        """Genera PDF con QR"""
        self.log("Generando PDF con código QR...")

        invoice_data.update(
            {
                "codigo_hash": nubefact_response.get("codigo_hash"),
                "cadena_para_codigo_qr": nubefact_response.get("cadena_para_codigo_qr"),
                "qr_url": nubefact_response.get("cadena_para_codigo_qr"),
                "xml_url": nubefact_response.get("enlace_del_xml"),
                "enlace_del_pdf": nubefact_response.get("enlace_del_pdf"),
                "sunat_response": nubefact_response,
                "aceptada_por_sunat": nubefact_response.get(
                    "aceptada_por_sunat", False
                ),
            }
        )

        template_name = invoice_data.get("template", "billing/factura_electronica.html")
        pdf_generator = InvoicePDFGenerator(invoice_data, template_name)
        pdf_content = pdf_generator.generate_sync()

        self.log(f"✅ PDF generado ({len(pdf_content)} bytes)", "success", "✅")
        return pdf_content

    def save_pdf_to_disk(self, pdf_content, invoice_data):
        """Guarda PDF en disco"""
        output_dir = self.config["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"factura_{invoice_data['serie']}_{invoice_data['numero']}_{datetime.now().strftime('%Y%m%d')}.pdf"
        filepath = output_dir / filename

        with open(filepath, "wb") as f:
            f.write(pdf_content)

        self.log(f"💾 PDF guardado: {filepath}", "success", "💾")
        return str(filepath)

    def run_single_test(self, invoice_number=None):
        """Ejecuta prueba completa"""
        self.test_results["start_time"] = datetime.now()

        try:
            # Paso 1: Preparar datos
            self.log("\n" + "=" * 60)
            self.log("PASO 1: PREPARANDO DATOS DE FACTURA")
            self.log("=" * 60)

            invoice_data = self.create_test_invoice_data(invoice_number)
            self.log(
                f"✅ Datos preparados: {invoice_data['serie']}-{invoice_data['numero']}"
            )
            self.log(f"   Cliente: {invoice_data['cliente_denominacion']}")
            self.log(f"   RUC: {invoice_data['cliente_numero_de_documento']}")
            self.log(f"   Total: S/ {invoice_data['total']}")
            self.log(f"   Items: {len(invoice_data['items'])}")

            # Paso 2: Enviar a NubeFact
            self.log("\n" + "=" * 60)
            self.log("PASO 2: ENVIANDO A NUBEFACT")
            self.log("=" * 60)

            nubefact_response = self.send_to_nubefact_sync(invoice_data)

            # Paso 3: Generar PDF
            if self.config["generate_pdf"]:
                self.log("\n" + "=" * 60)
                self.log("PASO 3: GENERANDO PDF CON CÓDIGO QR")
                self.log("=" * 60)

                pdf_content = self.generate_pdf_with_qr(invoice_data, nubefact_response)

                # Paso 4: Guardar PDF
                if self.config["save_to_disk"] and pdf_content:
                    self.log("\n" + "=" * 60)
                    self.log("PASO 4: GUARDANDO ARCHIVO")
                    self.log("=" * 60)

                    filepath = self.save_pdf_to_disk(pdf_content, invoice_data)

                    # Resumen final
                    file_size_kb = len(pdf_content) / 1024
                    self.log(f"\n📊 RESUMEN DEL ARCHIVO:")
                    self.log(f"   Ruta: {filepath}")
                    self.log(f"   Tamaño: {file_size_kb:.1f} KB")
                    self.log(
                        f"   Factura: {invoice_data['serie']}-{invoice_data['numero']}"
                    )
                    self.log(
                        f"   QR incluido: {'✅' if nubefact_response.get('cadena_para_codigo_qr') else '❌'}"
                    )
                    self.log(
                        f"   Hash incluido: {'✅' if nubefact_response.get('codigo_hash') else '❌'}"
                    )

                    # ✅ CORRECCIÓN: Usar terminología correcta
                    sunat_status = nubefact_response.get("aceptada_por_sunat")
                    status_text = self.get_sunat_status_text(sunat_status)
                    self.log(f"   Estado SUNAT: {status_text}")

            # Éxito completo
            self.test_results["end_time"] = datetime.now()
            duration = (
                self.test_results["end_time"] - self.test_results["start_time"]
            ).total_seconds()

            self.log("\n" + "=" * 60)
            self.log("🏁 PRUEBA COMPLETADA")
            self.log("=" * 60)
            self.log(f"⏱️  Duración total: {duration:.2f} segundos")

            return {
                "success": True,
                "invoice_data": invoice_data,
                "nubefact_response": nubefact_response,
                "generated_files": [filepath] if self.config["save_to_disk"] else [],
                "aceptada_por_sunat": nubefact_response.get("aceptada_por_sunat"),
                "envio_exitoso": True,
            }

        except Exception as e:
            self.test_results["end_time"] = datetime.now()
            self.log(f"\n❌ PRUEBA FALLIDA: {str(e)}", "error", "❌")
            import traceback

            traceback.print_exc()

            return {
                "success": False,
                "error": str(e),
                "nubefact_response": (
                    nubefact_response if "nubefact_response" in locals() else None
                ),
            }


def main():
    print("\n" + "=" * 60)
    print("🧪 PRUEBA SINCRÓNICA FINAL - TERMINOLOGÍA CORREGIDA")
    print("=" * 60)

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Usar NubeFact real")
    parser.add_argument("--numero", type=str, help="Número específico de factura")
    args = parser.parse_args()

    config = {
        "generate_pdf": True,
        "save_to_disk": True,
        "output_dir": Path("test_output") / datetime.now().strftime("%Y%m%d"),
        "use_real_nubefact": args.real,
        "simulate_nubefact_response": not args.real,
    }

    if args.real:
        print("⚠️  MODO REAL: Enviando a NubeFact real")

    runner = InvoiceTestRunner(config)
    result = runner.run_single_test(args.numero)

    if result["success"]:
        print(f"\n🎉 PRUEBA EXITOSA!")
        print(
            f"   Factura: {result['invoice_data']['serie']}-{result['invoice_data']['numero']}"
        )

        # ✅ CORRECCIÓN: Mostrar estado correcto
        sunat_status = result.get("aceptada_por_sunat")
        if sunat_status is True:
            status_display = "✅ ACEPTADA por SUNAT"
        elif sunat_status is False:
            status_display = (
                "⏳ PENDIENTE de actualización (esperando confirmación SUNAT)"
            )
        else:
            status_display = "❓ ESTADO DESCONOCIDO"

        print(f"   Estado SUNAT: {status_display}")

        if result.get("generated_files"):
            print(f"   Archivo: {result['generated_files'][0]}")

        if result.get("nubefact_response", {}).get("cadena_para_codigo_qr"):
            qr_data = result["nubefact_response"]["cadena_para_codigo_qr"]
            print(f"\n🔗 DATOS DEL QR:")
            print(f"   {qr_data[:80]}...")
    else:
        print(f"\n💀 PRUEBA FALLIDA: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
