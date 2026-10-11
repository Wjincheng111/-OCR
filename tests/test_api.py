from io import BytesIO

import numpy as np
import pymupdf
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import get_document_service
from app.core.config import Settings
from app.main import app
from app.ocr.base import BaseOCREngine
from app.schemas.ocr import OCRTextBlock
from app.services.document_service import DocumentService


class StubOCREngine(BaseOCREngine):
    def recognize(self, image: np.ndarray, page_number: int) -> list[OCRTextBlock]:
        height, width = image.shape[:2]
        return [
            OCRTextBlock(
                text=f"测试文本-{page_number}",
                confidence=0.99,
                bounding_box=[
                    [0, 0],
                    [width, 0],
                    [width, height],
                    [0, height],
                ],
                page_number=page_number,
            )
        ]


def _test_service() -> DocumentService:
    settings = Settings(
        max_file_size_mb=1,
        max_pdf_pages=5,
        pdf_dpi=72,
        save_results=False,
    )
    return DocumentService(settings=settings, engine=StubOCREngine())


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 12), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    document = pymupdf.open()
    document.new_page(width=100, height=80)
    content = document.tobytes()
    document.close()
    return content


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_exposes_ocr_route() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "post" in schema["paths"]["/api/v1/ocr"]


def test_unsupported_file_type_is_rejected_before_ocr_initialization() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            files={"file": ("notes.txt", b"not an image", "text/plain")},
        )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_empty_file_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            files={"file": ("empty.png", b"", "image/png")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_mismatched_file_signature_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            files={"file": ("fake.png", b"not a png", "image/png")},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_file_signature"


def test_corrupt_image_returns_failed_result_without_crashing() -> None:
    app.dependency_overrides[get_document_service] = _test_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ocr",
                files={
                    "file": (
                        "corrupt.png",
                        b"\x89PNG\r\n\x1a\ncorrupt-data",
                        "image/png",
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["processing_status"] == "failed"
    assert response.json()["error_message"]


def test_oversized_file_is_rejected() -> None:
    app.dependency_overrides[get_document_service] = _test_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ocr",
                files={
                    "file": (
                        "large.png",
                        b"\x89PNG\r\n\x1a\n" + (b"0" * (1024 * 1024 + 1)),
                        "image/png",
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_image_ocr_flow_with_mock_engine() -> None:
    app.dependency_overrides[get_document_service] = _test_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ocr",
                files={"file": ("sample.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["processing_status"] == "success"
    assert payload["document"]["total_pages"] == 1
    assert payload["pages"][0]["text_blocks"][0]["confidence"] == 0.99
    assert len(payload["pages"][0]["text_blocks"][0]["bounding_box"]) == 4


def test_pdf_is_processed_page_by_page_with_mock_engine() -> None:
    app.dependency_overrides[get_document_service] = _test_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ocr",
                files={"file": ("sample.pdf", _pdf_bytes(), "application/pdf")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["total_pages"] == 1
    assert payload["pages"][0]["page_number"] == 1
    assert payload["pages"][0]["text_blocks"][0]["page_number"] == 1


def test_unexpected_service_error_returns_safe_json() -> None:
    class CrashingService:
        async def process_upload(self, _file: object) -> None:
            raise RuntimeError("private internal detail")

    app.dependency_overrides[get_document_service] = lambda: CrashingService()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/ocr",
                files={"file": ("sample.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "服务器内部错误，请稍后重试。",
        }
    }
