#!/usr/bin/env python
"""
Async Stress Test - NubefactServiceAsync
Sends 50 concurrent requests to the Nubefact API.
"""
import os
import sys
import django
import json
import asyncio
import time
from datetime import datetime
from typing import List, Dict
import uuid

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
project_dir = r"C:\Users\lagonzalez\Desktop\django_fx"
sys.path.insert(0, project_dir)
os.chdir(project_dir)
django.setup()

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync


def create_payload(numero: int) -> dict:
    """Create a test payload with given invoice number"""
    return {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": "1",
        "serie": "F001",
        "numero": numero,
        "fecha_de_emision": datetime.now().strftime("%d/%m/%Y"),        
        "tipo_de_comprobante": "1",
        "serie": "F001",
        "cliente_tipo_de_documento": "6",
        "cliente_numero_de_documento": "20343443961",
        "cliente_denominacion": "PRUEBA STRESS S.A.C.",
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


async def send_single_request(
    svc: NubefactServiceAsync, numero: int, semaphore: asyncio.Semaphore
) -> Dict:
    """Send a single async request with rate limiting via semaphore"""
    async with semaphore:
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        result = {
            "request_id": request_id,
            "numero": numero,
            "status": "UNKNOWN",
            "duration_ms": 0,
            "error": None,
            "response": None,
        }

        try:
            payload = create_payload(numero)
            response = await svc.generar_comprobante(payload)
            result["status"] = "SUCCESS"
            result["response"] = {
                "enlace": response.get("enlace"),
                "codigo_hash": response.get("codigo_hash"),
            }
        except Exception as e:
            result["status"] = "FAILED"
            result["error"] = str(e)
        finally:
            result["duration_ms"] = int((time.time() - start) * 1000)

        return result


async def stress_test(num_requests: int = 50, concurrency: int = 10):
    """Run stress test with N concurrent requests"""
    print(f"\n{'='*70}")
    print(f"ASYNC STRESS TEST - NubefactServiceAsync")
    print(f"{'='*70}")
    print(f"[CONFIG] Requests: {num_requests}")
    print(f"[CONFIG] Concurrency: {concurrency}")
    print(f"[CONFIG] Starting at: {datetime.now().isoformat()}")
    print(f"{'='*70}\n")

    # Create service instance
    async with NubefactServiceAsync() as svc:
        print(f"[✓] Service initialized")
        print(f"    Base URL: {svc.base_url}")
        print(f"    Token: {svc.auth_token[:25]}...\n")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)

        # Create tasks for all requests
        tasks = []
        start_time = time.time()

        for i in range(num_requests):
            numero = 92000 + i  # Start from 92000 to avoid duplicates
            task = send_single_request(svc, numero, semaphore)
            tasks.append(task)

        # Execute all tasks concurrently
        print(f"[→] Sending {num_requests} concurrent requests...\n")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Process results
        successful = 0
        failed = 0
        errors = {}
        durations = []

        print(f"{'STATUS':<10} {'NUMERO':<8} {'DURATION':<12} {'RESULT':<40}")
        print(f"{'-'*70}")

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"ERROR     {i:<7}  Exception: {str(result)[:35]}")
                failed += 1
                continue

            status = result["status"]
            numero = result["numero"]
            duration = result["duration_ms"]

            if status == "SUCCESS":
                successful += 1
                durations.append(duration)
                hash_short = (
                    result["response"]["codigo_hash"][:20]
                    if result["response"]
                    else "???"
                )
                print(
                    f"{status:<10} {numero:<8} {duration:>6}ms        ✓ {hash_short}..."
                )
            else:
                failed += 1
                error_short = (
                    (result["error"][:35] + "...")
                    if len(result["error"]) > 35
                    else result["error"]
                )
                print(
                    f"{status:<10} {numero:<8} {duration:>6}ms        ✗ {error_short}"
                )
                errors[result["error"]] = errors.get(result["error"], 0) + 1

            # Print progress every 10 requests
            if (i + 1) % 10 == 0:
                print(f"  ... {i+1}/{num_requests} completed")

        # Print summary
        print(f"\n{'='*70}")
        print("STRESS TEST SUMMARY")
        print(f"{'='*70}")
        print(f"[✓] Successful: {successful}/{num_requests}")
        print(f"[✗] Failed:     {failed}/{num_requests}")
        print(f"[⏱] Total time: {total_time:.2f}s")
        print(f"[⏱] Requests/sec: {num_requests/total_time:.2f}")

        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            print(f"\n[TIMING]")
            print(f"  Average: {avg_duration:.0f}ms")
            print(f"  Min:     {min_duration:.0f}ms")
            print(f"  Max:     {max_duration:.0f}ms")

        if errors:
            print(f"\n[ERROR BREAKDOWN]")
            for error, count in sorted(
                errors.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"  {count:>3}x {error[:60]}")

        # Save results to file
        results_file = (
            f"stress_results_async_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(results_file, "w") as f:
            json.dump(
                {
                    "config": {
                        "num_requests": num_requests,
                        "concurrency": concurrency,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "summary": {
                        "successful": successful,
                        "failed": failed,
                        "total_time_seconds": total_time,
                        "requests_per_second": num_requests / total_time,
                        "avg_duration_ms": avg_duration if durations else None,
                        "min_duration_ms": min_duration if durations else None,
                        "max_duration_ms": max_duration if durations else None,
                    },
                    "results": [r for r in results if not isinstance(r, Exception)],
                },
                f,
                indent=2,
            )

        print(f"\n[✓] Results saved to: {results_file}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(stress_test(num_requests=50, concurrency=10))
