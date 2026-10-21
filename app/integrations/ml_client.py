import httpx

from app.core.config import get_settings


class MlError(Exception):
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self.payload = payload
        super().__init__(payload)


class MlClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or get_settings().ml_base_url

    async def translate(self, body: dict) -> dict:
        return await self._post_json("/v1/translate", body)

    async def ocr(self, filename: str, content: bytes, content_type: str) -> dict:
        return await self._post_file("/v1/ocr", filename, content, content_type)

    async def asr(self, filename: str, content: bytes, content_type: str) -> dict:
        return await self._post_file("/v1/asr", filename, content, content_type)

    async def _post_json(self, path: str, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=60) as client:
                response = await client.post(path, json=body)
        except httpx.HTTPError as exc:
            raise MlError(503, {"code": "ml_unavailable", "message": "Bộ dịch chưa chạy."}) from exc
        return self._read(response)

    async def _post_file(self, path: str, filename: str, content: bytes, content_type: str) -> dict:
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=60) as client:
                response = await client.post(path, files=files)
        except httpx.HTTPError as exc:
            raise MlError(503, {"code": "ml_unavailable", "message": "Bộ dịch chưa chạy."}) from exc
        return self._read(response)

    def _read(self, response: httpx.Response) -> dict:
        payload = response.json() if response.content else {}
        if response.status_code >= 400:
            detail = payload.get("detail", payload)
            if not isinstance(detail, dict):
                detail = {"code": "ml_error", "message": str(detail)}
            raise MlError(response.status_code, detail)
        return payload


def get_ml_client() -> MlClient:
    return MlClient()
