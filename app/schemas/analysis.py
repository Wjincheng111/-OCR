from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.classification import DocumentClassification
from app.schemas.document import Document
from app.schemas.extraction import EquipmentLineItem, ExtractedField
from app.schemas.ocr import OCRDocumentResult
from app.schemas.validation import (
    BatchValidationIssue,
    ReviewRecommendation,
    ValidationIssue,
)


class AnalysisProcessingStatus(str, Enum):
    SUCCESS = "success"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class DocumentAnalysisResult(BaseModel):
    """文件 OCR、分类、字段提取、校验和复核建议的统一输出。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    document: Document
    ocr_result: OCRDocumentResult
    classification: DocumentClassification | None = None
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    equipment_items: list[EquipmentLineItem] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    review: ReviewRecommendation
    processing_status: AnalysisProcessingStatus
    processing_time_ms: int = Field(ge=0)
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> "DocumentAnalysisResult":
        if self.document != self.ocr_result.document:
            raise ValueError("顶层 document 必须与 ocr_result.document 一致")
        if self.processing_status == AnalysisProcessingStatus.FAILED and not self.error_message:
            raise ValueError("失败结果必须包含 error_message")
        if self.processing_status != AnalysisProcessingStatus.FAILED and self.error_message:
            raise ValueError("非失败结果不应包含 error_message")
        if self.processing_status == AnalysisProcessingStatus.NEEDS_REVIEW and not self.review.required:
            raise ValueError("needs_review 状态必须要求人工复核")
        if self.processing_status != AnalysisProcessingStatus.FAILED and self.classification is None:
            raise ValueError("非失败结果必须包含 classification")
        if self.processing_status == AnalysisProcessingStatus.SUCCESS and self.review.required:
            raise ValueError("success 状态不能要求人工复核")
        return self


class BatchValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_group_id: str | None = None
    documents: list[DocumentAnalysisResult] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def validate_unique_documents(self) -> "BatchValidationRequest":
        ids = [item.document.document_id for item in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("批量校验中的 document_id 不能重复")
        return self


class BatchValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_group_id: str | None = None
    checked_documents: int = Field(ge=2)
    consistent: bool
    issues: list[BatchValidationIssue] = Field(default_factory=list)


class PackageAnalysisResult(BaseModel):
    """同一项目组多份材料的分析及跨文档一致性结果。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    project_group_id: str | None = None
    documents: list[DocumentAnalysisResult] = Field(min_length=2, max_length=100)
    consistency: BatchValidationResult
    review: ReviewRecommendation
    processing_status: AnalysisProcessingStatus
    processing_time_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_consistency_count(self) -> "PackageAnalysisResult":
        if self.consistency.checked_documents != len(self.documents):
            raise ValueError("一致性校验的文档数必须与材料包文档数一致")
        if self.processing_status == AnalysisProcessingStatus.NEEDS_REVIEW and not self.review.required:
            raise ValueError("needs_review 状态必须要求人工复核")
        return self
