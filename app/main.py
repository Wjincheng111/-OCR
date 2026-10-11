import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging_config import configure_logging
from app.core.middleware import UploadBodyLimitMiddleware


settings = get_settings()
configure_logging(settings.debug)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "分布式光伏材料的文件预处理、OCR、文档分类、字段提取、"
        "数据标准化、一致性校验与人工复核提示。"
    ),
)
app.add_middleware(
    UploadBodyLimitMiddleware,
    # multipart 边界和字段需要少量额外空间；文件本体仍由服务层精确计数。
    single_file_limit_bytes=settings.max_file_size_bytes + 1024 * 1024,
    package_limit_bytes=settings.max_package_size_bytes + 2 * 1024 * 1024,
    json_limit_bytes=settings.max_json_body_bytes,
)
app.include_router(router)


@app.exception_handler(AppError)
async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理的服务器异常", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "服务器内部错误，请稍后重试。",
            }
        },
    )
