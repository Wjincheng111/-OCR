class AppError(Exception):
    """可以安全返回给调用方的应用异常。"""

    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidUploadError(AppError):
    def __init__(self, message: str, *, code: str = "invalid_upload") -> None:
        super().__init__(message, code=code, status_code=400)


class UnsupportedFileTypeError(AppError):
    def __init__(self, message: str = "仅支持 PDF、JPG、JPEG 和 PNG 文件。") -> None:
        super().__init__(message, code="unsupported_file_type", status_code=415)


class FileTooLargeError(AppError):
    def __init__(self, max_size_mb: int) -> None:
        super().__init__(
            f"文件过大，最大允许 {max_size_mb} MB。",
            code="file_too_large",
            status_code=413,
        )


class PackageTooLargeError(AppError):
    def __init__(self, max_size_mb: int) -> None:
        super().__init__(
            f"材料包总大小不能超过 {max_size_mb} MB。",
            code="package_too_large",
            status_code=413,
        )


class DocumentProcessingError(Exception):
    """已接收文件，但无法继续处理时使用的内部异常。"""


class OCREngineError(Exception):
    """OCR 引擎初始化或识别失败。"""
