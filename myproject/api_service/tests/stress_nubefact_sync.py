# stress_nubefact_sync.py
"""
Script de estrés sincrono para NubefactService.

- Envía N requests síncronas a `generar_comprobante`.
- Incrementa `numero` por cada envío a partir de `REF_NUMBER`.
- Registra resumen (éxitos/errores) y guarda detalles en `stress_results.json`.

USO:
    python api_service/tests/stress_nubefact_sync.py --total 50 --delay 0.2

Advertencia: Este script realiza llamadas reales al servicio Nubefact.
Asegúrate de tener permisos y de estar de acuerdo con el volumen de peticiones.
"""

import os
import sys
import django
import time
import json
import argparse
from copy import deepcopy
from datetime import datetime

# Configurar Django
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from api_service.services.nubefact.nubefact_service import NubefactService
from api_service.models import ApiCallLog

# Valores por defecto
REF_NUMBER = 91431
DEFAULT_TOTAL = 50
DEFAULT_DELAY = 0.2  # segundos entre requests (para evitar golpear muy fuerte)

# JSON base (puedes adaptarlo si necesitas campos distintos)
JSON_BASE = {
    "operacion": "generar_comprobante",
    "tipo_de_comprobante": "1",
    "serie": "F001",
    "numero": REF_NUMBER,
    "cliente_tipo_de_documento": "6",
    "cliente_numero_de_documento": "20343443961",
    "cliente_denominacion": "PRUEBA STRESS S.A.C.",
    "fecha_de_emision": datetime.utcnow().strftime("%Y-%m-%d"),
    "moneda": "1",
    "total_gravada": 100.0,
    "total_igv": 18.0,
    "total": 118.0,
    "items": [
        {
            "unidad_de_medida": "ZZ",
            "codigo": "STRESS001",
            "descripcion": "Servicio de stress test",
            "cantidad": 1.0,
            "valor_unitario": 100.0,
            "precio_unitario": 118.0,
            "descuento": 0.0,
            "subtotal": 100.0,
            "tipo_de_igv": "1",
            "igv": 18.0,
            "total": 118.0,
        }
    ],
}


def run_stress(
    total: int = DEFAULT_TOTAL,
    delay: float = DEFAULT_DELAY,
    start_ref: int = REF_NUMBER,
):
    service = NubefactService()

    results = []
    successes = 0
    failures = 0

    initial_log_count = ApiCallLog.objects.filter(
        service__service_type="NUBEFACT"
    ).count()
    print(f"Initial ApiCallLog count: {initial_log_count}")

    for i in range(total):
        numero = start_ref + i
        payload = deepcopy(JSON_BASE)
        payload["numero"] = numero
        # opcional: añadir marca temporal al campo observaciones
        payload["observaciones"] = (
            f"Stress test run {datetime.utcnow().isoformat()} #{i+1}"
        )

        print(f"[{i+1}/{total}] Enviando numero={numero}...", end=" ")
        start = time.time()
        try:
            resp = service.generar_comprobante(payload)
            duration = time.time() - start

            ok = bool(resp and resp.get("success"))
            if ok:
                successes += 1
            else:
                # considerar como success cuando no hay 'success' True (depende de API)
                # aquí tratamos explicitamente
                failures += 1

            record = {
                "index": i + 1,
                "numero": numero,
                "success": resp.get("success") if isinstance(resp, dict) else False,
                "response": resp,
                "duration_s": round(duration, 3),
                "timestamp": datetime.utcnow().isoformat(),
            }

            results.append(record)
            print("OK" if ok else "FAILED", f"(t={record['duration_s']}s)")

        except Exception as e:
            duration = time.time() - start
            failures += 1
            record = {
                "index": i + 1,
                "numero": numero,
                "success": False,
                "response": str(e),
                "duration_s": round(duration, 3),
                "timestamp": datetime.utcnow().isoformat(),
            }
            results.append(record)
            print(f"EXCEPTION: {type(e).__name__}: {e}")

        # delay to avoid hammering the API too hard
        if delay and i < total - 1:
            time.sleep(delay)

    final_log_count = ApiCallLog.objects.filter(
        service__service_type="NUBEFACT"
    ).count()

    summary = {
        "start_time": datetime.utcnow().isoformat(),
        "total_sent": total,
        "successes": successes,
        "failures": failures,
        "initial_log_count": initial_log_count,
        "final_log_count": final_log_count,
        "results": results,
    }

    out_file = os.path.join(os.path.dirname(__file__), "stress_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\nStress test completed")
    print(f"  Sent: {total}, successes: {successes}, failures: {failures}")
    print(f"  ApiCallLog: {initial_log_count} -> {final_log_count}")
    print(f"  Results saved to: {out_file}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress test sync for NubefactService")
    parser.add_argument(
        "--total", type=int, default=DEFAULT_TOTAL, help="Total requests to send"
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY, help="Delay (s) between requests"
    )
    parser.add_argument(
        "--start-ref", type=int, default=REF_NUMBER, help="Starting reference number"
    )
    args = parser.parse_args()

    print(
        f"Running stress test: total={args.total}, delay={args.delay}, start_ref={args.start_ref}"
    )
    print(
        "WARNING: This will send real requests to Nubefact API using configured ApiService token."
    )

    confirm = input("Type YES to proceed: ")
    if confirm != "YES":
        print("Aborted by user")
        sys.exit(0)

    run_stress(total=args.total, delay=args.delay, start_ref=args.start_ref)
