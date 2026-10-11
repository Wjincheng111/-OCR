from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from app.extraction.catalog import FIELD_DISPLAY_NAMES, REQUIRED_FIELDS
from app.schemas.classification import (
    ClassificationStatus,
    DocumentClassification,
    DocumentType,
)
from app.schemas.extraction import EquipmentLineItem, ExtractedField
from app.schemas.ocr import OCRDocumentResult
from app.schemas.validation import (
    ReviewPriority,
    ReviewRecommendation,
    ValidationIssue,
    ValidationSeverity,
)


SINGLE_VALUE_FIELDS = {
    "project_name",
    "project_location",
    "project_capacity_kw",
    "applicant_name",
    "insured_name",
    "contract_number",
    "contract_amount_cny",
    "contract_date",
    "inspection_conclusion",
    "acceptance_conclusion",
    "acceptance_date",
    "risk_location",
    "insurance_amount_cny",
    "insurance_period_start",
    "insurance_period_end",
    "document_number",
    "report_number",
    "testing_body",
    "inspection_date",
}


class DocumentDataValidator:
    """只检查数据质量和一致性，不产生任何核保结论。"""

    def __init__(
        self,
        *,
        classification_threshold: float = 0.55,
        field_confidence_threshold: float = 0.70,
        ocr_confidence_threshold: float = 0.75,
    ) -> None:
        self.classification_threshold = classification_threshold
        self.field_confidence_threshold = field_confidence_threshold
        self.ocr_confidence_threshold = ocr_confidence_threshold

    def validate(
        self,
        ocr_result: OCRDocumentResult,
        classification: DocumentClassification,
        fields: list[ExtractedField],
        equipment_items: list[EquipmentLineItem] | None = None,
    ) -> list[ValidationIssue]:
        equipment_items = equipment_items or []
        issues: list[ValidationIssue] = []
        issues.extend(self._validate_ocr_confidence(ocr_result))
        issues.extend(self._validate_classification(classification))
        issues.extend(self._validate_required_fields(classification.document_type, fields))
        issues.extend(self._validate_field_confidence(fields))
        issues.extend(self._validate_conflicts(fields))
        issues.extend(self._validate_positive_numbers(fields))
        issues.extend(self._validate_date_order(fields))
        issues.extend(self._validate_capacity_arithmetic(fields))
        issues.extend(
            self._validate_equipment_items(
                classification.document_type, equipment_items
            )
        )
        return issues

    @staticmethod
    def build_review(issues: list[ValidationIssue]) -> ReviewRecommendation:
        actionable = [
            issue
            for issue in issues
            if issue.severity in {ValidationSeverity.WARNING, ValidationSeverity.ERROR}
        ]
        if not actionable:
            return ReviewRecommendation(required=False, priority=ReviewPriority.LOW, reasons=[])
        priority = (
            ReviewPriority.HIGH
            if any(issue.severity == ValidationSeverity.ERROR for issue in actionable)
            else ReviewPriority.MEDIUM
        )
        reasons = list(dict.fromkeys(issue.code for issue in actionable))
        return ReviewRecommendation(required=True, priority=priority, reasons=reasons)

    def _validate_ocr_confidence(self, ocr_result: OCRDocumentResult) -> list[ValidationIssue]:
        confidences = [
            block.confidence for page in ocr_result.pages for block in page.text_blocks
        ]
        if not confidences:
            return []
        average = sum(confidences) / len(confidences)
        if average >= self.ocr_confidence_threshold:
            return []
        return [
            ValidationIssue(
                code="low_ocr_confidence",
                severity=ValidationSeverity.WARNING,
                message=f"OCR 平均置信度为 {average:.2f}，建议人工核对原件。",
            )
        ]

    def _validate_classification(
        self, classification: DocumentClassification
    ) -> list[ValidationIssue]:
        if classification.document_type == DocumentType.OTHER:
            return [
                ValidationIssue(
                    code="classification_unresolved",
                    severity=ValidationSeverity.WARNING,
                    message="未能确定文档类型，需要人工分类。",
                )
            ]
        issues: list[ValidationIssue] = []
        if classification.status == ClassificationStatus.AMBIGUOUS:
            issues.append(
                ValidationIssue(
                    code="classification_ambiguous",
                    severity=ValidationSeverity.WARNING,
                    message="多个文档类型得分接近，需要人工确认分类。",
                )
            )
        if classification.mixed_document:
            issues.append(
                ValidationIssue(
                    code="mixed_document_suspected",
                    severity=ValidationSeverity.WARNING,
                    message="不同页面可能属于不同材料类型，建议拆分或人工确认。",
                )
            )
        if classification.confidence < self.classification_threshold:
            issues.append(
                ValidationIssue(
                    code="classification_low_confidence",
                    severity=ValidationSeverity.WARNING,
                    message=f"文档分类置信度为 {classification.confidence:.2f}，建议人工确认。",
                )
            )
        return issues

    @staticmethod
    def _validate_required_fields(
        document_type: DocumentType, fields: list[ExtractedField]
    ) -> list[ValidationIssue]:
        required = REQUIRED_FIELDS.get(document_type, ())
        present = {field.field_name for field in fields}
        return [
            ValidationIssue(
                code="required_field_missing",
                severity=ValidationSeverity.WARNING,
                message=f"缺少建议复核的字段：{FIELD_DISPLAY_NAMES.get(name, name)}。",
                field_names=[name],
            )
            for name in required
            if name not in present
        ]

    def _validate_field_confidence(
        self, fields: list[ExtractedField]
    ) -> list[ValidationIssue]:
        low_fields = sorted(
            {
                field.field_name
                for field in fields
                if field.confidence < self.field_confidence_threshold
            }
        )
        if not low_fields:
            return []
        names = "、".join(FIELD_DISPLAY_NAMES.get(name, name) for name in low_fields)
        return [
            ValidationIssue(
                code="low_extraction_confidence",
                severity=ValidationSeverity.WARNING,
                message=f"以下字段提取置信度较低：{names}。",
                field_names=low_fields,
            )
        ]

    @staticmethod
    def _validate_conflicts(fields: list[ExtractedField]) -> list[ValidationIssue]:
        grouped: dict[str, set[str]] = defaultdict(set)
        for field in fields:
            if field.field_name in SINGLE_VALUE_FIELDS:
                grouped[field.field_name].add(str(field.normalized_value).strip().casefold())
        issues: list[ValidationIssue] = []
        for name, values in grouped.items():
            if len(values) > 1:
                issues.append(
                    ValidationIssue(
                        code="intra_document_conflict",
                        severity=ValidationSeverity.WARNING,
                        message=f"同一文档内“{FIELD_DISPLAY_NAMES.get(name, name)}”出现多个不同值。",
                        field_names=[name],
                    )
                )
        return issues

    @staticmethod
    def _validate_positive_numbers(fields: list[ExtractedField]) -> list[ValidationIssue]:
        numeric_names = {
            "project_capacity_kw",
            "rated_power_w",
            "module_count",
            "inverter_count",
            "quantity",
            "contract_amount_cny",
            "insurance_amount_cny",
        }
        issues: list[ValidationIssue] = []
        for field in fields:
            if field.field_name not in numeric_names:
                continue
            try:
                value = Decimal(str(field.normalized_value))
            except InvalidOperation:
                continue
            if value <= 0:
                issues.append(
                    ValidationIssue(
                        code="invalid_non_positive_value",
                        severity=ValidationSeverity.ERROR,
                        message=f"字段“{field.display_name}”应为正数。",
                        field_names=[field.field_name],
                    )
                )
        return issues

    @staticmethod
    def _validate_date_order(fields: list[ExtractedField]) -> list[ValidationIssue]:
        best = DocumentDataValidator._best_fields(fields)
        start = best.get("insurance_period_start")
        end = best.get("insurance_period_end")
        if start is None or end is None:
            return []
        try:
            start_date = date.fromisoformat(str(start.normalized_value))
            end_date = date.fromisoformat(str(end.normalized_value))
        except ValueError:
            return []
        if start_date <= end_date:
            return []
        return [
            ValidationIssue(
                code="invalid_date_range",
                severity=ValidationSeverity.ERROR,
                message="保险期间的开始日期晚于结束日期。",
                field_names=["insurance_period_start", "insurance_period_end"],
            )
        ]

    @staticmethod
    def _validate_capacity_arithmetic(fields: list[ExtractedField]) -> list[ValidationIssue]:
        best = DocumentDataValidator._best_fields(fields)
        required = {"module_count", "rated_power_w", "project_capacity_kw"}
        if not required.issubset(best):
            return []
        try:
            calculated_kw = (
                Decimal(str(best["module_count"].normalized_value))
                * Decimal(str(best["rated_power_w"].normalized_value))
                / Decimal("1000")
            )
            stated_kw = Decimal(str(best["project_capacity_kw"].normalized_value))
        except InvalidOperation:
            return []
        tolerance = max(Decimal("0.1"), abs(stated_kw) * Decimal("0.001"))
        if abs(calculated_kw - stated_kw) <= tolerance:
            return []
        return [
            ValidationIssue(
                code="arithmetic_mismatch",
                severity=ValidationSeverity.WARNING,
                message=(
                    f"组件数量×单块功率约为 {calculated_kw} kW，"
                    f"与文档容量 {stated_kw} kW 不一致。"
                ),
                field_names=["module_count", "rated_power_w", "project_capacity_kw"],
            )
        ]

    def _validate_equipment_items(
        self,
        document_type: DocumentType,
        items: list[EquipmentLineItem],
    ) -> list[ValidationIssue]:
        if document_type != DocumentType.EQUIPMENT_LIST:
            return []
        if not items:
            return [
                ValidationIssue(
                    code="table_structure_uncertain",
                    severity=ValidationSeverity.WARNING,
                    message="识别到设备清单，但没有可靠提取出设备行。",
                )
            ]

        issues: list[ValidationIssue] = []
        for item in items:
            missing = [
                name
                for name in ("equipment_type", "model", "quantity")
                if getattr(item, name) is None
            ]
            if missing:
                issues.append(
                    ValidationIssue(
                        code="required_line_item_field_missing",
                        severity=ValidationSeverity.WARNING,
                        message=f"设备清单第 {item.item_index} 行缺少类型、型号或数量字段。",
                        field_names=[f"equipment_items[{item.item_index}].{name}" for name in missing],
                    )
                )
            if item.confidence < self.field_confidence_threshold:
                issues.append(
                    ValidationIssue(
                        code="low_extraction_confidence",
                        severity=ValidationSeverity.WARNING,
                        message=f"设备清单第 {item.item_index} 行提取置信度较低。",
                        field_names=[f"equipment_items[{item.item_index}]"],
                    )
                )
            for name in ("quantity", "unit_power_w", "total_power_kw"):
                field = getattr(item, name)
                if field is None:
                    continue
                try:
                    value = Decimal(str(field.normalized_value))
                except InvalidOperation:
                    continue
                if value <= 0:
                    issues.append(
                        ValidationIssue(
                            code="invalid_non_positive_value",
                            severity=ValidationSeverity.ERROR,
                            message=(
                                f"设备清单第 {item.item_index} 行的“{field.display_name}”"
                                "应为正数。"
                            ),
                            field_names=[f"equipment_items[{item.item_index}].{name}"],
                        )
                    )
            if item.quantity and item.unit_power_w and item.total_power_kw:
                try:
                    calculated_kw = (
                        Decimal(str(item.quantity.normalized_value))
                        * Decimal(str(item.unit_power_w.normalized_value))
                        / Decimal("1000")
                    )
                    stated_kw = Decimal(str(item.total_power_kw.normalized_value))
                except InvalidOperation:
                    continue
                tolerance = max(Decimal("0.1"), abs(stated_kw) * Decimal("0.001"))
                if abs(calculated_kw - stated_kw) > tolerance:
                    issues.append(
                        ValidationIssue(
                            code="arithmetic_mismatch",
                            severity=ValidationSeverity.WARNING,
                            message=(
                                f"设备清单第 {item.item_index} 行的数量×单台功率"
                                "与合计功率不一致。"
                            ),
                            field_names=[f"equipment_items[{item.item_index}]"],
                        )
                    )
        return issues

    @staticmethod
    def _best_fields(fields: list[ExtractedField]) -> dict[str, ExtractedField]:
        best: dict[str, ExtractedField] = {}
        for field in fields:
            current = best.get(field.field_name)
            if current is None or field.confidence > current.confidence:
                best[field.field_name] = field
        return best
