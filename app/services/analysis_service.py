import logging
import time
from collections.abc import Sequence

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import InvalidUploadError, PackageTooLargeError
from app.extraction import DocumentClassifier, EquipmentTableExtractor, RuleBasedExtractor
from app.schemas.analysis import (
    AnalysisProcessingStatus,
    BatchValidationRequest,
    DocumentAnalysisResult,
    PackageAnalysisResult,
)
from app.schemas.ocr import OCRDocumentResult, ProcessingStatus
from app.schemas.validation import ReviewPriority, ReviewRecommendation
from app.services.document_service import DocumentService
from app.utils.result_writer import save_result
from app.validation import BatchConsistencyValidator, DocumentDataValidator


logger = logging.getLogger(__name__)


class AnalysisService:
    """编排 OCR、分类、字段提取、数据校验和人工复核判断。"""

    def __init__(
        self,
        settings: Settings,
        *,
        document_service: DocumentService | None = None,
        classifier: DocumentClassifier | None = None,
        extractor: RuleBasedExtractor | None = None,
        equipment_extractor: EquipmentTableExtractor | None = None,
        validator: DocumentDataValidator | None = None,
        consistency_validator: BatchConsistencyValidator | None = None,
    ) -> None:
        self.settings = settings
        self.document_service = document_service or DocumentService(settings=settings)
        self.classifier = classifier or DocumentClassifier()
        self.extractor = extractor or RuleBasedExtractor()
        self.equipment_extractor = equipment_extractor or EquipmentTableExtractor()
        self.validator = validator or DocumentDataValidator(
            classification_threshold=settings.classification_review_threshold,
            field_confidence_threshold=settings.field_confidence_review_threshold,
            ocr_confidence_threshold=settings.ocr_confidence_review_threshold,
        )
        self.consistency_validator = consistency_validator or BatchConsistencyValidator()

    async def analyze_upload(self, upload: UploadFile) -> DocumentAnalysisResult:
        ocr_result = await self.document_service.process_upload(upload)
        return self.analyze_ocr(ocr_result)

    def analyze_ocr(self, ocr_result: OCRDocumentResult) -> DocumentAnalysisResult:
        started_at = time.perf_counter()
        if ocr_result.processing_status == ProcessingStatus.FAILED:
            result = DocumentAnalysisResult(
                document=ocr_result.document,
                ocr_result=ocr_result,
                review=ReviewRecommendation(
                    required=True,
                    priority=ReviewPriority.HIGH,
                    reasons=["ocr_failed"],
                ),
                processing_status=AnalysisProcessingStatus.FAILED,
                processing_time_ms=ocr_result.processing_time_ms,
                error_message=ocr_result.error_message or "OCR 处理失败。",
            )
            self._optionally_save(result)
            return result

        classification = self.classifier.classify(ocr_result)
        fields = self.extractor.extract(ocr_result, classification)
        equipment_items = self.equipment_extractor.extract(ocr_result, classification)
        issues = self.validator.validate(
            ocr_result, classification, fields, equipment_items
        )
        review = self.validator.build_review(issues)
        analysis_elapsed = self._elapsed_ms(started_at)
        result = DocumentAnalysisResult(
            document=ocr_result.document,
            ocr_result=ocr_result,
            classification=classification,
            extracted_fields=fields,
            equipment_items=equipment_items,
            validation_issues=issues,
            review=review,
            processing_status=(
                AnalysisProcessingStatus.NEEDS_REVIEW
                if review.required
                else AnalysisProcessingStatus.SUCCESS
            ),
            processing_time_ms=ocr_result.processing_time_ms + analysis_elapsed,
        )
        self._optionally_save(result)
        return result

    async def analyze_package(
        self,
        uploads: Sequence[UploadFile],
        *,
        project_group_id: str | None = None,
    ) -> PackageAnalysisResult:
        started_at = time.perf_counter()
        if not 2 <= len(uploads) <= self.settings.max_package_files:
            raise InvalidUploadError(
                f"每个材料包必须包含 2 至 {self.settings.max_package_files} 个文件。",
                code="invalid_package_file_count",
            )

        analyses: list[DocumentAnalysisResult] = []
        total_size = 0
        for upload in uploads:
            analysis = await self.analyze_upload(upload)
            analyses.append(analysis)
            total_size += analysis.document.file_size
            if total_size > self.settings.max_package_size_bytes:
                raise PackageTooLargeError(self.settings.max_package_size_mb)

        consistency = self.consistency_validator.validate(
            BatchValidationRequest(
                project_group_id=project_group_id,
                documents=analyses,
            )
        )
        document_review_reasons = [
            reason
            for item in analyses
            for reason in item.review.reasons
            if item.review.required
        ]
        consistency_reasons = [issue.code for issue in consistency.issues]
        reasons = list(dict.fromkeys(document_review_reasons + consistency_reasons))
        has_error = any(
            item.processing_status == AnalysisProcessingStatus.FAILED for item in analyses
        )
        review = ReviewRecommendation(
            required=bool(reasons),
            priority=(
                ReviewPriority.HIGH
                if has_error
                else ReviewPriority.MEDIUM
                if reasons
                else ReviewPriority.LOW
            ),
            reasons=reasons,
        )
        return PackageAnalysisResult(
            project_group_id=project_group_id,
            documents=analyses,
            consistency=consistency,
            review=review,
            processing_status=(
                AnalysisProcessingStatus.NEEDS_REVIEW
                if review.required
                else AnalysisProcessingStatus.SUCCESS
            ),
            processing_time_ms=self._elapsed_ms(started_at),
        )

    def validate_batch(self, request: BatchValidationRequest):
        return self.consistency_validator.validate(request)

    def _optionally_save(self, result: DocumentAnalysisResult) -> None:
        if not self.settings.save_results:
            return
        try:
            save_result(
                result,
                self.settings.resolved_output_dir,
                filename="analysis.json",
            )
        except OSError:
            logger.exception(
                "分析结果保存失败 document_id=%s", result.document.document_id
            )

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((time.perf_counter() - started_at) * 1000))
