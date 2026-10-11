import re
import unicodedata
from decimal import Decimal, InvalidOperation

from app.schemas.analysis import BatchValidationRequest, BatchValidationResult
from app.schemas.extraction import ExtractedField
from app.schemas.validation import BatchValidationIssue, ValidationSeverity


TEXT_FIELD_GROUPS_TO_COMPARE = (
    (("project_name",), "project_name", "项目名称"),
    (("project_location", "risk_location"), "project_location", "项目/标的地点"),
    (("insured_name",), "insured_name", "被保险人"),
    (("insurance_period_start",), "insurance_period_start", "保险期间开始日期"),
    (("insurance_period_end",), "insurance_period_end", "保险期间结束日期"),
)

EXACT_NUMERIC_FIELDS_TO_COMPARE = {
    "module_count": "组件数量",
    "inverter_count": "逆变器数量",
}


class BatchConsistencyValidator:
    """比较同一项目组内多份材料的关键字段，不进行业务风险判断。"""

    def validate(self, request: BatchValidationRequest) -> BatchValidationResult:
        issues: list[BatchValidationIssue] = []
        failed_ids = [
            item.document.document_id
            for item in request.documents
            if item.processing_status.value == "failed"
        ]
        if failed_ids:
            issues.append(
                BatchValidationIssue(
                    code="document_analysis_failed",
                    severity=ValidationSeverity.ERROR,
                    message="部分文档分析失败，无法完成全部一致性校验。",
                    document_ids=failed_ids,
                )
            )

        for field_names, output_name, display_name in TEXT_FIELD_GROUPS_TO_COMPARE:
            values = self._collect_best_values_from_names(request, field_names)
            normalized = {self._comparison_key(value) for value, _document_id in values}
            normalized.discard("")
            if len(normalized) > 1:
                issues.append(
                    BatchValidationIssue(
                        code="cross_document_conflict",
                        severity=ValidationSeverity.WARNING,
                        message=f"不同文档中的“{display_name}”不一致。",
                        field_name=output_name,
                        document_ids=[document_id for _value, document_id in values],
                        observed_values={
                            document_id: str(value) for value, document_id in values
                        },
                    )
                )

        capacity_values = self._collect_best_values(request, "project_capacity_kw")
        if self._numeric_values_conflict(capacity_values):
            issues.append(
                BatchValidationIssue(
                    code="cross_document_capacity_conflict",
                    severity=ValidationSeverity.WARNING,
                    message="不同文档中的项目容量超出允许误差。",
                    field_name="project_capacity_kw",
                    document_ids=[document_id for _value, document_id in capacity_values],
                    observed_values={
                        document_id: str(value)
                        for value, document_id in capacity_values
                    },
                )
            )

        for field_name, display_name in EXACT_NUMERIC_FIELDS_TO_COMPARE.items():
            values = self._collect_best_values(request, field_name)
            if self._numeric_values_conflict_with_tolerance(values, Decimal("0")):
                issues.append(
                    BatchValidationIssue(
                        code="cross_document_count_conflict",
                        severity=ValidationSeverity.WARNING,
                        message=f"不同文档中的“{display_name}”不一致。",
                        field_name=field_name,
                        document_ids=[document_id for _value, document_id in values],
                        observed_values={
                            document_id: str(value) for value, document_id in values
                        },
                    )
                )

        insurance_amounts = self._collect_best_values(request, "insurance_amount_cny")
        if self._numeric_values_conflict_with_tolerance(
            insurance_amounts, Decimal("0.01")
        ):
            issues.append(
                BatchValidationIssue(
                    code="cross_document_insurance_amount_conflict",
                    severity=ValidationSeverity.WARNING,
                    message="不同投保材料中的保险金额不一致。",
                    field_name="insurance_amount_cny",
                    document_ids=[
                        document_id for _value, document_id in insurance_amounts
                    ],
                    observed_values={
                        document_id: str(value)
                        for value, document_id in insurance_amounts
                    },
                )
            )

        consistent = not any(
            issue.severity in {ValidationSeverity.WARNING, ValidationSeverity.ERROR}
            for issue in issues
        )
        return BatchValidationResult(
            project_group_id=request.project_group_id,
            checked_documents=len(request.documents),
            consistent=consistent,
            issues=issues,
        )

    @staticmethod
    def _collect_best_values(
        request: BatchValidationRequest, field_name: str
    ) -> list[tuple[object, str]]:
        values: list[tuple[object, str]] = []
        for document in request.documents:
            matching = [
                field for field in document.extracted_fields if field.field_name == field_name
            ]
            if not matching:
                continue
            best: ExtractedField = max(matching, key=lambda field: field.confidence)
            values.append((best.normalized_value, document.document.document_id))
        return values

    @staticmethod
    def _collect_best_values_from_names(
        request: BatchValidationRequest, field_names: tuple[str, ...]
    ) -> list[tuple[object, str]]:
        values: list[tuple[object, str]] = []
        accepted = set(field_names)
        for document in request.documents:
            matching = [
                field
                for field in document.extracted_fields
                if field.field_name in accepted
            ]
            if not matching:
                continue
            best = max(matching, key=lambda field: field.confidence)
            values.append((best.normalized_value, document.document.document_id))
        return values

    @staticmethod
    def _comparison_key(value: object) -> str:
        text = unicodedata.normalize("NFKC", str(value)).casefold()
        return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)

    @staticmethod
    def _numeric_values_conflict(values: list[tuple[object, str]]) -> bool:
        if len(values) < 2:
            return False
        try:
            decimals = [Decimal(str(value)) for value, _document_id in values]
        except InvalidOperation:
            return False
        baseline = decimals[0]
        tolerance = max(Decimal("0.1"), abs(baseline) * Decimal("0.001"))
        return any(abs(value - baseline) > tolerance for value in decimals[1:])

    @staticmethod
    def _numeric_values_conflict_with_tolerance(
        values: list[tuple[object, str]], tolerance: Decimal
    ) -> bool:
        if len(values) < 2:
            return False
        try:
            decimals = [Decimal(str(value)) for value, _document_id in values]
        except InvalidOperation:
            return False
        return any(abs(value - decimals[0]) > tolerance for value in decimals[1:])
