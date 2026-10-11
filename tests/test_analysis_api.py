from io import BytesIO

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.api.routes import get_analysis_service
from app.core.config import Settings
from app.main import app
from app.ocr.base import BaseOCREngine
from app.schemas.ocr import OCRTextBlock
from app.services.analysis_service import AnalysisService
from app.services.document_service import DocumentService
from tests.helpers import make_ocr_result


class ProjectOCREngine(BaseOCREngine):
    def recognize(self, _image: np.ndarray, page_number: int) -> list[OCRTextBlock]:
        texts = [
            "项目基本资料",
            "项目名称：甲屋顶光伏项目",
            "项目地点：江苏省某市",
            "建设单位：甲能源有限公司",
            "装机容量：1MW",
        ]
        return [
            OCRTextBlock(
                text=text,
                confidence=0.99,
                bounding_box=[[5, 5 + i * 20], [250, 5 + i * 20], [250, 20 + i * 20], [5, 20 + i * 20]],
                page_number=page_number,
            )
            for i, text in enumerate(texts)
        ]


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (300, 150), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _analysis_service() -> AnalysisService:
    settings = Settings(
        max_file_size_mb=1,
        max_package_files=4,
        max_package_size_mb=4,
        pdf_dpi=72,
        save_results=False,
    )
    document_service = DocumentService(settings=settings, engine=ProjectOCREngine())
    return AnalysisService(settings=settings, document_service=document_service)


def test_openapi_exposes_complete_analysis_routes() -> None:
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/analyze",
        "/api/v1/analyze/from-ocr",
        "/api/v1/analyze-package",
        "/api/v1/validate/batch",
        "/api/v1/document-types",
    ):
        assert path in paths


def test_analyze_from_ocr_api() -> None:
    payload = make_ocr_result(
        [[
            "组件技术资料",
            "制造商：隆基绿能科技股份有限公司",
            "组件型号：LR5-72HTH-585M",
            "最大功率：585W",
        ]],
        filename="组件技术资料.pdf",
    ).model_dump(mode="json")
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze/from-ocr", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["document_type"] == "pv_module_datasheet"
    assert any(field["field_name"] == "model" for field in body["extracted_fields"])


def test_single_upload_analysis_api() -> None:
    app.dependency_overrides[get_analysis_service] = _analysis_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyze",
                files={"file": ("项目基本资料.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["document_type"] == "project_basic_info"
    assert body["processing_status"] == "success"


def test_package_upload_analyzes_and_checks_documents() -> None:
    app.dependency_overrides[get_analysis_service] = _analysis_service
    files = [
        ("files", ("项目资料1.png", _png_bytes(), "image/png")),
        ("files", ("项目资料2.png", _png_bytes(), "image/png")),
    ]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyze-package",
                files=files,
                data={"project_group_id": "case-001"},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert len(body["documents"]) == 2
    assert body["consistency"]["consistent"] is True
    assert body["project_group_id"] == "case-001"


def test_package_requires_at_least_two_files() -> None:
    app.dependency_overrides[get_analysis_service] = _analysis_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyze-package",
                files=[("files", ("only.png", _png_bytes(), "image/png"))],
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_package_file_count"


def test_upload_body_is_rejected_before_multipart_parsing() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ocr",
            content=b"small-body",
            headers={
                "content-type": "multipart/form-data; boundary=x",
                "content-length": str(30 * 1024 * 1024),
            },
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_body_too_large"
