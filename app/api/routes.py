from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.config import get_settings
from app.schemas.analysis import (
    BatchValidationRequest,
    BatchValidationResult,
    DocumentAnalysisResult,
    PackageAnalysisResult,
)
from app.schemas.classification import DocumentType
from app.schemas.ocr import OCRDocumentResult
from app.services.analysis_service import AnalysisService
from app.services.document_service import DocumentService


router = APIRouter()


def get_document_service() -> DocumentService:
    # PaddleOCR 延迟到文件通过校验且真正需要识别时才初始化。
    return DocumentService(settings=get_settings())


def get_analysis_service() -> AnalysisService:
    return AnalysisService(settings=get_settings())


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/api/v1/ocr",
    response_model=OCRDocumentResult,
    tags=["ocr"],
    summary="上传文件并执行 OCR",
)
async def run_ocr(
    file: Annotated[UploadFile, File(description="PDF、JPG、JPEG 或 PNG 文件")],
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> OCRDocumentResult:
    return await service.process_upload(file)


@router.post(
    "/api/v1/analyze",
    response_model=DocumentAnalysisResult,
    tags=["analysis"],
    summary="上传单个文件并完成 OCR、分类、字段提取与数据校验",
)
async def analyze_document(
    file: Annotated[UploadFile, File(description="PDF、JPG、JPEG 或 PNG 文件")],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> DocumentAnalysisResult:
    return await service.analyze_upload(file)


@router.post(
    "/api/v1/analyze/from-ocr",
    response_model=DocumentAnalysisResult,
    tags=["analysis"],
    summary="从已有 OCR JSON 重新执行分类、提取与校验",
)
def analyze_from_ocr(
    ocr_result: OCRDocumentResult,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> DocumentAnalysisResult:
    return service.analyze_ocr(ocr_result)


@router.post(
    "/api/v1/analyze-package",
    response_model=PackageAnalysisResult,
    tags=["analysis"],
    summary="分析同一项目的一组文件并执行跨文档一致性校验",
)
async def analyze_package(
    files: Annotated[
        list[UploadFile], File(description="同一项目的 2 个或更多 PDF/图片文件")
    ],
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
    project_group_id: Annotated[str | None, Form()] = None,
) -> PackageAnalysisResult:
    return await service.analyze_package(files, project_group_id=project_group_id)


@router.post(
    "/api/v1/validate/batch",
    response_model=BatchValidationResult,
    tags=["validation"],
    summary="校验多份已有分析 JSON 的关键字段一致性",
)
def validate_batch(
    request: BatchValidationRequest,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> BatchValidationResult:
    return service.validate_batch(request)


@router.get(
    "/api/v1/document-types",
    tags=["analysis"],
    summary="列出支持的文档分类",
)
def list_document_types() -> dict[str, list[str]]:
    return {"document_types": [item.value for item in DocumentType]}
