import httpx

from app.core.config import get_settings

TEXT_TIMEOUT = 60
FILE_TIMEOUT = 180


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
        return await self._post(path, TEXT_TIMEOUT, json=body)

    async def _post_file(self, path: str, filename: str, content: bytes, content_type: str) -> dict:
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        return await self._post(path, FILE_TIMEOUT, files=files)

    async def _post(self, path: str, timeout: float, **kwargs) -> dict:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
                response = await client.post(path, **kwargs)
        except httpx.TimeoutException as exc:
            raise MlError(503, {"code": "ml_timeout", "message": "Bộ dịch phản hồi quá lâu, thử lại sau."}) from exc
        except httpx.HTTPError as exc:
            raise MlError(503, {"code": "ml_unavailable", "message": "Bộ dịch chưa chạy."}) from exc
        return self._read(response)

    def _read(self, response: httpx.Response) -> dict:
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            raise MlError(503, {"code": "ml_error", "message": "Bộ dịch trả về dữ liệu không đọc được."}) from None
        if response.status_code >= 400:
            detail = payload.get("detail", payload)
            if not isinstance(detail, dict):
                detail = {"code": "ml_error", "message": str(detail)}
            raise MlError(response.status_code, detail)
        return payload


def get_ml_client() -> MlClient:
    return MlClient()
