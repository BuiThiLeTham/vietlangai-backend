import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("vietlangai.error")


class AppError(HTTPException):
    """Standardized domain exception carrying an error code and localized message."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if not isinstance(detail, dict):
            detail = {"code": "http_error", "message": str(detail)}
        elif "code" not in detail:
            detail = {"code": "http_error", "message": detail.get("message", "Yêu cầu không hợp lệ."), **detail}
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "loc": [str(part) for part in err.get("loc", [])],
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "Dữ liệu đầu vào không hợp lệ.",
                    "errors": errors,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": "Đã xảy ra lỗi hệ thống, vui lòng thử lại sau.",
                }
            },
        )

