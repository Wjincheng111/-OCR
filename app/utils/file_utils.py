from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.errors import FileTooLargeError, InvalidUploadError, UnsupportedFileTypeError


ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/octet-stream",
}
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class UploadMetadata:
    original_filename: str
    file_type: str


def validate_upload_metadata(upload: UploadFile) -> UploadMetadata:
    raw_name = (upload.filename or "").replace("\\", "/")
    safe_name = PurePosixPath(raw_name).name
    if not safe_name or safe_name in {".", ".."}:
        raise InvalidUploadError("文件名不能为空。")

    suffix = Path(safe_name).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError()

    content_type = (upload.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedFileTypeError("上传文件的媒体类型不受支持。")

    return UploadMetadata(original_filename=safe_name, file_type=suffix)


async def save_upload_to_temp(
    upload: UploadFile,
    destination: Path,
    *,
    file_type: str,
    max_size_bytes: int,
    max_size_mb: int,
) -> int:
    """分块保存上传文件，限制大小并验证文件头；destination 由服务端生成。"""

    size = 0
    first_bytes = b""
    try:
        with destination.open("wb") as target:
            while chunk := await upload.read(CHUNK_SIZE):
                if not first_bytes:
                    first_bytes = chunk[:16]
                size += len(chunk)
                if size > max_size_bytes:
                    raise FileTooLargeError(max_size_mb)
                target.write(chunk)
    finally:
        await upload.close()

    if size == 0:
        raise InvalidUploadError("上传文件为空。", code="empty_file")
    if not _signature_matches(first_bytes, file_type):
        raise InvalidUploadError(
            "文件内容与扩展名不一致，或文件已经损坏。",
            code="invalid_file_signature",
        )
    return size


def _signature_matches(header: bytes, file_type: str) -> bool:
    if file_type == "pdf":
        return header.startswith(b"%PDF-")
    if file_type in {"jpg", "jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if file_type == "png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    return False

