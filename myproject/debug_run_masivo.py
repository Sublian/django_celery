import asyncio
from unittest.mock import AsyncMock, MagicMock

from api_service.services.migo_service_async import MigoAPIServiceAsync


async def main():
    service = MigoAPIServiceAsync()
    service.cache_service = MagicMock()
    service.cache_service.get = MagicMock(return_value=None)
    service.cache_service.is_ruc_invalid = MagicMock(return_value=False)

    rucs = ["20100038146", "20123456789", "20345678901"]
    responses = []
    for i, ruc in enumerate(rucs):
        response = MagicMock()
        response.status_code = 200
        response.json = AsyncMock(
            return_value={
                "success": True,
                "ruc": ruc,
                "nombre_o_razon_social": f"EMPRESA {i+1}",
            }
        )
        responses.append(response)

    service.client = AsyncMock()
    service.client.post = AsyncMock(side_effect=responses)

    result = await service.consultar_ruc_masivo_async(rucs, batch_size=10)
    print("RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())
