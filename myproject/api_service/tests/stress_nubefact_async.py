import asyncio
import json
import time
from copy import deepcopy

from api_service.services.nubefact.nubefact_service_async import NubefactServiceAsync


async def run_stress(total: int = 50, concurrency: int = 10, delay: float = 0.0):
    base_payload = {
        "numero": "0001",
        "cliente": {"nombre": "Test"},
        # ... minimal payload; real fields should match production
    }

    semaphore = asyncio.Semaphore(concurrency)
    results = []

    async def worker(i):
        async with semaphore:
            payload = deepcopy(base_payload)
            payload["numero"] = f"{int(payload['numero']) + i:04d}"
            start = time.time()
            async with NubefactServiceAsync() as svc:
                try:
                    res = await svc.generar_comprobante(payload)
                    duration = time.time() - start
                    results.append(
                        {
                            "index": i,
                            "success": True,
                            "response": res,
                            "duration": duration,
                        }
                    )
                except Exception as e:
                    duration = time.time() - start
                    results.append(
                        {
                            "index": i,
                            "success": False,
                            "error": str(e),
                            "duration": duration,
                        }
                    )
            if delay:
                await asyncio.sleep(delay)

    tasks = [asyncio.create_task(worker(i)) for i in range(total)]
    await asyncio.gather(*tasks)

    summary = {
        "total": total,
        "successes": sum(1 for r in results if r.get("success")),
        "failures": sum(1 for r in results if not r.get("success")),
        "results": results,
    }

    with open(
        "api_service/tests/stress_results_async.json", "w", encoding="utf-8"
    ) as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(
        "Stress test finished:",
        summary["successes"],
        "successes",
        summary["failures"],
        "failures",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.0)
    args = parser.parse_args()

    asyncio.run(
        run_stress(total=args.total, concurrency=args.concurrency, delay=args.delay)
    )
