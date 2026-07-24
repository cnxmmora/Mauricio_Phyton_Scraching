from curl_cffi.requests import AsyncSession
from curl_cffi.requests.models import Response


class CurlHttpClient:
    @staticmethod
    async def fetch(url: str) -> str:
        async with AsyncSession() as requests:
            response: Response = await requests.get(url=url, impersonate="chrome")
            response.raise_for_status()

            return response.text
