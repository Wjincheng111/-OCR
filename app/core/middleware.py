from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse


ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]
ASGISend = Callable[[dict[str, Any]], Awaitable[None]]


class _RequestBodyTooLarge(Exception):
    pass


class UploadBodyLimitMiddleware:
    """在 multipart 解析前限制上传请求体，避免超大请求先写满临时目录。"""

    def __init__(
        self,
        app: Any,
        *,
        single_file_limit_bytes: int,
        package_limit_bytes: int,
        json_limit_bytes: int,
    ) -> None:
        self.app = app
        self.single_file_limit_bytes = single_file_limit_bytes
        self.package_limit_bytes = package_limit_bytes
        self.json_limit_bytes = json_limit_bytes

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        limit = self._limit_for(scope)
        if limit is None:
            await self.app(scope, receive, send)
            return

        content_length = self._content_length(scope)
        if content_length is not None and content_length > limit:
            await self._reject(scope, receive, send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, send)

    def _limit_for(self, scope: dict[str, Any]) -> int | None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            return None
        path = scope.get("path", "")
        if path == "/api/v1/analyze-package":
            return self.package_limit_bytes
        if path in {"/api/v1/ocr", "/api/v1/analyze"}:
            return self.single_file_limit_bytes
        if path in {"/api/v1/analyze/from-ocr", "/api/v1/validate/batch"}:
            return self.json_limit_bytes
        return None

    @staticmethod
    def _content_length(scope: dict[str, Any]) -> int | None:
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    @staticmethod
    async def _reject(
        scope: dict[str, Any], receive: ASGIReceive, send: ASGISend
    ) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "request_body_too_large",
                    "message": "上传请求体超过允许大小。",
                }
            },
        )
        await response(scope, receive, send)
