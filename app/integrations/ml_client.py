import logging
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger("vietlangai.ml")

TEXT_TIMEOUT = 60
FILE_TIMEOUT = 180


class MlError(Exception):
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self.payload = payload
        super().__init__(payload)


class MlClient:
    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.ml_base_url
        self.api_key = settings.ml_api_key
        self.text_timeout = settings.ml_text_timeout or TEXT_TIMEOUT
        self.file_timeout = settings.ml_file_timeout or FILE_TIMEOUT

    async def translate(self, body: dict) -> dict:
        return await self._post_json("/v1/translate", body)

    async def ocr(self, filename: str, content: bytes, content_type: str) -> dict:
        return await self._post_file("/v1/ocr", filename, content, content_type)

    async def asr(self, filename: str, content: bytes, content_type: str) -> dict:
        return await self._post_file("/v1/asr", filename, content, content_type)

    async def _post_json(self, path: str, body: dict) -> dict:
        return await self._post(path, self.text_timeout, json=body)

    async def _post_file(self, path: str, filename: str, content: bytes, content_type: str) -> dict:
        files = {"file": (filename, content, content_type or "application/octet-stream")}
        return await self._post(path, self.file_timeout, files=files)

    async def _post(self, path: str, timeout: float, **kwargs) -> dict:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout, headers=headers) as client:
                response = await client.post(path, **kwargs)
        except httpx.TimeoutException as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning("ML service timeout on %s after %.1f ms", path, elapsed_ms)
            raise MlError(503, {"code": "ml_timeout", "message": "Bộ dịch phản hồi quá lâu, thử lại sau."}) from exc
        except httpx.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning("ML service unavailable on %s after %.1f ms", path, elapsed_ms)
            raise MlError(503, {"code": "ml_unavailable", "message": "Bộ dịch chưa chạy."}) from exc
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info("ML call %s completed with status %d in %.1f ms", path, response.status_code, elapsed_ms)
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
